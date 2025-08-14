# 🔍 What the repo - GitHub Repository Analytics Platform

A comprehensive platform for analyzing GitHub repositories with AI-powered insights, risk assessment, and interactive dashboards. This system provides deep analytics on pull requests, engineer contributions, and code changes across your repositories.

## 🎯 Overview

**What the repo** is a full-stack analytics platform that combines:
- **GitHub PR Collection** with AI-powered analysis
- **Vector Search** using Milvus for semantic queries
- **Interactive Dashboards** for engineer insights and shipping analytics
- **Risk Assessment** for code changes and PRs
- **Real-time Analytics** with Supabase PostgreSQL

## 🏗️ Architecture

```
GitHub API → Data Collection → Milvus Vector DB → Analytics Engine → Supabase → Web UI
     ↓              ↓              ↓                    ↓              ↓         ↓
PR Data    →  AI Analysis   →  Vector Search   →  Metrics Calc  →  Fast UI  →  Dashboards
```

## 📁 Project Structure

```
what_the_repo/
├── 📂 git_data_download/          # GitHub PR data collection
├── 📂 milvus_data_load/           # Vector database loading
├── 📂 postgres_data_load/         # Analytics data processing
├── 📂 static/                     # Web assets
├── 🚀 main.py                     # FastAPI web application (local development)
├── 🛠️ start_app.py               # Application startup script
├── 📋 requirements.txt            # All dependencies
├── 🚀 api/                        # Vercel serverless deployment
│   ├── index.py                   # Vercel-compatible FastAPI app
│   ├── requirements.txt           # Vercel dependencies
│   └── static/                    # Static files for Vercel
├── ⚙️ vercel.json                 # Vercel configuration
└── 📖 VERCEL_DEPLOYMENT.md        # Vercel deployment guide
```

---

## 📂 Directory Documentation

### 🔽 git_data_download/

**Purpose**: Collects comprehensive pull request data from GitHub repositories with AI-powered analysis.

**Key Files**:
- `github_pr_collector.py` - Main data collection script

**Features**:
- ✅ **Complete PR Data**: Title, description, metadata, file changes
- ✅ **AI-Powered Summaries**: File-level and PR-level summaries using OpenAI GPT
- ✅ **Risk Assessment**: Comprehensive risk scoring for files and PRs
- ✅ **File Analysis**: Language detection, content extraction, statistics
- ✅ **Rate Limiting**: Respects GitHub API limits
- ✅ **Batch Processing**: Efficient handling of large repositories

**Usage**:
```bash
# Set environment variables
export GITHUB_TOKEN="your_github_token"
export OPENAI_API_KEY="your_openai_api_key"

# Collect PR data
python git_data_download/github_pr_collector.py owner/repo --state all --output pr_data.json
```

**Risk Assessment Features**:
- **File-Level Scoring**: 0-10 risk score with detailed reasons
- **High-Risk Detection**: Automatic flagging of dangerous changes
- **Confidence Scoring**: Reliability indicators for assessments
- **Comprehensive Rules**: Size, security, API changes, schema modifications

---

### 🔽 milvus_data_load/

**Purpose**: Loads processed PR data into Milvus vector database for semantic search and analysis.

**Key Files**:
- `load_to_milvus.py` - Vector database loader

**Features**:
- ✅ **Vector Embeddings**: 3072-dimensional embeddings using OpenAI
- ✅ **Multiple Text Types**: Title/body, summaries, code chunks
- ✅ **Smart Processing**: Function extraction, content limits, batch insertion
- ✅ **Rate Limiting**: Built-in API call management
- ✅ **Schema Compliance**: Proper Milvus collection structure

**Usage**:
```bash
# Set environment variables
export MILVUS_URL="https://your-cluster.zillizcloud.com"
export MILVUS_TOKEN="your_milvus_token"
export OPENAI_API_KEY="your_openai_api_key"

# Load data to Milvus
python milvus_data_load/load_to_milvus.py pr_data.json --collection github_prs
```

**Milvus Schema**:
- **Vector Field**: 3072-dimensional embeddings
- **Metadata Fields**: Repository, PR, file, author information
- **Content Types**: title_body, pr_summary, code_chunk
- **Status Tracking**: Open, closed, merged states

---

### 🔽 postgres_data_load/

**Purpose**: Processes data for analytics dashboards and engineer insights.

**Key Files**:
- `engineer_lens_data_processor.py` - Engineer analytics processor
- `what_shipped_data_processor.py` - Shipping analytics processor

