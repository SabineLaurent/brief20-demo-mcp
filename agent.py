"""Agent LangChain branché sur le serveur MCP de data.gouv.fr."""

import asyncio
import json
import os
import sys
import time

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

LARGEUR_ARGUMENTS = 60


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
    return ChatOpenAI(
        model=os.environ["AZURE_DEPLOYMENT"],
        base_url=os.environ["AZURE_BASE_URL"],
        api_key=os.environ["AZURE_API_KEY"],
        temperature=0,
    )


async def main() -> None:
    tools = await discover_tools()
    print(f"→ {len(tools)} outils découverts : {', '.join(o.name for o in tools)}\n")


if __name__ == "__main__":
    asyncio.run(main())
