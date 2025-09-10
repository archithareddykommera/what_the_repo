# What the Repo - System Architecture

**How to read this doc**: This document describes the complete system architecture of What the Repo, including data flow, components, and design decisions. Each section focuses on a specific aspect of the system.

## 1. Overview & Problems Solved

What the Repo is a comprehensive GitHub PR analysis platform that solves three core problems:

1. **Engineering Analytics Gap**: Traditional GitHub analytics lack semantic understanding and risk assessment
2. **"What Shipped" Tracking**: Difficulty tracking actual features deployed vs. code changes
3. **Semantic Search**: Finding relevant PRs and files across large codebases

The system combines vector search (Milvus), analytics (Supabase), and AI analysis (OpenAI) to provide intelligent insights into engineering activity.

## 2. User-Facing Pages & Data Contracts

### Ask Repo-GPT Page
- **Purpose**: Natural language Q&A about repository activity
- **Data Contract**: 
  - Input: Natural language query + optional repo filter
  - Output: Structured results with explanations
  - Routing: Direct/Hybrid/Vector based on query type

### What Shipped Page
- **Purpose**: Track and analyze deployed features
- **Data Contract**:
  - Input: Time filters, author filters, risk filters
  - Output: PR list with feature classification, risk scores
  - Source: `repo_prs` table with precomputed analytics

### Engineer Profile Page
- **Purpose**: Individual engineer analytics and insights
- **Data Contract**:
  - Input: Engineer username + time window (7/15/30/60/90/all_time)
  - Output: Metrics, file ownership, PR history
  - Source: `author_metrics_window`, `author_file_ownership` tables

## 3. Data Sources: GitHub API, Milvus, Supabase

### GitHub API
- **Collection**: PR metadata, files changed, timestamps
- **Processing**: Raw data → JSON files → ETL pipeline
- **Rate Limits**: 5000 requests/hour (authenticated)

### Milvus Vector Database
- **Collections**: `pr_index_what_the_repo`, `file_changes_what_the_repo`
- **Embeddings**: OpenAI text-embedding-ada-002 (1536 dimensions)
- **Index**: IVF_FLAT with ef=64 for similarity search

### Supabase PostgreSQL
- **Tables**: Analytics rollups and precomputed metrics
- **Connection**: Direct PostgreSQL + Supabase client fallback
- **RLS**: Row-level security for multi-tenant isolation

## 4. ETL Pipeline (Ingest → LLM → Embeddings → Loads)

### Data Collection Phase
```
GitHub API → Raw PR Data → JSON Files (6.4MB sample)
```

### Processing Phase
```
JSON Files → ETL Processors → PostgreSQL Tables
                ↓
            LLM Analysis → Risk Scores → Feature Classification
                ↓
            Content Embeddings → Milvus Collections
```

### Key ETL Components
- `engineer_lens_data_processor.py`: Author metrics and file ownership
- `what_shipped_data_processor.py`: PR analytics and feature tracking
- Batch processing with upsert operations for incremental updates

## 5. Risk Scoring (File→PR), Feature Classification Rules

### Risk Scoring Algorithm
1. **File-Level Risk**: LLM analysis of file changes → risk score (0-10)
2. **PR Aggregation**: Weighted average of file risks → PR risk score
3. **Thresholds**: High risk ≥ 7.0, Medium risk ≥ 4.0, Low risk < 4.0

### Feature Classification Rules (Priority Order)
1. **`label-allow`** (90% confidence): Explicit `feature` attribute in JSON
2. **`title-allow`** (70% confidence): Feature keywords in PR title
3. **`title-allow`** (60% confidence): Feature keywords in PR body
4. **`unlabeled-include`** (30% confidence): Low risk PRs (< 3.0)
5. **`excluded`** (0% confidence): Default fallback

## 6. Vector Search Routing (Direct / Hybrid / Vector)

### Routing Logic (`router.py`)
- **Direct Routes**: Scalar queries (counts, lists, specific PRs)
- **Hybrid Routes**: Topic-based with semantic terms (auth, payment, security)
- **Vector Routes**: Semantic similarity search for complex queries

### Query Patterns
```python
# Direct patterns
r'\b(count|top|most|list|merged)\b'
r'features?\s+shipped'
r'what\s+was\s+shipped'

# Hybrid patterns  
r'\b(auth|authentication|authorization)\b'
r'\b(payment|billing|invoice)\b'
r'\b(security|vulnerability|risk)\b'

# Vector patterns (fallback)
# Complex semantic queries not matching above patterns
```

## 7. Data Models: Milvus Collections + Supabase Tables

### Milvus Collections
```python
# pr_index_what_the_repo
{
    'pr_id': int,           # Primary key
    'repo_name': str,       # Repository identifier
    'pr_number': int,       # GitHub PR number
    'title': str,           # PR title
    'body': str,            # PR description
    'embedding': vector,    # 1536-dim embedding
    'created_at': int,      # Timestamp
    'is_merged': bool,      # Merge status
    'risk_score': float,    # Aggregated risk
    'feature_rule': str     # Feature classification
}

# file_changes_what_the_repo
{
    'file_id': str,         # Primary key
    'repo_name': str,       # Repository identifier
    'filename': str,        # File path
    'embedding': vector,    # 1536-dim embedding
    'pr_id': int,          # Associated PR
    'lines_changed': int,   # Change magnitude
    'risk_score': float     # File-level risk
}
```

