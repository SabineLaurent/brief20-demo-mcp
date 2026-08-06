# Démo MCP data.gouv.fr avec un agent LangChain — conception

Date : 2026-08-06

## 1. Objectif

Préparer une démonstration de 10 minutes, en direct devant une promotion de formation
IA agentique, montrant l'usage d'un serveur MCP par un agent LangChain.

La démonstration répond à la consigne pédagogique suivante : trouver un serveur MCP
simple à comprendre et actif, le configurer manuellement, l'exploiter via un éditeur
de code, et préparer une petite démo.

## 2. Contraintes

| Contrainte | Valeur |
|---|---|
| Durée | 10 minutes, en direct |
| Objectif pédagogique | Faire comprendre le protocole d'abord, l'effet ensuite |
| LLM | Azure AI Foundry, déploiement `gpt-5.6-luna`, clé sans `api_version` |
| Éditeur | VS Code 1.131 |
| Langage | Python 3.12, géré par `uv` |
| Répertoire | `/Users/sabine/REPO_GIT/demo-mcp` |

Contrainte matérielle constatée : ni `github.copilot` ni `github.copilot-chat` ne sont
installés dans VS Code. Le client MCP de l'éditeur sera donc l'extension
`anthropic.claude-code`, déjà présente.

## 3. Choix du serveur MCP

Serveur retenu : **MCP data.gouv.fr**, `https://mcp.data.gouv.fr/mcp`.

### 3.1 Vérifications effectuées le 2026-08-06

Toutes les mesures ci-dessous proviennent d'appels réels au serveur, pas de
documentation.

| Vérification | Résultat |
|---|---|
| Handshake `initialize` | `data.gouv.fr MCP server` v1.28.1, protocole `2025-06-18` |
| Transport | HTTP streamable uniquement (ni stdio, ni SSE) |
| Session | Aucun en-tête `mcp-session-id` renvoyé : serveur *stateless* |
| Authentification | Aucune. Lecture seule, aucune clé API |
| `tools/list` | 10 outils |
| Latence mesurée | 0,43 s à 2,06 s selon l'outil |
| Format des réponses | Texte formaté lisible, ~1 600 tokens pour une recherche |

Les 10 outils : `search_datasets`, `search_organizations`, `search_dataservices`,
`get_dataservice_info`, `get_dataservice_openapi_spec`, `query_resource_data`,
`get_dataset_info`, `list_dataset_resources`, `get_resource_info`, `get_metrics`.

### 3.2 Justification

1. **Coût d'entrée nul.** Aucune clé, aucune installation, aucun `npx`, aucun Docker.
   La configuration tient en quatre lignes de JSON.
2. **Surface lisible.** Dix outils aux noms explicites, projetables à l'écran sans
   défilement.
3. **Les descriptions d'outils portent le mode d'emploi.** Celle de `search_datasets`
   contient : « Typical workflow: search_datasets → list_dataset_resources →
   query_resource_data ». C'est le support du message pédagogique central de la démo :
   un serveur MCP fournit les outils *et* leur notice à destination du modèle.
4. **Transport représentatif.** HTTP streamable distant, plus proche de l'écosystème
   actuel que du stdio local.
5. **Sujet accessible.** Données publiques françaises, réponses vérifiables en direct
   sur data.gouv.fr.

### 3.3 Alternatives écartées

