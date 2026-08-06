"""Agent LangChain branché sur le serveur MCP de data.gouv.fr."""

import asyncio
import json
import os
import sys
import time
import warnings

# create_react_agent est déprécié depuis LangGraph 1.0 au profit de
# langchain.agents.create_agent, qui vit dans un paquet non installé ici.
# L'avertissement est masqué pour ne pas polluer l'écran pendant la démo.
warnings.filterwarnings("ignore", message=".*create_react_agent.*")

from dotenv import load_dotenv  # noqa: E402
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

LARGEUR_ARGUMENTS = 60

# Ce prompt ne décrit PAS l'enchaînement des outils : les descriptions fournies
# par le serveur MCP s'en chargent déjà, et c'est ce que la démonstration montre.
#
# En revanche il tranche les ambiguïtés de SOURCE. Sans ce cadrage, l'agent
# hésitait entre plusieurs bases nationales IRVE et plusieurs ressources, et
# renvoyait un chiffre différent à chaque exécution (1 099, puis 944, puis
# 1 212). C'est le rôle normal d'un prompt système en production. Il n'est pas
# projeté pendant la démonstration : la question posée à l'écran reste naturelle.
SYSTEME = (
    "Tu réponds en français, de façon concise. "
    "Tu utilises exclusivement les outils data.gouv.fr pour trouver tes chiffres. "
    "Tu cites toujours l'URL data.gouv.fr de la source utilisée.\n"
    "Méthode à suivre :\n"
    "- Pour chercher un jeu, emploie deux ou trois mots-clés spécifiques et "
    "n'y mets jamais le nom de la commune : la recherche combine les mots par "
    "un ET logique et ne renverrait rien.\n"
    "- Si plusieurs jeux de données conviennent, retiens celui publié par "
    "l'organisation data.gouv.fr elle-même et ignore les versions beta.\n"
    "- Dans un jeu, retiens la ressource CSV consolidée la plus récente.\n"
    "- Pour compter les enregistrements d'une commune, filtre avec "
    "filter_column='code_insee_commune', filter_operator='exact', puis lis le "
    "nombre total de lignes renvoyé par l'outil.\n"
    "- Dès que tu disposes d'une réponse chiffrée, arrête-toi et réponds.\n"
    "Mise en forme : la réponse s'affiche dans un terminal qui ne rend pas le "
    "markdown. N'emploie donc ni astérisques de gras, ni liens entre crochets : "
    "écris l'URL de la source telle quelle, sur sa propre ligne. Les blocs de "
    "code délimités par des accents graves restent en revanche bienvenus."
)


def load_servers(path: str = "mcp.json") -> dict[str, dict[str, str]]:
    """Convertit la configuration au format éditeur vers celui attendu par
    langchain-mcp-adapters.

    Le fichier mcp.json utilise la clé `type: http`, comprise par les éditeurs.
    langchain-mcp-adapters attend `transport: streamable_http`. Le protocole est
    standardisé, le format du fichier de configuration ne l'est pas encore.
    """
    with open(path, encoding="utf-8") as fichier:
        serveurs = json.load(fichier)["mcpServers"]
    return {
        nom: {"url": config["url"], "transport": "streamable_http"}
        for nom, config in serveurs.items()
    }


def format_tool_call(name: str, args: dict) -> str:
    """Rend un appel d'outil sur une ligne, arguments tronqués si nécessaire."""
    rendu = ", ".join(f"{cle}={valeur!r}" for cle, valeur in args.items())
    if len(rendu) > LARGEUR_ARGUMENTS:
        rendu = rendu[: LARGEUR_ARGUMENTS - 1] + "…"
    return f"🔧 {name}({rendu})"


def format_tool_result(content: str, seconds: float) -> str:
    """Rend la taille et la durée d'une réponse d'outil, typographie française."""
    taille = f"{len(content):,}".replace(",", " ")
    duree = f"{seconds:.1f}".replace(".", ",")
    return f"   ← {taille} caractères en {duree} s"


async def discover_tools(session) -> list:
    """Renvoie les outils exposés par le serveur, sur une session déjà ouverte.

    On passe par une session explicite plutôt que par MultiServerMCPClient.get_tools() :
    ce dernier ouvre une connexion HTTP neuve à CHAQUE appel d'outil, ce qui multiplie
    les occasions de tomber sur un httpx.ConnectTimeout. Une session unique suffit.
    """
    return await load_mcp_tools(session)


def build_model() -> ChatOpenAI:
    """Construit le modèle Azure via l'API v1 compatible OpenAI."""
    manquantes = [
        nom
        for nom in ("AZURE_DEPLOYMENT", "AZURE_BASE_URL", "AZURE_API_KEY")
        if nom not in os.environ
    ]
    if manquantes:
        print(f"\nVariables d'environnement absentes : {', '.join(manquantes)}")
        print("Copier .env.example vers .env et renseigner les valeurs.")
        sys.exit(1)

    return ChatOpenAI(
        model=os.environ["AZURE_DEPLOYMENT"],
        base_url=os.environ["AZURE_BASE_URL"],
        api_key=os.environ["AZURE_API_KEY"],
        temperature=0,
    )


async def main(question: str) -> None:
    serveurs = load_servers()
    client = MultiServerMCPClient(serveurs)

    async with client.session(next(iter(serveurs))) as session:
        tools = await discover_tools(session)
        print(f"→ {len(tools)} outils découverts : {', '.join(o.name for o in tools)}\n")

        agent = create_react_agent(model=build_model(), tools=tools, prompt=SYSTEME)
        chronos: dict[str, float] = {}

        async for etape in agent.astream(
            {"messages": [("user", question)]}, stream_mode="updates"
        ):
            for noeud, contenu in etape.items():
                for message in contenu.get("messages", []):
                    if noeud == "agent" and getattr(message, "tool_calls", None):
                        for appel in message.tool_calls:
                            print(format_tool_call(appel["name"], appel["args"]))
                            chronos[appel["id"]] = time.perf_counter()
                    elif noeud == "tools":
                        debut = chronos.pop(message.tool_call_id, None)
                        ecoule = time.perf_counter() - debut if debut else 0.0
                        print(format_tool_result(str(message.content), ecoule))
                    elif noeud == "agent" and message.content:
                        print(f"\n💬 {message.content}")


def lire_question(argv: list[str]) -> str:
    """Renvoie la question passée en argument, ou la demande au clavier.

    Saisir la question en direct est plus vivant qu'une commande pré-écrite, et
    évite les mésaventures de quoting sur les apostrophes françaises.
    """
    if len(argv) > 1:
        return " ".join(argv[1:]).strip()

    question = input("❓ Ta question : ").strip()
    if not question:
        print("Aucune question saisie.")
        sys.exit(1)
    return question


if __name__ == "__main__":
    asyncio.run(main(lire_question(sys.argv)))