### Supabase Tables
```sql
-- Analytics rollups
author_metrics_daily: Daily metrics per author
author_metrics_window: Windowed metrics (7/15/30/60/90/all_time)
author_prs_window: PR details per window
author_file_ownership: File ownership percentages

-- What Shipped data
repo_prs: PR analytics with feature classification
repo_kpis_daily: Daily repository KPIs
```

## 8. Caching & Pagination Strategy

### Caching Strategy
- **No explicit caching**: Relies on database query optimization
- **Connection pooling**: Supabase client connection reuse
- **Batch processing**: ETL operations use batch upserts

### Pagination Strategy
- **Limit-based**: Default 50 results, configurable up to 1000
- **Offset pagination**: For large result sets
- **Time-slicing**: Natural language time parsing for date ranges

## 9. Security: Key Handling, RLS Posture, Rate Limits

### Key Management
- **Service Role Keys**: Used for database operations (bypasses RLS)
- **Environment Variables**: Secure key storage in Railway
- **No ANON_KEY usage**: All operations use service role

### Row-Level Security (RLS)
- **Multi-tenant isolation**: Repository-based data separation
- **Author-based filtering**: Engineer profile data isolation
- **Time-based access**: Historical data access controls

### Rate Limiting
- **GitHub API**: 5000 requests/hour (authenticated)
- **OpenAI API**: Token-based rate limits
- **No application-level rate limiting**: Relies on platform limits

## 10. Scaling Concerns and SLOs

### Current Scaling Limits
- **Vector Search**: ~1000 PRs, ef=64, limit=50
- **Database**: Supabase free tier limits
- **Embeddings**: OpenAI API rate limits

### SLOs (Service Level Objectives)
- **Query Response**: < 2 seconds for direct queries
- **Vector Search**: < 5 seconds for semantic queries
- **ETL Processing**: < 30 minutes for full repository
- **Uptime**: 99.9% (Railway SLA)

### Scaling Strategies
- **Horizontal scaling**: Multiple Railway instances
- **Database scaling**: Supabase Pro for higher limits
- **Vector scaling**: Milvus cluster for larger datasets

## 11. Failure Modes & Observability

### Failure Modes
1. **Database Connection**: Supabase client fallback
2. **Vector Search**: Graceful degradation to direct queries
3. **LLM API**: Cached risk scores, feature classification
4. **Data Processing**: Incremental ETL with error recovery

### Observability
- **Logging**: Structured logs in `*.log` files
- **Error Handling**: Try-catch blocks with detailed error messages
- **Health Checks**: Railway health check endpoint
- **Monitoring**: No explicit APM integration

## 12. Testing Strategy (Unit, Contract, Smoke)

### Testing Coverage
- **Unit Tests**: `test_*.py` files for routing, parsing, deployment
- **Integration Tests**: Railway deployment testing
- **Contract Tests**: No explicit API contract testing
- **Smoke Tests**: Health check endpoints

### Test Files
- `test_routing.py`: Query routing logic
- `test_time_parsing.py`: Natural language time parsing
- `test_deployment.py`: Railway deployment validation
- `test_milvus_features.py`: Vector search functionality

## 13. Local Dev & Environment Setup

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SUPABASE_URL=...
export MILVUS_URL=...
export OPENAI_API_KEY=...

# Run application
python main.py
```

### Environment Requirements
- **Python**: 3.11 (specified in runtime.txt)
- **Dependencies**: FastAPI, uvicorn, pymilvus, supabase, openai
- **External Services**: Supabase, Milvus, OpenAI API

## 14. Deployment Paths (Docker/GitHub Actions)

### Railway Deployment (Primary)
- **Platform**: Railway with automatic GitHub integration
- **Build**: Nixpacks builder with Python 3.11
- **Deploy**: Automatic deployment on git push
- **Health Check**: `/` endpoint with 300s timeout

### Alternative Deployment
- **Docker**: `.dockerignore` configured but no Dockerfile
- **GitHub Actions**: No explicit CI/CD configuration
- **Manual**: `build.sh` script for custom deployment

## 15. Future Work (Feature Grouping, Rename Tracking, APM)

### Planned Enhancements
1. **Feature Grouping**: Cluster related PRs into feature sets
2. **Rename Tracking**: Follow file renames across PRs
3. **APM Integration**: Application performance monitoring
4. **Advanced Analytics**: Team velocity, code review metrics
5. **Real-time Updates**: WebSocket-based live updates

### Technical Debt
- **API Documentation**: OpenAPI/Swagger specification
- **Database Migrations**: Schema versioning and migrations
- **Rate Limiting**: Application-level rate limiting
- **Caching**: Redis-based caching layer
- **Monitoring**: Prometheus/Grafana integration

## Gaps & Assumptions

### Missing Components
- No explicit API versioning strategy
- No database migration system
- No comprehensive error tracking
- No performance monitoring

### Assumptions
- Single-tenant architecture per deployment
- GitHub as primary data source
- OpenAI API availability and rate limits
- Railway platform reliability
