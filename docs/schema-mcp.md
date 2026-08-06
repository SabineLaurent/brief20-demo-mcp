# Schémas d'introduction — MCP

Supports à projeter pendant les 45 premières secondes de la démonstration.

## 1. Le problème : N × M intégrations

Chaque client doit écrire un connecteur pour chaque source de données.
Trois clients et trois sources, c'est déjà **neuf connecteurs** à écrire et à maintenir.

```mermaid
graph LR
    A1[Agent LangChain]
    A2[Cursor]
    A3[Claude Code]

    S1[(data.gouv.fr)]
    S2[(GitHub)]
    S3[(Fichiers locaux)]

    A1 --> S1
    A1 --> S2
    A1 --> S3
    A2 --> S1
    A2 --> S2
    A2 --> S3
    A3 --> S1
    A3 --> S2
    A3 --> S3
```

## 2. La solution : N + M

Chaque client parle **un seul protocole**. Chaque source expose **un seul serveur**.
Trois clients et trois sources : **six branchements**, et chaque nouveau client
bénéficie immédiatement de toutes les sources existantes.

```mermaid
graph LR
    A1[Agent LangChain]
    A2[Cursor]
    A3[Claude Code]

    MCP{{Protocole MCP}}

    M1[Serveur MCP<br/>data.gouv.fr]
    M2[Serveur MCP<br/>GitHub]
    M3[Serveur MCP<br/>Filesystem]

    S1[(data.gouv.fr)]
    S2[(GitHub)]
    S3[(Fichiers locaux)]

    A1 --> MCP
    A2 --> MCP
    A3 --> MCP

    MCP --> M1
    MCP --> M2
    MCP --> M3

    M1 --> S1
    M2 --> S2
    M3 --> S3
```

## 3. Ce qui se passe réellement pendant la démo

Le serveur n'expose pas seulement des outils : il expose aussi **leur mode d'emploi**,
que le modèle lit avant de décider.

```mermaid
sequenceDiagram
    autonumber
    participant U as Utilisateur
    participant A as agent.py
    participant L as LLM Azure
    participant S as mcp.data.gouv.fr

    Note over A,S: Découverte, une seule fois au démarrage
    A->>S: initialize
    S-->>A: data.gouv.fr MCP server v1.28.1
    A->>S: tools/list
    S-->>A: 10 outils, avec leurs descriptions

    Note over U,S: Exécution
    U->>A: Combien de points de recharge à Toulouse ?
    A->>L: question + les 10 outils

    L-->>A: appelle search_datasets
    A->>S: tools/call search_datasets
    S-->>A: 6 243 caractères en 1,1 s

    L-->>A: appelle list_dataset_resources
    A->>S: tools/call list_dataset_resources
    S-->>A: 892 caractères en 0,5 s

    L-->>A: appelle query_resource_data
    A->>S: tools/call query_resource_data
    S-->>A: 7 029 caractères en 0,8 s

    L-->>A: réponse finale
    A-->>U: le chiffre, et l'URL data.gouv.fr de la source
```

## Le chiffre à retenir

La ressource interrogée compte **233 972 lignes** pour **157 Mo**.
Elle n'est **jamais téléchargée** : le serveur MCP interroge l'API Tabular
et ne renvoie que ce qui est demandé, en moins d'une seconde.
