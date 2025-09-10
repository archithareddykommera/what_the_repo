# What the Repo - Database Schema

**How to read this doc**: This document provides detailed field definitions for all database tables and collections, including data types, constraints, and example data.

## Milvus Collections

### pr_index_what_the_repo

Primary collection for PR data with vector embeddings.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `pr_id` | `int64` | Primary key, unique PR identifier | `12345` |
| `repo_name` | `varchar(255)` | Repository name | `"my-app"` |
| `pr_number` | `int64` | GitHub PR number | `789` |
| `title` | `varchar(1000)` | PR title | `"Add user authentication"` |
| `body` | `varchar(10000)` | PR description/body | `"This PR implements..."` |
| `embedding` | `vector(1536)` | OpenAI embedding vector | `[0.1, -0.2, 0.3, ...]` |
| `created_at` | `int64` | Unix timestamp of PR creation | `1705752000` |
| `merged_at` | `int64` | Unix timestamp of PR merge | `1705838400` |
| `is_merged` | `bool` | Whether PR was merged | `true` |
| `author` | `varchar(255)` | GitHub username of author | `"john-doe"` |
| `additions` | `int64` | Lines added | `450` |
| `deletions` | `int64` | Lines deleted | `23` |
| `changed_files` | `int64` | Number of files changed | `12` |
| `risk_score` | `float` | Aggregated risk score (0-10) | `6.8` |
| `feature_rule` | `varchar(50)` | Feature classification rule | `"label-allow"` |

**Index Configuration**:
- **Index Type**: IVF_FLAT
- **Metric Type**: L2
- **nlist**: 1024
- **Search Parameters**: ef=64

**Example Record**:
```json
{
  "pr_id": 12345,
  "repo_name": "my-app",
  "pr_number": 789,
  "title": "Add user authentication",
  "body": "This PR implements OAuth2 authentication...",
  "embedding": [0.1, -0.2, 0.3, ...],
  "created_at": 1705752000,
  "merged_at": 1705838400,
  "is_merged": true,
  "author": "john-doe",
  "additions": 450,
  "deletions": 23,
  "changed_files": 12,
  "risk_score": 6.8,
  "feature_rule": "label-allow"
}
```

### file_changes_what_the_repo

Collection for file-level changes with vector embeddings.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `file_id` | `varchar(500)` | Primary key, unique file identifier | `"my-app:src/auth/login.py"` |
| `repo_name` | `varchar(255)` | Repository name | `"my-app"` |
| `filename` | `varchar(500)` | File path | `"src/auth/login.py"` |
| `embedding` | `vector(1536)` | OpenAI embedding vector | `[0.1, -0.2, 0.3, ...]` |
| `pr_id` | `int64` | Associated PR ID | `12345` |
| `lines_changed` | `int64` | Lines added + deleted | `320` |
| `risk_score` | `float` | File-level risk score (0-10) | `7.2` |
| `status` | `varchar(50)` | File change status | `"modified"` |
| `language` | `varchar(50)` | Programming language | `"python"` |
| `created_at` | `int64` | Unix timestamp | `1705752000` |

**Index Configuration**:
- **Index Type**: IVF_FLAT
- **Metric Type**: L2
- **nlist**: 1024
- **Search Parameters**: ef=64

**Example Record**:
```json
{
  "file_id": "my-app:src/auth/login.py",
  "repo_name": "my-app",
  "filename": "src/auth/login.py",
  "embedding": [0.1, -0.2, 0.3, ...],
  "pr_id": 12345,
  "lines_changed": 320,
  "risk_score": 7.2,
  "status": "modified",
  "language": "python",
  "created_at": 1705752000
}
```

## Supabase Tables

### authors

Engineer/author information.

| Field | Type | Constraints | Description | Example |
|-------|------|-------------|-------------|---------|
| `username` | `text` | PRIMARY KEY | GitHub username | `"john-doe"` |
| `display_name` | `text` | NOT NULL | Display name | `"John Doe"` |
| `avatar_url` | `text` | NOT NULL | GitHub avatar URL | `"https://github.com/john-doe.png"` |
| `created_at` | `timestamptz` | DEFAULT now() | Record creation time | `2024-01-20T16:45:00Z` |
| `updated_at` | `timestamptz` | DEFAULT now() | Last update time | `2024-01-20T16:45:00Z` |

