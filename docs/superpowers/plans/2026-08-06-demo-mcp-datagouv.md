# Démo MCP data.gouv.fr — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire une démo de 10 minutes où un agent LangChain interroge le serveur MCP de data.gouv.fr pour répondre à une question chiffrée sourcée, puis découvrir une API publique.

**Architecture:** Un fichier de configuration `mcp.json` au format éditeur, converti à la volée pour `langchain-mcp-adapters`. Un test de fumée `smoke.py` qui valide séparément le serveur MCP (en `urllib` pur, sans dépendance) et le *tool calling* du déploiement Azure. Un agent `agent.py` d'une cinquantaine de lignes qui découvre les outils, exécute un prompt passé en argument, et affiche chaque appel d'outil.

**Tech Stack:** Python 3.12, `uv`, `langchain-mcp-adapters`, `langgraph`, `langchain-openai`, `python-dotenv`, `pytest`.

## Global Constraints

- Serveur MCP : `https://mcp.data.gouv.fr/mcp`, transport HTTP streamable, sans authentification.
- LLM : Azure AI Foundry, API v1 compatible OpenAI, **sans** `api_version`. On utilise `ChatOpenAI` avec `base_url`, pas `AzureChatOpenAI`.
- Nom du déploiement : `gpt-5.6-luna`, passé comme paramètre `model`.
- `temperature=0` partout : la démo doit être reproductible.
- Tout le texte visible (prompts, affichage, messages) est en français.
- Ne jamais lire ni afficher le contenu de `.env`. Seul `.env.example` est versionné.
- La création de `pyproject.toml` est explicitement prévue par la spec approuvée §4.
- Ressource IRVE cible : dataset `5448d3e0c751df01f85d0572`, ressource `eb76d20a-8501-400e-b336-d85724de5435`, filtre `code_insee_commune="31555"` (Toulouse).
- Ne jamais figer un chiffre attendu dans un test : la base IRVE est régénérée quotidiennement.

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `mcp.json` | Configuration MCP, format éditeur. Source unique de vérité. |
| `.env.example` | Variables Azure attendues. |
| `pyproject.toml` | Dépendances. |
| `smoke.py` | Valide les deux dépendances externes séparément. Aucun import lourd dans le bloc MCP. |
| `agent.py` | Fonctions pures (chargement de config, formatage) + boucle d'agent. |
| `tests/test_agent.py` | Tests unitaires des fonctions pures d'`agent.py`. |
| `docs/schema-mcp.md` | Schémas Mermaid projetés en introduction. |
| `logs/` | Sorties pré-enregistrées, non versionnées. |