| Alternative | Motif du rejet |
|---|---|
| Playwright MCP | ~25 outils, réponses très verbeuses (arbres d'accessibilité), 4 à 6 tours d'agent à 10-20 s, ~150 Mo de Chromium à installer, non déterminisme lié au site cible. Incompatible avec un créneau de 10 minutes en direct. Le spectacle masque en outre le concept. |
| Filesystem MCP | Sûr et lisible, mais sans données réelles ni effet mémorable. |
| Context7 | Deux outils seulement, très simple, mais périmètre trop étroit pour porter deux scénarios. |
| GitHub MCP | ~90 outils et un jeton d'accès personnel requis. Surface trop large. |

### 3.4 Limites assumées

- data.gouv.fr annonce ce serveur comme **expérimental**. Ce point sera dit à la
  promotion : il illustre la jeunesse de l'écosystème MCP.
- Le serveur est distant : la démo dépend du réseau de la salle. Voir §8.

## 4. Architecture

```
demo-mcp/
├── mcp.json         # la configuration MCP, artefact unique et portable
├── .env.example     # variables Azure attendues (.env réel non versionné)
├── pyproject.toml   # dépendances, gérées par uv
├── smoke.py         # test de fumée : valide le LLM et le serveur séparément
├── agent.py         # l'agent LangChain, prompt passé en argument CLI
└── logs/            # sorties pré-enregistrées, filet de sécurité (non versionné)
```

Dépendances : `langchain-mcp-adapters`, `langgraph`, `langchain-openai`,
`python-dotenv`.

### 4.1 Responsabilités

- **`mcp.json`** — source unique de vérité de la configuration. Lu par `agent.py`,
  et copiable tel quel dans le client MCP de l'éditeur.
- **`smoke.py`** — dérisqueur. Teste les deux dépendances externes séparément, afin
  qu'un échec désigne le maillon fautif.
- **`agent.py`** — client MCP LangChain. Découvre les outils, construit un agent
  ReAct, exécute le prompt, et **affiche explicitement chaque appel d'outil**.

### 4.2 Flux d'exécution

```
question → LLM Azure décide → search_datasets(query=…)
                                 ↓ HTTPS POST mcp.data.gouv.fr/mcp
                              ← ~6 000 caractères, ~1 s
         → LLM relit         → list_dataset_resources(dataset_id=…)
         → LLM relit         → query_resource_data(resource_id=…, filter_column=…)
         → réponse finale + URL data.gouv.fr vérifiable
```

## 5. Fichiers

### 5.1 `mcp.json`

```json
{
  "mcpServers": {
    "datagouv": { "type": "http", "url": "https://mcp.data.gouv.fr/mcp" }
  }
}
```

Ce format est celui des éditeurs. `langchain-mcp-adapters` attend une structure
différente : `{"datagouv": {"url": …, "transport": "streamable_http"}}`. `agent.py`
effectue la conversion en trois lignes.

Cet écart est conservé volontairement : il est mentionné en démo pour montrer que le
protocole est standardisé alors que le format du fichier de configuration ne l'est
pas encore.

### 5.2 `.env.example`

Variables attendues pour Azure AI Foundry sans `api_version` :

```
AZURE_BASE_URL=https://<ressource>.openai.azure.com/openai/v1/
AZURE_API_KEY=<clé>
AZURE_DEPLOYMENT=gpt-5.6-luna
```

Azure AI Foundry expose une API v1 compatible OpenAI qui ne requiert pas le paramètre
`api-version`. L'agent utilise donc `ChatOpenAI` avec `base_url`, et non
`AzureChatOpenAI`. Le nom du **déploiement** est passé comme `model`.

Si le test de fumée révèle que ce chemin ne fonctionne pas sur la ressource Azure
utilisée, le repli est `AzureChatOpenAI` avec un `api_version` explicite.

### 5.3 `smoke.py`

Deux blocs indépendants, exit code 1 si l'un échoue.

**Bloc 1 — serveur MCP**, en `urllib` pur, sans aucune dépendance :
`initialize` puis `tools/list`. Affiche le nom et la version du serveur, et le
nombre d'outils. Attendu : 10.

**Bloc 2 — LLM Azure** : instancie le modèle, lui associe un outil jouet (une
addition), et vérifie que le modèle **l'appelle effectivement**. C'est le seul test
qui prouve que le déploiement `gpt-5.6-luna` gère le *tool calling*.

### 5.4 `agent.py`

Environ 50 lignes.

```python
import asyncio, json, os, sys
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

SERVERS = {
    name: {"url": cfg["url"], "transport": "streamable_http"}
    for name, cfg in json.load(open("mcp.json"))["mcpServers"].items()
}

SYSTEM = (
    "Tu réponds en français, de façon concise. "
    "Tu utilises exclusivement les outils data.gouv.fr pour trouver tes chiffres. "
    "Tu cites toujours l'URL data.gouv.fr de la source utilisée."
)

async def main(question: str) -> None:
    tools = await MultiServerMCPClient(SERVERS).get_tools()
    print(f"→ {len(tools)} outils découverts : {', '.join(t.name for t in tools)}\n")

    model = ChatOpenAI(
        model=os.environ["AZURE_DEPLOYMENT"],
        base_url=os.environ["AZURE_BASE_URL"],
        api_key=os.environ["AZURE_API_KEY"],
        temperature=0,
    )
    agent = create_react_agent(model=model, tools=tools, prompt=SYSTEM)

    async for step in agent.astream(
        {"messages": [("user", question)]}, stream_mode="updates"
    ):
        ...  # affichage : nom de l'outil, arguments, taille et durée de la réponse

asyncio.run(main(sys.argv[1]))
```

Format d'affichage visé, une ligne par événement :

```
→ 10 outils découverts : search_datasets, search_organizations, …

🔧 search_datasets(query='bornes recharge véhicules électriques')
   ← 6 243 caractères en 1,1 s
🔧 list_dataset_resources(dataset_id='5448d3e0c751df01f85d0572')
   ← 892 caractères en 0,5 s
🔧 query_resource_data(resource_id='eb76d20a…', filter_column='code_insee_commune',
                       filter_value='31555')
   ← 7 029 caractères en 0,8 s

💬 Il y a 1 099 points de recharge à Toulouse.
   Source : https://www.data.gouv.fr/datasets/base-nationale-des-irve-…
```

Cet affichage n'est pas cosmétique : sans lui, l'écran ne montre qu'un curseur pendant
une vingtaine de secondes et le public ne voit pas le protocole à l'œuvre.

### 5.5 Décisions de conception

1. **`temperature=0`** — la démonstration doit être reproductible d'une exécution à
   l'autre.
2. **Le prompt système ne décrit pas l'enchaînement des outils**, puisque les
   descriptions du serveur le font déjà. C'est ce que la démo cherche à prouver, et
   c'est vérifié : l'agent enchaîne correctement `search_datasets` →
   `list_dataset_resources` → `query_resource_data` sans qu'on le lui dise.

   **En revanche il tranche les ambiguïtés de source.** Constat à l'exécution : sans
   ce cadrage, l'agent hésitait entre plusieurs bases nationales IRVE et plusieurs
   ressources, et renvoyait 1 099, puis 944, puis 1 212 selon les exécutions. Le
   prompt précise donc de retenir le jeu publié par data.gouv.fr, la ressource
   consolidée la plus récente, un filtre `exact` sur `code_insee_commune`, et
   d'employer deux ou trois mots-clés sans nom de commune dans les recherches — la
   recherche combinant les termes par un ET logique. C'est le rôle normal d'un prompt
   système en production, et il n'est pas projeté pendant la démonstration : la
   question affichée reste naturelle.
3. **Le prompt passe en argument de ligne de commande.** Un seul fichier sert les deux
   scénarios, sans changement de fenêtre en direct.

## 6. Déroulé de la démonstration

| Temps | Séquence | Contenu |
|---|---|---|
| 0:00–0:45 | Introduction | Un schéma : sans MCP, N agents × M outils = N×M intégrations ; avec MCP, N+M |
| 0:45–2:15 | Configuration manuelle | Saisie de `mcp.json` à l'écran, `/mcp` affiche les 10 outils, lecture de la description de `search_datasets` |
| 2:15–3:00 | Avant | La même question posée au modèle sans MCP : il invente un chiffre |
| 3:00–5:45 | Scénario 1 | L'agent enchaîne trois outils et répond, sourcé |
| 5:45–8:00 | Scénario 2 | L'agent découvre une API publique et sa spécification OpenAPI |
| 8:00–10:00 | Conclusion | Trois messages, puis questions |

### 6.1 Scénario 1 — la question chiffrée

Prompt exact :

```
Combien de points de recharge pour véhicules électriques
y a-t-il à Toulouse ? Cite ta source.
```

Chaîne attendue : `search_datasets` → `list_dataset_resources` →
`query_resource_data(filter_column="code_insee_commune", filter_value="31555")`.

Jeu de données cible : **Base nationale des IRVE**,
dataset `5448d3e0c751df01f85d0572`, ressource `eb76d20a-8501-400e-b336-d85724de5435`.

Mesures relevées le 2026-08-06 : 233 972 lignes, fichier de 156,9 Mo, ressource
régénérée le matin même, réponse en 0,81 s.

Argument à énoncer à voix haute : le fichier fait 157 Mo et n'a jamais été téléchargé.

### 6.2 Scénario 2 — la découverte d'API

Prompt exact :

```
Trouve une API publique de géocodage d'adresses sur data.gouv.fr
et explique-moi concrètement comment l'appeler.
```

Chaîne attendue : `search_dataservices` → `get_dataservice_openapi_spec`.

Résultat vérifié : API Adresse (Base Adresse Nationale), dataservice
`672cf67802ef6b1be63b8975`, spécification résumée de 3 352 caractères en 0,81 s,
14 endpoints dont `GET /search` avec ses paramètres `q`, `limit`, `postcode`.

### 6.3 Conclusion — les trois messages

1. MCP est un protocole, pas une bibliothèque. Le même `mcp.json` fonctionne dans
   Claude Code, Cursor, VS Code ou un agent maison.
2. La configuration tient en quatre lignes. Le coût d'entrée est quasi nul.
3. Les données ouvertes sont imparfaites : la base IRVE annonce une borne de
   160 000 kW. MCP donne l'accès, pas le discernement.

## 7. Pièges identifiés et parades

Ces pièges ont été découverts en interrogeant réellement le serveur.

| Piège | Constat | Parade |
|---|---|---|
| Ressources hors API Tabular | `query_resource_data` a refusé la ressource du fichier des prénoms Insee, hébergée hors data.gouv.fr | Ressource cible pré-identifiée et figée (§6.1) |
| Communes à arrondissements | Paris `75056` retourne 54 lignes, alors que le seul 1er arrondissement `75101` en retourne 88. Lyon `69123` : 23 | N'utiliser que des communes sans arrondissements. Toulouse `31555` : 1 099. Bordeaux `33063` : 1 060 |
| Points de charge et non stations | Le schéma IRVE comporte une ligne par point de charge | Formuler la question et la réponse en « points de recharge » |
| Valeurs aberrantes | `puissance_nominale` maximale à 160 000 | Ne pas fonder le scénario sur un tri par puissance. Garder le fait comme illustration en conclusion |
| Fraîcheur quotidienne | La ressource est régénérée chaque jour | Ne pas figer le chiffre attendu dans les tests. Relancer les vérifications le matin de la démo |
| Deux bases nationales concurrentes | Le jeu historique de data.gouv.fr (créé en 2014) et un jeu `[BETA]` du Point d'Accès National (créé en 2025) sont tous deux actifs et mis à jour quotidiennement, avec des périmètres différents | Trancher dans le prompt système, pas dans la question projetée |
| Recherche en ET logique | `search_datasets("points recharge véhicules électriques Toulouse")` renvoie **zéro résultat**, ce qui déclenchait trois recherches de rattrapage | Le prompt système impose deux ou trois mots-clés, sans nom de commune |
| Une connexion HTTP par appel d'outil | `MultiServerMCPClient.get_tools()` ouvre une session neuve à chaque appel — sa docstring le dit — d'où des `httpx.ConnectTimeout` intermittents (1 échec sur 8 exécutions) | Session persistante via `client.session()` + `load_mcp_tools()`. Supprime les timeouts et réduit la durée d'environ 40 % |

## 8. Critères de succès

La démonstration est prête quand les quatre conditions suivantes sont vraies.

| # | Vérification | Critère |
|---|---|---|
| 1 | `uv run smoke.py` | exit 0 : serveur MCP à 10 outils **et** *tool calling* confirmé sur le déploiement |
| 2 | Scénario 1 | 5 appels d'outils au maximum, moins de 30 s, un nombre cohérent (ordre de grandeur d'un millier) **et** une URL data.gouv.fr |
| 3 | Scénario 2 | l'agent nomme un endpoint réel et au moins deux de ses paramètres, moins de 30 s |
| 4 | Stabilité | trois exécutions consécutives de chaque scénario produisent la même chaîne d'outils |

