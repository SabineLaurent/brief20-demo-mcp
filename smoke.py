"""Test de fumée : valide séparément le serveur MCP et le modèle Azure.

Le bloc MCP doit rester exécutable par n'importe quel Python 3, y compris
celui du système (3.9 sur macOS), afin de pouvoir diagnostiquer le réseau
avant même que l'environnement du projet ne soit installé. D'où l'import
`annotations` ci-dessous et l'absence de toute dépendance externe.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

MCP_URL = "https://mcp.data.gouv.fr/mcp"


def mcp_call(method: str, params: dict | None = None, timeout: int = 30) -> dict:
    """Appelle le serveur MCP en JSON-RPC et renvoie la réponse décodée."""
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    ).encode()
    request = urllib.request.Request(
        MCP_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    raw = urllib.request.urlopen(request, timeout=timeout).read().decode()
    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(raw)


def check_mcp() -> bool:
    """Vérifie que le serveur répond au handshake et expose ses outils."""
    try:
        handshake = mcp_call(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "1.0"},
            },
        )
        server = handshake["result"]["serverInfo"]
        tools = mcp_call("tools/list")["result"]["tools"]
    except Exception as erreur:
        print(f"[KO] serveur MCP injoignable : {erreur}")
        return False

    print(f"[OK] {server['name']} v{server['version']} — {len(tools)} outils")
    print("     " + ", ".join(outil["name"] for outil in tools))
    if len(tools) != 10:
        print(f"     Attention : 10 outils attendus, {len(tools)} reçus.")
    return len(tools) > 0


if __name__ == "__main__":
    sys.exit(0 if check_mcp() else 1)