**Indexes**:
- Primary key on `username`

**Example Record**:
```json
{
  "username": "john-doe",
  "display_name": "John Doe",
  "avatar_url": "https://github.com/john-doe.png",
  "created_at": "2024-01-20T16:45:00Z",
  "updated_at": "2024-01-20T16:45:00Z"
}
```

### author_metrics_daily

Daily metrics per author per repository.

| Field | Type | Constraints | Description | Example |
|-------|------|-------------|-------------|---------|
| `username` | `text` | FOREIGN KEY | Author username | `"john-doe"` |
| `repo_name` | `text` | NOT NULL | Repository name | `"my-app"` |
| `day` | `date` | NOT NULL | Date | `2024-01-20` |
| `prs_submitted` | `int` | DEFAULT 0 | PRs submitted | `3` |
| `prs_merged` | `int` | DEFAULT 0 | PRs merged | `2` |
| `lines_changed` | `int` | DEFAULT 0 | Lines added/deleted | `1250` |
| `high_risk_prs` | `int` | DEFAULT 0 | High risk PRs | `1` |
| `features_merged` | `int` | DEFAULT 0 | Feature PRs merged | `1` |
| `updated_at` | `timestamptz` | DEFAULT now() | Last update time | `2024-01-20T16:45:00Z` |

**Indexes**:
- Primary key on `(username, repo_name, day)`
- Foreign key to `authors(username)`

**Example Record**:
```json
{
  "username": "john-doe",
  "repo_name": "my-app",
  "day": "2024-01-20",
  "prs_submitted": 3,
  "prs_merged": 2,
  "lines_changed": 1250,
  "high_risk_prs": 1,
  "features_merged": 1,
  "updated_at": "2024-01-20T16:45:00Z"
}
```

### author_metrics_window

Windowed metrics per author per repository.

| Field | Type | Constraints | Description | Example |
|-------|------|-------------|-------------|---------|
| `username` | `text` | FOREIGN KEY | Author username | `"john-doe"` |
| `repo_name` | `text` | NOT NULL | Repository name | `"my-app"` |
| `window_days` | `int` | NOT NULL | Window size (7,15,30,60,90,999) | `30` |
| `start_date` | `date` | NOT NULL | Window start date | `2023-12-21` |
| `end_date` | `date` | NOT NULL | Window end date | `2024-01-20` |
| `prs_submitted` | `int` | DEFAULT 0 | Total PRs submitted | `25` |
| `prs_merged` | `int` | DEFAULT 0 | Total PRs merged | `22` |
| `high_risk_prs` | `int` | DEFAULT 0 | High risk PRs | `3` |
| `high_risk_rate` | `numeric` | DEFAULT 0 | High risk rate (%) | `13.6` |
| `lines_changed` | `int` | DEFAULT 0 | Total lines changed | `15420` |
| `ownership_low_risk_prs` | `int` | DEFAULT 0 | Low risk ownership PRs | `0` |
| `updated_at` | `timestamptz` | DEFAULT now() | Last update time | `2024-01-20T16:45:00Z` |

**Indexes**:
- Primary key on `(username, repo_name, window_days, start_date, end_date)`
- Foreign key to `authors(username)`

**Example Record**:
```json
{
  "username": "john-doe",
  "repo_name": "my-app",
  "window_days": 30,
  "start_date": "2023-12-21",
  "end_date": "2024-01-20",
  "prs_submitted": 25,
  "prs_merged": 22,
  "high_risk_prs": 3,
  "high_risk_rate": 13.6,
  "lines_changed": 15420,
  "ownership_low_risk_prs": 0,
  "updated_at": "2024-01-20T16:45:00Z"
}
```

### author_prs_window

PR details per author per window.

