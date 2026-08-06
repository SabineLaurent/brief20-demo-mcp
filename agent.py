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
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

LARGEUR_ARGUMENTS = 60

# Ce prompt cadre le format de la réponse mais ne décrit PAS l'enchaînement des
# outils : les descriptions fournies par le serveur MCP s'en chargent déjà.
# C'est précisément ce que la démonstration cherche à montrer.
SYSTEME = (
    "Tu réponds en français, de façon concise. "
    "Tu utilises exclusivement les outils data.gouv.fr pour trouver tes chiffres. "
    "Tu cites toujours l'URL data.gouv.fr de la source utilisée."
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


async def discover_tools() -> list:
    """Ouvre la connexion MCP et renvoie les outils exposés par le serveur."""
    client = MultiServerMCPClient(load_servers())
    return await client.get_tools()


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
    tools = await discover_tools()
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage : uv run agent.py "ta question"')
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
