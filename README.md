# Démo MCP data.gouv.fr

Un agent LangChain branché sur le serveur MCP de data.gouv.fr, pour une
démonstration de 10 minutes.

## Mise en route

```bash
cp .env.example .env    # puis renseigner les valeurs Azure
uv sync
uv run smoke.py         # doit afficher deux lignes [OK]
```

`smoke.py` valide les deux dépendances externes **séparément** : le serveur MCP
d'abord, le modèle Azure ensuite. En cas d'échec, le message indique lequel des
deux maillons a lâché.

Le bloc MCP n'a aucune dépendance : `python3 smoke.py` fonctionne même sans
environnement installé, ce qui permet de diagnostiquer le réseau en premier.

## Utilisation

```bash
# Scénario 1 — la question chiffrée
uv run agent.py "Combien de points de recharge pour véhicules électriques y a-t-il à Toulouse ? Cite ta source."

# Scénario 2 — la découverte d'API
uv run agent.py "Trouve une API publique de géocodage d'adresses sur data.gouv.fr et explique-moi concrètement comment l'appeler."
```

## Configuration MCP

`mcp.json` est la source unique de vérité. Il est au format des éditeurs, et se
copie tel quel dans le client MCP de VS Code, Cursor ou Claude Code :

```json
{
  "mcpServers": {
    "datagouv": { "type": "http", "url": "https://mcp.data.gouv.fr/mcp" }
  }
}
```

Aucune clé, aucune installation. `agent.py` convertit ce format vers celui
attendu par `langchain-mcp-adapters` : le protocole est standardisé, le format
du fichier de configuration ne l'est pas encore.

## Tests

```bash
uv run pytest -q
```

Les fonctions pures sont couvertes par pytest. Les chemins réseau ne le sont
pas : `smoke.py` **est** leur test, en conditions réelles. Simuler le serveur
MCP donnerait une fausse assurance, alors que c'est justement sa disponibilité
réelle qu'on veut vérifier avant de monter sur scène.

## Le jour de la démo

1. `uv run smoke.py` avant de monter sur scène.
2. Relancer les deux scénarios : la base IRVE est régénérée quotidiennement, le
   chiffre de Toulouse aura peut-être changé.
3. En cas de panne réseau, dérouler sur `logs/scenario1.txt` et
   `logs/scenario2.txt`.

Ne pas utiliser Paris ni Lyon comme exemple : leurs points de recharge sont
répartis entre les codes INSEE d'arrondissement, et le chiffre obtenu serait
faux. Toulouse (`31555`) et Bordeaux (`33063`) sont fiables.

## Documentation

- Conception : `docs/superpowers/specs/2026-08-06-demo-mcp-datagouv-design.md`
- Plan d'implémentation : `docs/superpowers/plans/2026-08-06-demo-mcp-datagouv.md`
- Schémas à projeter : `docs/schema-mcp.md`