| Field | Type | Constraints | Description | Example |
|-------|------|-------------|-------------|---------|
| `username` | `text` | FOREIGN KEY | Author username | `"john-doe"` |
| `repo_name` | `text` | NOT NULL | Repository name | `"my-app"` |
| `window_days` | `int` | NOT NULL | Window size | `30` |
| `start_date` | `date` | NOT NULL | Window start date | `2023-12-21` |
| `end_date` | `date` | NOT NULL | Window end date | `2024-01-20` |
| `pr_number` | `int` | NOT NULL | GitHub PR number | `789` |
| `title` | `text` | NOT NULL | PR title | `"Add user authentication"` |
| `pr_summary` | `text` | | PR description | `"This PR implements..."` |
| `merged_at` | `timestamptz` | | Merge timestamp | `2024-01-16T14:20:00Z` |
| `risk_score` | `float` | DEFAULT 0 | Risk score | `6.8` |
| `high_risk` | `bool` | DEFAULT false | High risk flag | `false` |
| `feature_rule` | `text` | | Feature classification | `"label-allow"` |
| `feature_confidence` | `float` | DEFAULT 0 | Feature confidence | `0.9` |
| `updated_at` | `timestamptz` | DEFAULT now() | Last update time | `2024-01-20T16:45:00Z` |

**Indexes**:
- Primary key on `(username, repo_name, window_days, start_date, end_date, pr_number)`
- Foreign key to `authors(username)`

**Example Record**:
```json
{
  "username": "john-doe",
  "repo_name": "my-app",
  "window_days": 30,
  "start_date": "2023-12-21",
  "end_date": "2024-01-20",
  "pr_number": 789,
  "title": "Add user authentication",
  "pr_summary": "This PR implements OAuth2 authentication...",
  "merged_at": "2024-01-16T14:20:00Z",
  "risk_score": 6.8,
  "high_risk": false,
  "feature_rule": "label-allow",
  "feature_confidence": 0.9,
  "updated_at": "2024-01-20T16:45:00Z"
}
```

### author_file_ownership

File ownership percentages per author per window.

| Field | Type | Constraints | Description | Example |
|-------|------|-------------|-------------|---------|
| `username` | `text` | FOREIGN KEY | Author username | `"john-doe"` |
| `repo_name` | `text` | NOT NULL | Repository name | `"my-app"` |
| `window_days` | `int` | NOT NULL | Window size | `30` |
| `start_date` | `date` | NOT NULL | Window start date | `2023-12-21` |
| `end_date` | `date` | NOT NULL | Window end date | `2024-01-20` |
| `file_id` | `text` | NOT NULL | Unique file identifier | `"my-app:src/auth/login.py"` |
| `file_path` | `text` | NOT NULL | File path | `"src/auth/login.py"` |
| `ownership_pct` | `float` | DEFAULT 0 | Ownership percentage | `85.2` |
| `author_lines` | `int` | DEFAULT 0 | Lines by this author | `1250` |
| `total_lines` | `int` | DEFAULT 0 | Total lines in file | `1468` |
| `last_touched` | `timestamptz` | | Last modification time | `2024-01-20T16:45:00Z` |
| `updated_at` | `timestamptz` | DEFAULT now() | Last update time | `2024-01-20T16:45:00Z` |

**Indexes**:
- Primary key on `(username, repo_name, window_days, start_date, end_date, file_id)`
- Foreign key to `authors(username)`

**Example Record**:
```json
{
  "username": "john-doe",
  "repo_name": "my-app",
  "window_days": 30,
  "start_date": "2023-12-21",
  "end_date": "2024-01-20",
  "file_id": "my-app:src/auth/login.py",
  "file_path": "src/auth/login.py",
  "ownership_pct": 85.2,
  "author_lines": 1250,
  "total_lines": 1468,
  "last_touched": "2024-01-20T16:45:00Z",
  "updated_at": "2024-01-20T16:45:00Z"
}
```

### repo_prs

PR analytics with feature classification.

