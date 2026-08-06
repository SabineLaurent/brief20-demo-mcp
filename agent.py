"""Agent LangChain branché sur le serveur MCP de data.gouv.fr."""

import json

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
