# What the Repo - System Diagrams

**How to read this doc**: This document contains Mermaid diagrams that visualize the What the Repo system architecture, data flow, and database schemas. Each diagram focuses on a specific aspect of the system.

## System Context Diagram

Shows the high-level system architecture and external dependencies.

```mermaid
graph TB
    User[👤 User] --> UI[🌐 Web UI]
    UI --> API[🚀 FastAPI App]
    
    API --> Milvus[(🔍 Milvus Vector DB)]
    API --> Supabase[(🗄️ Supabase PostgreSQL)]
    API --> OpenAI[🤖 OpenAI API]
    
    ETL[⚙️ ETL Pipeline] --> GitHub[📦 GitHub API]
    ETL --> Milvus
    ETL --> Supabase
    
    subgraph "External Services"
        GitHub
        OpenAI
    end
    
    subgraph "Data Storage"
        Milvus
        Supabase
    end
    
    subgraph "Application Layer"
        UI
        API
        ETL
    end
```

## Data Flow ETL

Illustrates the complete ETL pipeline from GitHub to analytics.

```mermaid
flowchart TD
    A[GitHub API] --> B[Raw PR Data]
    B --> C[JSON Files]
    C --> D[ETL Processors]
    
    D --> E[PostgreSQL Tables]
    D --> F[LLM Analysis]
    D --> G[Content Embeddings]
    
    F --> H[Risk Scores]
    F --> I[Feature Classification]
    
    G --> J[Milvus Collections]
    H --> E
    I --> E
    
    subgraph "Data Sources"
        A
    end
    
    subgraph "Processing"
        D
        F
        G
    end
    
    subgraph "Storage"
        E
        J
    end
    
    subgraph "Analytics"
        H
        I
    end
```

## Request Routing

Shows how queries are routed to different handlers based on content analysis.

```mermaid
flowchart TD
    A[Natural Language Query] --> B{Router Analysis}
    
    B -->|Direct Patterns| C[Direct Handler]
    B -->|Hybrid Patterns| D[Hybrid Handler]
    B -->|Vector Patterns| E[Vector Handler]
    
    C --> F[Supabase Query]
    D --> G[Time Slice + Semantic]
    E --> H[Vector Search]
    
    F --> I[Structured Results]
    G --> I
    H --> I
    
    I --> J[Response to User]
    
    subgraph "Routing Logic"
        B
    end
    
    subgraph "Handlers"
        C
        D
        E
    end
    
    subgraph "Data Sources"
        F
        G
        H
    end
```

## Sequence Diagram: "What features shipped last two weeks"

Shows the interaction flow for a feature query.

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Web UI
    participant API as FastAPI
    participant R as Router
    participant H as Hybrid Handler
    participant S as Supabase
    participant M as Milvus
    
    U->>UI: "What features shipped last two weeks"
    UI->>API: POST /ask {query, repo_name}
    API->>R: route_query(query)
    R->>R: Parse time: "last two weeks"
    R->>R: Detect hybrid pattern: "features shipped"
    R->>API: {route: "hybrid", object: "features", metric: "list"}
    
    API->>H: hybrid_features(repo, time_range)
    H->>S: Query repo_prs WHERE feature_rule != 'excluded'
    H->>M: Vector search for semantic similarity
    S->>H: PR list with feature classification
    M->>H: Similar PRs with scores
    
    H->>H: Combine and rank results
    H->>API: Structured response with explanations
    API->>UI: JSON response
    UI->>U: Display feature list with risk scores
```

## Sequence Diagram: "File that changed most last week"

Shows the interaction flow for a file analysis query.

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Web UI
    participant API as FastAPI
    participant R as Router
    participant D as Direct Handler
    participant S as Supabase
    participant M as Milvus
    
    U->>UI: "File that changed most last week"
    UI->>API: POST /ask {query, repo_name}
    API->>R: route_query(query)
    R->>R: Parse time: "last week"
    R->>R: Detect direct pattern: "most"
    R->>API: {route: "direct", object: "files", metric: "top"}
    
    API->>D: direct_top_file_by_lines(repo, time_range)
    D->>S: Query author_file_ownership GROUP BY file_id
    D->>M: Search file_changes collection
    S->>D: File ownership data
    M->>D: File change history
    
    D->>D: Aggregate by lines changed
    D->>D: Calculate ownership percentages
    D->>API: Top files with metrics
    API->>UI: JSON response
    UI->>U: Display file ranking with ownership
```

## ERD: Milvus Logical Schema