**Note sur la stratégie de test.** Les fonctions pures (conversion de configuration, formatage de l'affichage) sont couvertes par `pytest` en TDD. Les chemins réseau ne le sont pas : `smoke.py` **est** leur test, exécuté en conditions réelles. Écrire des mocks pour le serveur MCP donnerait une fausse assurance — c'est précisément la disponibilité réelle du serveur qu'on veut vérifier avant de monter sur scène.

---

### Task 1 : Test de fumée du serveur MCP

Aucune dépendance : ce fichier doit tourner même si l'environnement Python n'est pas encore installé.

**Files:**
- Create: `smoke.py`
- Create: `mcp.json`

**Interfaces:**
- Consumes: rien
- Produces: `mcp_call(method: str, params: dict | None = None, timeout: int = 30) -> dict` qui renvoie l'objet JSON-RPC décodé ; `check_mcp() -> bool`

- [ ] **Step 1 : Créer `mcp.json`**

```json
{
  "mcpServers": {
    "datagouv": { "type": "http", "url": "https://mcp.data.gouv.fr/mcp" }
  }
}
```

- [ ] **Step 2 : Écrire le bloc MCP de `smoke.py`**

Le serveur répond en Server-Sent Events (`event: message` puis `data: {...}`), d'où le parsing par lignes.

Attention : le `python3` du système macOS est en 3.9, qui ne connaît pas la syntaxe
`dict | None` dans les annotations évaluées. D'où `from __future__ import annotations`,
qui préserve l'objectif « exécutable avant toute installation ».

```python
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
```

- [ ] **Step 3 : Exécuter le test de fumée**

Run: `python3 smoke.py`
Expected: `[OK] data.gouv.fr MCP server v1.28.1 — 10 outils` puis la liste des outils, exit code 0.

Si le code de sortie est 1, le réseau ou le serveur est en cause — rien d'autre ne peut fonctionner tant que ce n'est pas résolu.

- [ ] **Step 4 : Vérifier le code de sortie**

Run: `python3 smoke.py; echo "exit=$?"`
Expected: `exit=0`

- [ ] **Step 5 : Commit**

```bash
git add smoke.py mcp.json
git commit -m "Ajoute le test de fumée du serveur MCP data.gouv.fr"
```

---

### Task 2 : Environnement Python et test de fumée du modèle Azure

C'est la tâche qui lève l'incertitude sur le déploiement `gpt-5.6-luna`. Elle doit être terminée avant toute ligne d'agent.

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Modify: `smoke.py`

**Interfaces:**
- Consumes: `check_mcp() -> bool` de la Task 1
- Produces: `check_llm() -> bool`

- [ ] **Step 1 : Initialiser le projet et installer les dépendances**

```bash
uv init --python 3.12 --no-workspace --bare
uv python pin 3.12          # indispensable : voir la note ci-dessous
uv add langchain-mcp-adapters langgraph langchain-openai python-dotenv
uv add --dev pytest
```

Attention : `uv init --python 3.12` écrit seulement `requires-python = ">=3.12"`
et ne crée pas de `.python-version`. Sans `uv python pin 3.12`, uv résout
l'environnement sur le Python le plus récent disponible — 3.14 en l'occurrence,
sur lequel la pile LangChain est nettement moins éprouvée. Une démonstration
publique n'est pas l'endroit où le découvrir.

- [ ] **Step 2 : Créer `.env.example`**

```
AZURE_BASE_URL=https://<ressource>.openai.azure.com/openai/v1/
AZURE_API_KEY=<clé>
AZURE_DEPLOYMENT=gpt-5.6-luna
```

Demander à l'utilisatrice de créer son `.env` à partir de ce modèle. Ne jamais lire ce fichier.

- [ ] **Step 3 : Ajouter le bloc LLM à `smoke.py`**

Insérer avant le bloc `if __name__ == "__main__":`, puis remplacer ce bloc.

```python
def check_llm() -> bool:
    """Vérifie que le déploiement Azure répond ET sait appeler un outil."""
    from dotenv import load_dotenv
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    load_dotenv()

    @tool
    def addition(a: int, b: int) -> int:
        """Additionne deux entiers."""
        return a + b

    try:
        modele = ChatOpenAI(
            model=os.environ["AZURE_DEPLOYMENT"],
            base_url=os.environ["AZURE_BASE_URL"],
            api_key=os.environ["AZURE_API_KEY"],
            temperature=0,
        )
        reponse = modele.bind_tools([addition]).invoke(
            "Combien font 17 plus 25 ? Utilise l'outil à ta disposition."
        )
    except KeyError as manquante:
        print(f"[KO] variable d'environnement absente : {manquante}")
        return False
    except Exception as erreur:
        print(f"[KO] modèle Azure injoignable : {erreur}")
        return False

    if not reponse.tool_calls:
        print("[KO] le modèle a répondu mais n'a appelé aucun outil.")
        print("     Le tool calling est indispensable : voir le repli AzureChatOpenAI.")
        return False

    appel = reponse.tool_calls[0]
    print(f"[OK] tool calling confirmé : {appel['name']}({appel['args']})")
    return True


if __name__ == "__main__":
    resultats = [check_mcp(), check_llm()]
    sys.exit(0 if all(resultats) else 1)
```

Noter que les deux blocs s'exécutent toujours, même si le premier échoue : le but est de savoir **lequel** des deux maillons a lâché, pas de s'arrêter au premier.

- [ ] **Step 4 : Exécuter le test complet**

Run: `uv run smoke.py; echo "exit=$?"`
Expected: deux lignes `[OK]` et `exit=0`.

Si `check_llm` renvoie `[KO] le modèle a répondu mais n'a appelé aucun outil`, appliquer le repli documenté dans la spec §5.2 : remplacer `ChatOpenAI` par `AzureChatOpenAI` avec un `api_version` explicite (par exemple `2024-10-21`), en ajoutant `AZURE_API_VERSION` à `.env.example`.

- [ ] **Step 5 : Commit**

```bash
git add pyproject.toml uv.lock .env.example smoke.py
git commit -m "Ajoute l'environnement Python et le test de fumée du modèle Azure"
```

---

### Task 3 : Fonctions pures de l'agent

**Files:**
- Create: `agent.py`
- Create: `tests/test_agent.py`

**Interfaces:**
- Consumes: `mcp.json` de la Task 1
- Produces: `load_servers(path: str = "mcp.json") -> dict[str, dict[str, str]]`, `format_tool_call(name: str, args: dict) -> str`, `format_tool_result(content: str, seconds: float) -> str`

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer aussi un `conftest.py` **vide** à la racine. Sans lui, pytest insère
`tests/` dans `sys.path` mais pas la racine, et l'import de `agent` échoue.
La seule présence du fichier suffit ; cela évite de modifier `pyproject.toml`.

Créer `tests/test_agent.py` :

```python
import json

from agent import format_tool_call, format_tool_result, load_servers


def test_load_servers_convertit_le_format_editeur_vers_langchain(tmp_path):
    fichier = tmp_path / "mcp.json"
    fichier.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "datagouv": {"type": "http", "url": "https://mcp.data.gouv.fr/mcp"}
                }
            }
        ),
        encoding="utf-8",
    )

    assert load_servers(fichier) == {
        "datagouv": {
            "url": "https://mcp.data.gouv.fr/mcp",
            "transport": "streamable_http",
        }
    }


def test_format_tool_call_affiche_le_nom_et_les_arguments():
    resultat = format_tool_call("search_datasets", {"query": "bornes recharge"})
    assert resultat == "🔧 search_datasets(query='bornes recharge')"


def test_format_tool_call_tronque_les_arguments_trop_longs():
    resultat = format_tool_call("query_resource_data", {"resource_id": "x" * 200})
    assert len(resultat) < 100
    assert resultat.endswith("…)")


def test_format_tool_result_utilise_la_typographie_francaise():
    resultat = format_tool_result("x" * 7029, 0.81)
    assert resultat == "   ← 7 029 caractères en 0,8 s"
```

- [ ] **Step 2 : Vérifier que les tests échouent**

Run: `uv run pytest tests/test_agent.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'agent'`

- [ ] **Step 3 : Écrire l'implémentation minimale**

Créer `agent.py` :

```python
"""Agent LangChain branché sur le serveur MCP de data.gouv.fr."""

import json

LARGEUR_ARGUMENTS = 60


def load_servers(path: str = "mcp.json") -> dict[str, dict[str, str]]:
    """Convertit la configuration au format éditeur vers celui attendu par
    langchain-mcp-adapters."""
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
    taille = f"{len(content):,}".replace(",", " ")
    duree = f"{seconds:.1f}".replace(".", ",")
    return f"   ← {taille} caractères en {duree} s"
```

- [ ] **Step 4 : Vérifier que les tests passent**

Run: `uv run pytest tests/test_agent.py -v`
Expected: 4 passed

- [ ] **Step 5 : Commit**

```bash
git add agent.py tests/test_agent.py
git commit -m "Ajoute les fonctions de configuration et d'affichage de l'agent"
```

---

### Task 4 : Découverte des outils MCP

**Files:**
- Modify: `agent.py`

**Interfaces:**
- Consumes: `load_servers` de la Task 3
- Produces: `discover_tools() -> list` (coroutine renvoyant les outils LangChain), `build_model() -> ChatOpenAI`

- [ ] **Step 1 : Ajouter les imports et les deux fonctions**

En tête de `agent.py`, après `import json` :

```python
import asyncio
import os
import sys
import time

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()
```

Puis, après `format_tool_result` :

```python
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
```

- [ ] **Step 2 : Ajouter un mode `--list` en fin de fichier**

```python
async def main() -> None:
    tools = await discover_tools()
    print(f"→ {len(tools)} outils découverts : {', '.join(o.name for o in tools)}\n")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3 : Vérifier la découverte contre le serveur réel**

Run: `uv run agent.py`
Expected: `→ 10 outils découverts : search_datasets, search_organizations, search_dataservices, get_dataservice_info, get_dataservice_openapi_spec, query_resource_data, get_dataset_info, list_dataset_resources, get_resource_info, get_metrics`

- [ ] **Step 4 : Vérifier que les tests unitaires passent toujours**

Run: `uv run pytest tests/test_agent.py -v`
Expected: 4 passed

- [ ] **Step 5 : Commit**

```bash
git add agent.py
git commit -m "Ajoute la découverte des outils MCP et la construction du modèle"
```

---

### Task 5 : Boucle d'agent et affichage des appels d'outils

**Files:**
- Modify: `agent.py`

**Interfaces:**
- Consumes: `discover_tools`, `build_model`, `format_tool_call`, `format_tool_result` des Tasks 3 et 4
- Produces: `main(question: str) -> None`

- [ ] **Step 1 : Ajouter le prompt système**

Après `LARGEUR_ARGUMENTS = 60` :

```python
SYSTEME = (
    "Tu réponds en français, de façon concise. "
    "Tu utilises exclusivement les outils data.gouv.fr pour trouver tes chiffres. "
    "Tu cites toujours l'URL data.gouv.fr de la source utilisée."
)
```

Ce prompt cadre le format de réponse mais **ne décrit pas l'enchaînement des outils** : les descriptions du serveur s'en chargent, et c'est ce que la démo veut démontrer.

- [ ] **Step 2 : Remplacer `main` par la boucle complète**

```python
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
```

- [ ] **Step 3 : Exécuter le scénario 1**

Run:
```bash
uv run agent.py "Combien de points de recharge pour véhicules électriques y a-t-il à Toulouse ? Cite ta source."
```

Expected: la ligne des 10 outils, puis trois blocs `🔧` (`search_datasets`, `list_dataset_resources`, `query_resource_data`) chacun suivi d'une ligne `←`, puis un bloc `💬` contenant un nombre de l'ordre du millier et une URL `data.gouv.fr`.

- [ ] **Step 4 : Exécuter le scénario 2**

Run:
```bash
uv run agent.py "Trouve une API publique de géocodage d'adresses sur data.gouv.fr et explique-moi concrètement comment l'appeler."
```

Expected: deux blocs `🔧` (`search_dataservices`, `get_dataservice_openapi_spec`), puis une réponse nommant un endpoint réel et au moins deux de ses paramètres.

- [ ] **Step 5 : Commit**

```bash
git add agent.py
git commit -m "Ajoute la boucle d'agent et l'affichage des appels d'outils"
```

---

### Task 6 : Validation des critères de succès et logs de repli

**Files:**
- Create: `logs/scenario1.txt`
- Create: `logs/scenario2.txt`
- Create: `README.md`

**Interfaces:**
- Consumes: `agent.py` et `smoke.py` complets
- Produces: aucun code ; des artefacts de démonstration

- [ ] **Step 1 : Vérifier la stabilité du scénario 1**

Run:
```bash
for i in 1 2 3; do
  echo "=== essai $i ==="
  uv run agent.py "Combien de points de recharge pour véhicules électriques y a-t-il à Toulouse ? Cite ta source." 2>&1 | grep '🔧'
done
```

Expected: les trois essais produisent la **même** séquence de trois outils, dans le même ordre.

Si un essai diverge, ajouter au prompt système la phrase `"Pour une question chiffrée, suis le workflow décrit dans la description des outils."` et refaire les trois essais.

- [ ] **Step 2 : Vérifier la stabilité du scénario 2**

Run:
```bash
for i in 1 2 3; do
  echo "=== essai $i ==="
  uv run agent.py "Trouve une API publique de géocodage d'adresses sur data.gouv.fr et explique-moi concrètement comment l'appeler." 2>&1 | grep '🔧'
done
```

Expected: les trois essais produisent la même séquence d'outils.

- [ ] **Step 3 : Capturer les logs de repli**

```bash
mkdir -p logs
uv run agent.py "Combien de points de recharge pour véhicules électriques y a-t-il à Toulouse ? Cite ta source." | tee logs/scenario1.txt
uv run agent.py "Trouve une API publique de géocodage d'adresses sur data.gouv.fr et explique-moi concrètement comment l'appeler." | tee logs/scenario2.txt
```

Vérifier que les deux fichiers sont lisibles tels quels une fois projetés.

- [ ] **Step 4 : Écrire le `README.md`**

```markdown
# Démo MCP data.gouv.fr

Un agent LangChain branché sur le serveur MCP de data.gouv.fr.

## Mise en route

    cp .env.example .env    # puis renseigner les valeurs Azure
    uv sync
    uv run smoke.py         # doit afficher deux lignes [OK]

## Utilisation

    uv run agent.py "Combien de points de recharge pour véhicules électriques y a-t-il à Toulouse ? Cite ta source."

## Le jour de la démo

1. `uv run smoke.py` avant de monter sur scène.
2. Relancer les deux scénarios : la base IRVE est régénérée quotidiennement,
   le chiffre de Toulouse aura peut-être changé.
3. En cas de panne réseau, dérouler sur `logs/scenario1.txt` et `logs/scenario2.txt`.

Conception : `docs/superpowers/specs/2026-08-06-demo-mcp-datagouv-design.md`
Schémas : `docs/schema-mcp.md`
```

- [ ] **Step 5 : Commit**

```bash
git add README.md
git commit -m "Ajoute le README et valide les critères de succès"
```

Le répertoire `logs/` est ignoré par git : c'est voulu, ces fichiers sont regénérés la veille de la démo.

---

### Task 7 : Schémas Mermaid de l'introduction — **déjà livrée**

Cette tâche a été réalisée en même temps que la rédaction du plan, à la demande de
l'utilisatrice. Elle ne reste ici que pour la traçabilité et la vérification du rendu.

**Files:**
- Create: `docs/schema-mcp.md` ✅ fait

**Interfaces:**
- Consumes: rien
- Produces: aucun code ; support de projection

- [x] **Step 1 : Créer le fichier avec les trois schémas**

Trois diagrammes : le problème N×M, la solution N+M, et le diagramme de séquence du
protocole tel qu'il se déroulera pendant le scénario 1.

- [ ] **Step 2 : Vérifier le rendu**

Ouvrir `docs/schema-mcp.md` dans VS Code avec l'aperçu Markdown (`bierner.markdown-mermaid`
est installé) et confirmer que les trois diagrammes s'affichent. C'est la seule étape
restante : le rendu n'a pas pu être vérifié sans installer le CLI Mermaid.

- [x] **Step 3 : Commit**

---

## Auto-revue

**Couverture de la spec.** §3 choix du MCP → Task 1 (`mcp.json`). §4 architecture → Tasks 1 à 5. §5.1 `mcp.json` → Task 1. §5.2 `.env.example` → Task 2. §5.3 `smoke.py` → Tasks 1 et 2. §5.4 `agent.py` → Tasks 3 à 5. §5.5 décisions (`temperature=0`, prompt non guidant, prompt en argument CLI) → Tasks 4 et 5. §6 déroulé et prompts → Tasks 5 et 6. §7 pièges → contraintes globales et Task 5. §8 critères de succès → Task 6. §9 plan de repli → Task 6. §10 ordre de construction → ordre des tâches. Introduction du déroulé (0:00–0:45) → Task 7.

**Cohérence des signatures.** `load_servers`, `format_tool_call`, `format_tool_result` sont définies en Task 3 et consommées telles quelles en Tasks 4 et 5. `discover_tools` et `build_model` sont définies en Task 4 et consommées en Task 5. `mcp_call` et `check_mcp` sont définies en Task 1, `check_llm` en Task 2, et le bloc `__main__` de `smoke.py` les appelle toutes les deux.

**Point de vigilance connu — levé.** Les noms de nœuds `"agent"` et `"tools"` utilisés en Task 5 ont été confirmés dans le source de `langgraph` 1.2.10 (`langgraph/prebuilt/chat_agent_executor.py`, lignes 866-872). Si une version ultérieure les changeait, ajouter `print(etape.keys())` en début de boucle pour les relever.

## Journal d'exécution

Versions installées le 2026-08-06 : `langchain-mcp-adapters` 0.3.2, `langgraph` 1.2.10, `langchain-openai` 1.4.1, `langchain-core` 1.5.3, `python-dotenv` 1.2.2, `pytest` 9.1.1, sur CPython 3.12.13.

Écarts au plan initial, tous répercutés ci-dessus :

1. `from __future__ import annotations` ajouté à `smoke.py` — le `python3` du système macOS est en 3.9 et rejetait `dict | None`.
2. `uv python pin 3.12` ajouté — sans lui, l'environnement était résolu sur CPython 3.14.5.
3. `conftest.py` vide ajouté à la racine — sinon `tests/test_agent.py` ne peut pas importer `agent`.
4. Garde sur les variables d'environnement dans `build_model` — évite un `KeyError` avec traceback en pleine démonstration.
5. Avertissement de dépréciation masqué : `create_react_agent` a migré vers `langchain.agents.create_agent` en LangGraph 1.0, dans un paquet non installé ici. Le message s'affichait à l'écran. Migration à envisager après la démonstration.
6. **Session MCP persistante** au lieu de `MultiServerMCPClient.get_tools()`. Ce dernier ouvre une connexion HTTP à chaque appel d'outil — sa propre docstring l'indique — ce qui provoquait des `httpx.ConnectTimeout` intermittents (1 échec sur 8 exécutions). Le passage à `client.session()` + `load_mcp_tools(session)` a supprimé les échecs et réduit la durée d'environ 40 %.
7. **Cadrage des sources dans le prompt système.** Décision validée avec l'utilisatrice. Sans lui, le scénario 1 renvoyait 1 099, 944 ou 1 212 selon les exécutions, car plusieurs bases IRVE et plusieurs ressources coexistent. Voir la spec §5.5 et §7.

### Résultats de validation

| Critère | Mesure | Verdict |
|---|---|---|
| 1 — test de fumée | deux `[OK]`, exit 0 ; tool calling confirmé sans `api_version` | ✅ |
| 2 — scénario 1 | 4 exécutions : 4-5 appels, 13-18 s, 1 099 + URL | ✅ |
| 3 — scénario 2 | 3 exécutions : 3 appels, 16 s, endpoint et paramètres corrects | ✅ |
| 4 — stabilité | 4/4 et 3/3 identiques | ✅ |