| Field | Type | Constraints | Description | Example |
|-------|------|-------------|-------------|---------|
| `repo_name` | `text` | NOT NULL | Repository name | `"my-app"` |
| `pr_number` | `int` | NOT NULL | GitHub PR number | `789` |
| `title` | `text` | NOT NULL | PR title | `"Add user authentication"` |
| `pr_summary` | `text` | | PR description | `"This PR implements..."` |
| `author` | `text` | NOT NULL | Author username | `"john-doe"` |
| `created_at` | `timestamptz` | NOT NULL | Creation timestamp | `2024-01-15T10:30:00Z` |
| `merged_at` | `timestamptz` | | Merge timestamp | `2024-01-16T14:20:00Z` |
| `is_merged` | `bool` | DEFAULT false | Merge status | `true` |
| `additions` | `int` | DEFAULT 0 | Lines added | `450` |
| `deletions` | `int` | DEFAULT 0 | Lines deleted | `23` |
| `changed_files` | `int` | DEFAULT 0 | Files changed | `12` |
| `labels_full` | `jsonb` | | Full labels array | `["feature", "high-risk"]` |
| `feature_rule` | `text` | | Feature classification | `"label-allow"` |
| `feature_confidence` | `float` | DEFAULT 0 | Feature confidence | `0.9` |
| `risk_score` | `float` | DEFAULT 0 | Risk score | `6.8` |
| `high_risk` | `bool` | DEFAULT false | High risk flag | `false` |
| `risk_reasons` | `jsonb` | | Risk reasons array | `["auth", "external-api"]` |
| `top_risky_files` | `jsonb` | | Top risky files array | `[{"file": "login.py", "risk": 7.2}]` |
| `updated_at` | `timestamptz` | DEFAULT now() | Last update time | `2024-01-20T16:45:00Z` |

**Indexes**:
- Primary key on `(repo_name, pr_number)`

**Example Record**:
```json
{
  "repo_name": "my-app",
  "pr_number": 789,
  "title": "Add user authentication",
  "pr_summary": "This PR implements OAuth2 authentication...",
  "author": "john-doe",
  "created_at": "2024-01-15T10:30:00Z",
  "merged_at": "2024-01-16T14:20:00Z",
  "is_merged": true,
  "additions": 450,
  "deletions": 23,
  "changed_files": 12,
  "labels_full": ["feature", "high-risk"],
  "feature_rule": "label-allow",
  "feature_confidence": 0.9,
  "risk_score": 6.8,
  "high_risk": false,
  "risk_reasons": ["auth", "external-api"],
  "top_risky_files": [
    {
      "file_path": "src/auth/login.py",
      "risk": 7.2,
      "lines": 320,
      "status": "modified"
    }
  ],
  "updated_at": "2024-01-20T16:45:00Z"
}
```

## Embedding Construction

### Text Embedding Process

1. **Content Preparation**:
   - PR title + body concatenation
   - File content extraction
   - Text normalization and cleaning

2. **Embedding Generation**:
   - Model: OpenAI text-embedding-ada-002
   - Dimensions: 1536
   - Token limit: 8191 tokens per request

3. **Vector Storage**:
   - Milvus IVF_FLAT index
   - L2 distance metric
   - ef=64 for search optimization

### Example Embedding Pipeline

```python
# PR embedding
pr_text = f"{pr.title}\n\n{pr.body}"
embedding = openai.Embedding.create(
    model="text-embedding-ada-002",
    input=pr_text
)['data'][0]['embedding']

# File embedding
file_text = f"File: {filename}\nContent: {file_content}"
embedding = openai.Embedding.create(
    model="text-embedding-ada-002", 
    input=file_text
)['data'][0]['embedding']
```

## Data Relationships

### Foreign Key Relationships
- `author_metrics_daily.username` → `authors.username`
- `author_metrics_window.username` → `authors.username`
- `author_prs_window.username` → `authors.username`
- `author_file_ownership.username` → `authors.username`

### Composite Keys
- `author_metrics_daily`: `(username, repo_name, day)`
- `author_metrics_window`: `(username, repo_name, window_days, start_date, end_date)`
- `author_prs_window`: `(username, repo_name, window_days, start_date, end_date, pr_number)`
- `author_file_ownership`: `(username, repo_name, window_days, start_date, end_date, file_id)`
- `repo_prs`: `(repo_name, pr_number)`

## Gaps & Assumptions

### Missing Schema Elements
- No explicit database migration files
- No RLS (Row Level Security) policies documented
- No trigger functions for `updated_at` timestamps
- No materialized views for complex aggregations

### Assumptions
- All timestamps stored in UTC
- JSONB fields for flexible schema evolution
- Default values for numeric fields
- Cascade deletes for foreign key relationships