Shows the structure of Milvus collections.

```mermaid
erDiagram
    PR_INDEX {
        int pr_id PK
        string repo_name
        int pr_number
        string title
        string body
        vector embedding "1536 dimensions"
        int created_at
        boolean is_merged
        float risk_score
        string feature_rule
        int merged_at
        string author
        int additions
        int deletions
        int changed_files
    }
    
    FILE_CHANGES {
        string file_id PK
        string repo_name
        string filename
        vector embedding "1536 dimensions"
        int pr_id FK
        int lines_changed
        float risk_score
        string status
        string language
        int created_at
    }
    
    PR_INDEX ||--o{ FILE_CHANGES : "contains"
```

## ERD: Supabase Tables

Shows the structure of PostgreSQL tables.

```mermaid
erDiagram
    AUTHORS {
        string username PK
        string display_name
        string avatar_url
        timestamp created_at
        timestamp updated_at
    }
    
    AUTHOR_METRICS_DAILY {
        string username FK
        string repo_name
        date day
        int prs_submitted
        int prs_merged
        int lines_changed
        int high_risk_prs
        int features_merged
        timestamp updated_at
    }
    
    AUTHOR_METRICS_WINDOW {
        string username FK
        string repo_name
        int window_days
        date start_date
        date end_date
        int prs_submitted
        int prs_merged
        int high_risk_prs
        float high_risk_rate
        int lines_changed
        int ownership_low_risk_prs
        timestamp updated_at
    }
    
    AUTHOR_PRS_WINDOW {
        string username FK
        string repo_name
        int window_days
        date start_date
        date end_date
        int pr_number
        string title
        string pr_summary
        timestamp merged_at
        float risk_score
        boolean high_risk
        string feature_rule
        float feature_confidence
        timestamp updated_at
    }
    
    AUTHOR_FILE_OWNERSHIP {
        string username FK
        string repo_name
        int window_days
        date start_date
        date end_date
        string file_id
        string file_path
        float ownership_pct
        int author_lines
        int total_lines
        timestamp last_touched
        timestamp updated_at
    }
    
    REPO_PRS {
        string repo_name
        int pr_number
        string title
        string pr_summary
        string author
        timestamp created_at
        timestamp merged_at
        boolean is_merged
        int additions
        int deletions
        int changed_files
        json labels_full
        string feature_rule
        float feature_confidence
        float risk_score
        boolean high_risk
        json risk_reasons
        json top_risky_files
        timestamp updated_at
    }
    
    AUTHORS ||--o{ AUTHOR_METRICS_DAILY : "has"
    AUTHORS ||--o{ AUTHOR_METRICS_WINDOW : "has"
    AUTHORS ||--o{ AUTHOR_PRS_WINDOW : "has"
    AUTHORS ||--o{ AUTHOR_FILE_OWNERSHIP : "has"
```

## Data Processing Flow

Shows how data moves through the system.

```mermaid
flowchart LR
    A[GitHub PRs] --> B[Raw JSON]
    B --> C[ETL Processing]
    
    C --> D[Daily Metrics]
    C --> E[Window Metrics]
    C --> F[PR Details]
    C --> G[File Ownership]
    C --> H[Risk Assessment]
    C --> I[Feature Classification]
    
    D --> J[Supabase Tables]
    E --> J
    F --> J
    G --> J
    
    H --> K[Risk Scores]
    I --> L[Feature Rules]
    
    K --> M[Milvus Collections]
    L --> M
    
    subgraph "Input"
        A
    end
    
    subgraph "Processing"
        C
        H
        I
    end
    
    subgraph "Analytics"
        D
        E
        F
        G
    end
    
    subgraph "Storage"
        J
        M
    end
```

## Query Processing Flow

Shows how different query types are processed.

```mermaid
flowchart TD
    A[User Query] --> B{Query Type}
    
    B -->|Direct| C[Direct Handler]
    B -->|Hybrid| D[Hybrid Handler]
    B -->|Vector| E[Vector Handler]
    
    C --> F[Supabase Query]
    D --> G[Time Slice + Vector]
    E --> H[Semantic Search]
    
    F --> I[Structured Data]
    G --> I
    H --> I
    
    I --> J[Response Formatting]
    J --> K[User Response]
    
    subgraph "Query Analysis"
        B
    end
    
    subgraph "Processing"
        C
        D
        E
    end
    
    subgraph "Data Retrieval"
        F
        G
        H
    end
    
    subgraph "Response"
        I
        J
        K
    end
```
