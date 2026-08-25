# demo-mcp

Agent LangChain/LangGraph branché sur le serveur MCP public de data.gouv.fr.
L'agent découvre les outils exposés par le serveur, les appelle en boucle ReAct
pour répondre à une question en français, et cite l'URL data.gouv.fr de la
source utilisée.

Le serveur MCP fournit 10 outils (recherche de jeux de données, inspection des
ressources, requêtes sur les données tabulaires, métriques). Le dépôt ne
contient aucun code d'appel à l'API data.gouv.fr : tout passe par le protocole
MCP.

## Prérequis

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/)
- Un déploiement Azure AI Foundry exposant l'API v1 compatible OpenAI, avec le
  *tool calling* activé

## Installation

```bash
uv sync
cp .env.example .env    # puis renseigner les valeurs Azure
```

## Configuration

### Modèle

Trois variables, à renseigner dans `.env` (voir `.env.example`) :

| Variable | Description |
| --- | --- |
| `AZURE_BASE_URL` | URL de la ressource Azure, suffixe `/openai/v1/` compris |
| `AZURE_API_KEY` | Clé d'API |
| `AZURE_DEPLOYMENT` | Nom du **déploiement**, pas du modèle |

### Serveur MCP

`mcp.json` est la source unique de vérité. Il est au format des éditeurs et se
copie tel quel dans le client MCP de VS Code, Cursor ou Claude Code :

```json
{
  "mcpServers": {
    "datagouv": { "type": "http", "url": "https://mcp.data.gouv.fr/mcp" }
  }
}
```

Le serveur est public : aucune clé, aucune installation. `load_servers()` dans
[agent.py](agent.py) convertir ce format vers celui attendu par
`langchain-mcp-adapters` (`transport: streamable_http`) : le protocole est
standardisé, le format du fichier de configuration ne l'est pas encore.

## Utilisation

La question peut être passée en argument :

```bash
uv run agent.py "Combien de points de recharge pour véhicules électriques y a-t-il à Toulouse ? Cite ta source."
```

Sans argument, elle est demandée au clavier :

```bash
uv run agent.py
❓ Ta question : Combien de points de recharge y a-t-il à Bordeaux ?
```

La trace affiche chaque appel d'outil, la taille et la durée de sa réponse,
puis la réponse finale :

```text
→ 10 outils découverts : search_datasets, search_organizations, …

🔧 search_datasets(query='bornes recharge véhicules électriques', page=1, page…)
   ← 5 026 caractères en 0,8 s
🔧 list_dataset_resources(dataset_id='5448d3e0c751df01f85d0572')
   ← 1 805 caractères en 0,5 s
🔧 query_resource_data(resource_id='eb76d20a-8501-400e-b336-d85724de5435', page=1,…)
   ← 3 509 caractères en 0,6 s

💬 Toulouse compte 1 099 points de recharge pour véhicules électriques.

Source :
https://www.data.gouv.fr/datasets/base-nationale-des-irve-…
```

La réponse est produite en texte brut : le terminal ne rend pas le markdown.

## Vérification de l'environnement

```bash
uv run smoke.py    # doit afficher deux lignes [OK]
```

`smoke.py` valide les deux dépendances externes **séparément** — le serveur MCP
d'abord, le modèle Azure ensuite — et signale lequel des deux a échoué. Code de
sortie 0 si les deux passent.

Le bloc MCP n'a aucune dépendance externe : `python3 smoke.py` fonctionne même
sans environnement installé, ce qui permet de diagnostiquer le réseau avant
l'installation.

## Tests

```bash
uv run pytest -q
```

Les tests couvrent les fonctions pures de `agent.py` (conversion de la
configuration, formatage de la trace, lecture de la question). Les chemins
réseau ne sont pas simulés : `smoke.py` en tient lieu, en conditions réelles.

## Structure

| Fichier | Rôle |
| --- | --- |
| [agent.py](agent.py) | Agent : session MCP, découverte des outils, boucle ReAct, trace |
| [smoke.py](smoke.py) | Test de fumée des deux dépendances externes |
| [mcp.json](mcp.json) | Configuration du serveur MCP, format éditeur |
| [tests/test_agent.py](tests/test_agent.py) | Tests des fonctions pures |
| [conftest.py](conftest.py) | Fichier vide : place la racine dans le `sys.path` de pytest |

## Limites connues

- **Communes à arrondissements.** Ne pas interroger Paris ni Lyon sur les points
  de recharge : leurs enregistrements sont répartis entre les codes INSEE
  d'arrondissement et le total obtenu serait faux. Toulouse (`31555`) et
  Bordeaux (`33063`) donnent un résultat fiable.
- **Chiffres mouvants.** La base nationale IRVE est régénérée quotidiennement ;
  les valeurs renvoyées évoluent d'un jour à l'autre.
- **Choix de la source.** Sans le prompt système de `agent.py`, qui impose la
  ressource CSV consolidée la plus récente publiée par data.gouv.fr, l'agent
  hésite entre plusieurs bases IRVE et renvoie un chiffre différent à chaque
  exécution.
- **Dépréciation.** `create_react_agent` est déprécié depuis LangGraph 1.0 au
  profit de `langchain.agents.create_agent`, qui vit dans un paquet non installé
  ici. L'avertissement est masqué dans `agent.py`.

## Documentation

- Conception : [docs/superpowers/specs/2026-08-06-demo-mcp-datagouv-design.md](docs/superpowers/specs/2026-08-06-demo-mcp-datagouv-design.md)
- Plan d'implémentation : [docs/superpowers/plans/2026-08-06-demo-mcp-datagouv.md](docs/superpowers/plans/2026-08-06-demo-mcp-datagouv.md)
</content>