**Features**:
- ✅ **Engineer Metrics**: Throughput, risk assessment, contribution analysis
- ✅ **Shipping Analytics**: Feature detection, deployment tracking
- ✅ **Real-time Processing**: Incremental updates and ETL workflows
- ✅ **Dashboard Optimization**: Pre-calculated metrics for fast UI

**Usage**:
```bash
# Process engineer analytics
python postgres_data_load/engineer_lens_data_processor.py --repo "owner/repo"

# Process shipping analytics
python postgres_data_load/what_shipped_data_processor.py --repo "owner/repo"
```

---

## 🚀 Web Application

### FastAPI Application (`main.py`)

**Features**:
- ✅ **Repository Selection**: Dropdown for available repositories
- ✅ **Semantic Search**: Natural language queries about code
- ✅ **Interactive Dashboards**: Engineer Lens and What Shipped pages
- ✅ **PR Timeline**: Visual timeline with status color coding
- ✅ **Real-time Analytics**: Fast rendering with Supabase data

### Vercel Serverless Application (`api/index.py`)

**Features**:
- ✅ **Serverless Deployment**: Optimized for Vercel's serverless environment
- ✅ **Graceful Degradation**: Handles missing services gracefully
- ✅ **Cold Start Optimization**: Efficient initialization for serverless
- ✅ **Error Handling**: Returns empty results instead of errors
- ✅ **Health Monitoring**: Built-in health check endpoint

**Pages**:
- **Home** (`/`): Repository selection and search interface
- **Engineer Lens** (`/engineering-lens`): Engineer contribution analytics
- **What Shipped** (`/what-shipped`): Feature and deployment tracking
- **PR Details** (`/pr-details`): Detailed pull request information

**API Endpoints**:
- `GET /api/repositories` - Available repositories
- `GET /api/search` - Semantic search functionality
- `GET /api/engineers` - Engineer data for dashboard
- `GET /api/what-shipped-data` - Shipping analytics data
- `GET /health` - Application health check

### Startup Script (`start_app.py`)

**Features**:
- ✅ **Environment Validation**: Checks required variables
- ✅ **User-Friendly Interface**: Clear startup messages
- ✅ **Error Handling**: Graceful error management
- ✅ **Configuration Display**: Shows active settings

**Usage**:
```bash
# Start with startup script (recommended for development)
python start_app.py

# Or start directly
python main.py
```

---

## 🛠️ Setup Instructions

### 1. Environment Variables

Create a `.env` file with:

```bash
# GitHub API
GITHUB_TOKEN=your_github_token

# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# Milvus Vector Database
MILVUS_URL=https://your-cluster.zillizcloud.com
MILVUS_TOKEN=your_milvus_token
COLLECTION_NAME=github_prs

# Supabase PostgreSQL
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_DB_URL=postgresql://user:password@host:port/database
```

### 2. Install Dependencies

   ```bash
# Install all dependencies
   pip install -r requirements.txt
   ```

### 3. Database Setup

#### Supabase Tables

Run these SQL commands in your Supabase database:

```sql
-- Authors table
CREATE TABLE public.authors (
  id bigserial primary key,
  username text unique not null,
  display_name text,
  avatar_url text
);

-- Daily metrics
CREATE TABLE public.author_metrics_daily (
  id bigserial primary key,
  username text not null references public.authors(username) on delete cascade,
  repo_name text not null,
  day date not null,
  prs_submitted int not null default 0,
  prs_merged int not null default 0,
  lines_changed int not null default 0,
  high_risk_prs int not null default 0,
  features_merged int not null default 0,
  updated_at timestamptz not null default now(),
  unique(username, repo_name, day)
);

-- Window metrics
CREATE TABLE public.author_metrics_window (
  id bigserial primary key,
  username text not null references public.authors(username) on delete cascade,
  repo_name text not null,
  window_days int not null,
  end_date date not null,
  prs_submitted int not null default 0,
  prs_merged int not null default 0,
  high_risk_prs int not null default 0,
  high_risk_rate float not null default 0.0,
  lines_changed int not null default 0,
  ownership_low_risk_prs int not null default 0,
  updated_at timestamptz not null default now(),
  unique(username, repo_name, window_days, end_date)
);

-- File ownership
CREATE TABLE public.author_file_ownership (
  id bigserial primary key,
  username text not null references public.authors(username) on delete cascade,
  repo_name text not null,
  window_days int not null,
  end_date date not null,
  file_path text not null,
  ownership_pct float not null default 0.0,
  lines_owned int not null default 0,
  total_lines int not null default 0,
  updated_at timestamptz not null default now(),
  unique(username, repo_name, window_days, end_date, file_path)
);

-- PR features
CREATE TABLE public.author_prs_window (
  id bigserial primary key,
  username text not null references public.authors(username) on delete cascade,
  repo_name text not null,
  window_days int not null,
  end_date date not null,
  pr_id bigint not null,
  pr_number int not null,
  title text not null,
  pr_summary text,
  risk_score float not null default 0.0,
  high_risk boolean not null default false,
  is_merged boolean not null default false,
  merged_at timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null default now(),
  unique(username, repo_name, window_days, end_date, pr_id)
);

-- What Shipped table
CREATE TABLE public.repo_prs (
  id bigserial primary key,
  repo_name text not null,
  pr_number int not null,
  title text not null,
  pr_summary text,
  author text not null,
  created_at timestamptz not null,
  merged_at timestamptz,
  is_merged boolean not null default false,
  additions int not null default 0,
  deletions int not null default 0,
  changed_files int not null default 0,
  labels_full jsonb,
  feature_rule text,
  feature_confidence float,
  risk_score float not null default 0.0,
  high_risk boolean not null default false,
  risk_reasons jsonb,
  top_risky_files jsonb,
  updated_at timestamptz not null default now(),
  unique(repo_name, pr_number)
);
```

