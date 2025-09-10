# What the Repo - Repository Inventory

**How to read this doc**: This document provides a comprehensive inventory of the What the Repo application codebase, including file structure, dependencies, and runtime environment configuration.

## Repository Structure

### Core Application Files
- `main.py` (179KB, 4311 lines) - FastAPI web application with embedded HTML/JS UI
- `start_app.py` (2.2KB, 74 lines) - Application startup script
- `requirements.txt` (431B, 26 lines) - Main application dependencies
- `runtime.txt` (14B, 2 lines) - Python version specification (3.11)
- `Procfile` (62B, 2 lines) - Railway deployment configuration

### Routing & Query Processing
- `router.py` (13KB, 397 lines) - Query routing logic (direct/hybrid/vector)
- `time_parse.py` (12KB, 324 lines) - Natural language time parsing
- `direct_handlers.py` (14KB, 421 lines) - Direct database query handlers
- `hybrid_handlers.py` (11KB, 359 lines) - Hybrid search handlers
- `vector_handlers.py` (9.8KB, 315 lines) - Vector search handlers

### Database & Infrastructure
- `milvus_client.py` (10KB, 299 lines) - Milvus vector database client
- `analyze_features.py` (1.7KB, 47 lines) - Feature analysis utilities

### Data Processing
- `postgres_data_load/` - PostgreSQL ETL and analytics processing
  - `engineer_lens_data_processor.py` (80KB, 1494 lines) - Engineer metrics ETL
  - `what_shipped_data_processor.py` (26KB, 604 lines) - What Shipped ETL
  - `pr_data_20250811_235048.json` (6.4MB) - Sample PR data
- `milvus_data_load/` - Vector database operations
- `git_data_download/` - GitHub API data collection

### Static Assets & UI
- `static/` - Web assets and static files
- `api/` - API endpoint definitions

### Testing & Debug
- `test_*.py` - Various test files for routing, deployment, features
- `debug_*.py` - Debug utilities and scripts
- `test_deployment.py` (1.6KB, 52 lines) - Railway deployment testing

### Deployment Configuration
- `railway.json` (353B, 14 lines) - Railway platform configuration
- `build.sh` (457B, 25 lines) - Build script
- `.dockerignore` (503B, 61 lines) - Docker ignore patterns
- `RAILWAY_DEPLOYMENT.md` (6.1KB, 276 lines) - Deployment guide

### Logs & Data
- `what_shipped_processor.log` (66KB, 535 lines) - What Shipped processing logs
- `engineer_lens_processor.log` (23MB) - Engineer Lens processing logs
- `engineer_lens_debug.log` (95KB, 918 lines) - Debug logs
- `pr_data_20250808_115049.json` (5.8MB) - Historical PR data

## Runtime Environment

### Required Environment Variables
```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_DB_URL=postgresql://postgres:password@host:port/database

# Milvus Configuration
MILVUS_URL=https://your-milvus-instance.zilliz.com
MILVUS_TOKEN=your-milvus-token

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# GitHub Configuration (for data collection)
GITHUB_TOKEN=your-github-token
```

### Python Dependencies

#### Core Application (`requirements.txt`)
- **Web Framework**: FastAPI 0.104.1, uvicorn[standard] 0.24.0
- **Data Validation**: pydantic 2.5.0
- **Vector Database**: pymilvus 2.3.6
- **AI/ML**: openai 1.3.7
- **Database**: supabase 2.7.0, psycopg2-binary 2.9.9
- **Utilities**: python-dotenv 1.0.0, requests 2.31.0, numpy >=1.21.0,<2.0.0

#### Postgres Data Load (`postgres_data_load/requirements.txt`)
- **Database**: psycopg2-binary, supabase
- **Data Processing**: pandas, numpy
- **Utilities**: python-dotenv, requests

#### Git Data Download (`git_data_download/requirements.txt`)
- **GitHub API**: PyGithub
- **Data Processing**: pandas, numpy
- **Utilities**: python-dotenv, requests

#### Milvus Data Load (`milvus_data_load/requirements.txt`)
- **Vector Database**: pymilvus
- **Embeddings**: sentence-transformers, openai
- **Data Processing**: pandas, numpy

## Key Configuration Files

### Railway Deployment (`railway.json`)
```json
{
  "build": {
    "builder": "nixpacks"
  },
  "deploy": {
    "startCommand": "python main.py",
    "healthcheckPath": "/",
    "healthcheckTimeout": 300,
    "restartPolicyType": "ON_FAILURE"
  }
}
```

### Python Runtime (`runtime.txt`)
```
python-3.11
```

### Build Script (`build.sh`)
```bash
#!/bin/bash
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Data Flow Architecture

### Primary Data Sources
1. **GitHub API** → Raw PR data collection
2. **JSON Files** → Pre-processed PR data (6.4MB sample)
3. **Milvus** → Vector embeddings for semantic search
4. **Supabase** → Precomputed analytics tables

### Processing Pipeline
1. **Data Collection**: GitHub API → JSON files
2. **ETL Processing**: JSON → PostgreSQL tables
3. **Vector Processing**: PR content → Milvus embeddings
4. **Analytics**: PostgreSQL → Precomputed metrics

### Storage Volumes
- **Vector Data**: ~6.4MB PR data → Milvus collections
- **Analytics Data**: PostgreSQL tables for metrics
- **Static Assets**: Web UI files in `/static`

## Gaps & Assumptions

### Missing Documentation
- No explicit API documentation (OpenAPI/Swagger)
- No database schema migration files
- No environment-specific configuration files

### Assumptions
- Milvus collections: `pr_index_what_the_repo`, `file_changes_what_the_repo`
- Supabase tables: `repo_prs`, `author_metrics_daily`, `author_metrics_window`, `author_prs_window`, `author_file_ownership`
- Embedding dimension: 1536 (OpenAI text-embedding-ada-002)
- Vector search parameters: ef=64, limit=50

### Security Considerations
- Service role keys used for database access
- No explicit rate limiting configuration
- CORS enabled for all origins in development