Le critère 4 est déterminant : un scénario qui réussit une fois sur trois n'est pas
une démonstration.

### 8.1 Résultats de validation, 2026-08-06

| Critère | Mesure | Verdict |
|---|---|---|
| 1 — test de fumée | deux `[OK]`, exit 0. Tool calling confirmé sur `gpt-5.6-luna` par le chemin `ChatOpenAI` + `base_url`, sans `api_version` : le repli `AzureChatOpenAI` n'est pas nécessaire | ✅ |
| 2 — scénario 1 | 4 exécutions : 4 à 5 appels, 13 à 18 s, **1 099** et l'URL du jeu à chaque fois | ✅ |
| 3 — scénario 2 | 3 exécutions : 3 appels, 16 s, endpoint `GET /search` de l'API Adresse avec ses paramètres | ✅ |
| 4 — stabilité | scénario 1 : 4/4 identiques. Scénario 2 : 3/3 identiques, même séquence d'outils | ✅ |

Vérification complémentaire : la commande `curl` produite par l'agent au scénario 2 a
été exécutée et fonctionne (score 0,98, coordonnées correctes). Elle peut être lancée
en direct comme prolongement du scénario.

## 9. Plan de repli

À produire en préparation : `logs/scenario1.txt` et `logs/scenario2.txt`, capturés la
veille avec la sortie complète, ainsi qu'un prompt de repli pour le scénario 1 nommant
directement la « Base nationale des IRVE », ce qui économise un appel d'outil.

| Défaillance | Détection | Repli |
|---|---|---|
| Réseau de la salle | `smoke.py` bloc 1 échoue | Dérouler sur les logs pré-enregistrés |
| Azure indisponible ou quota atteint | `smoke.py` bloc 2 échoue | Logs pré-enregistrés ; le temps 1 reste jouable |
| Serveur data.gouv.fr lent | latence visible | Le commenter : le service est annoncé expérimental |
| Agent qui s'égare | plus de 6 appels d'outils | `Ctrl-C`, relancer avec le prompt de repli |
| Chiffre différent des répétitions | — | L'expliquer : données du jour |

## 10. Ordre de construction

1. `pyproject.toml` et `.env.example`
2. `mcp.json`
3. **`smoke.py`** — avant tout code d'agent, pour valider les deux dépendances
   externes et lever l'incertitude sur le *tool calling* du déploiement Azure
4. `agent.py`, d'abord la découverte des outils, puis l'affichage, puis la boucle
5. Validation des critères 2, 3 et 4
6. Capture des logs de repli