### 4. Data Pipeline

#### Step 1: Collect PR Data
```bash
python git_data_download/github_pr_collector.py owner/repo --state all --output pr_data.json
```

#### Step 2: Load to Milvus
     ```bash
python milvus_data_load/load_to_milvus.py pr_data.json --collection github_prs
```

#### Step 3: Process Analytics
```bash
# Engineer analytics
python postgres_data_load/engineer_lens_data_processor.py --repo "owner/repo"

# Shipping analytics
python postgres_data_load/what_shipped_data_processor.py --repo "owner/repo"
```

#### Step 4: Start Web Application
     ```bash
python start_app.py
```

---

## 🧪 Testing

### Test Files

- `test_what_shipped_processor.py` - What Shipped processor tests
- `test_github_pr_collector_output.json` - Sample test data

### Running Tests

```bash
# Run What Shipped tests
python test_what_shipped_processor.py

# Run with sample data
python -m pytest test_*.py
```

---

## 📊 Features Overview

### 🔍 Semantic Search
- Natural language queries about repository code
- Vector-based similarity search
- Multi-modal content (titles, summaries, code)

### 👤 Engineer Lens
- Individual engineer analytics
- Throughput metrics and risk assessment
- Contribution heatmaps and file ownership
- Time-based filtering (7, 14, 30, 90 days)

### 📦 What Shipped
- Feature detection and classification
- Deployment tracking and analytics
- Risk assessment for shipped changes
- Author and time-based filtering

### ⚠️ Risk Assessment
- File-level risk scoring (0-10)
- PR-level risk aggregation
- High-risk change detection
- Confidence scoring and reasoning

---

## 🔧 Configuration

### Collection Names
- **Milvus**: `github_prs` (default)
- **Supabase**: `authors`, `author_metrics_*`, `repo_prs`

### API Limits
- **GitHub**: Respects rate limits automatically
- **OpenAI**: Built-in rate limiting for embeddings
- **Milvus**: Batch processing for efficiency

### Performance
- **Vector Search**: Optimized for 3072-dimensional embeddings
- **Database**: Pre-calculated metrics for fast dashboard rendering
- **Caching**: Supabase for real-time analytics

---

## 🚀 Deployment

### Development
```bash
python start_app.py
```

### Production
```bash
# Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000

# Using gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Vercel Serverless Deployment (Recommended)
```bash
# Deploy to Vercel
vercel --prod

# Or connect GitHub repository for automatic deployments
```

**📖 See [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md) for detailed Vercel deployment guide.**

### Docker (Optional)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "start_app.py"]
```

---

## 📈 Monitoring

### Health Checks
- `GET /health` - Application status
- Database connectivity checks
- Milvus collection status

### Logging
- Structured logging with `structlog`
- Error tracking and debugging
- Performance metrics

---

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch
3. **Add** tests for new functionality
4. **Update** documentation
5. **Submit** a pull request

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🆘 Support

For issues and questions:
1. Check the documentation in each subdirectory
2. Review the test files for usage examples
3. Check environment variable configuration
4. Verify database schema setup

**Happy analyzing! 🎉** 