# 🔽 postgres_data_load/

**Purpose**: Processes data for analytics dashboards and engineer insights.

## 📋 Overview

This directory contains the analytics data processing system that transforms raw PR data into structured analytics for the Engineer Lens and What Shipped dashboards. It processes data from Milvus collections and stores pre-calculated metrics in Supabase PostgreSQL for fast dashboard rendering.

## 🗂️ Files

- `engineer_lens_data_processor.py` - Engineer analytics processor
- `what_shipped_data_processor.py` - Shipping analytics processor

## ✨ Features

### 👤 Engineer Lens Analytics
- **Throughput Metrics**: PRs submitted, merged, review activity
- **Risk Assessment**: High-risk PR identification and scoring
- **Contribution Heatmap**: File-level ownership and contribution analysis
- **Feature Analysis**: AI-powered feature detection and classification
- **Time-based Filtering**: 7, 14, 30, 90-day analysis windows

### 📦 What Shipped Analytics
- **Feature Detection**: Automatic feature classification and labeling
- **Deployment Tracking**: Merged PR analysis and shipping insights
- **Risk Assessment**: Risk scoring for shipped changes
- **Author Analytics**: Contributor analysis and filtering
- **Time Windows**: Flexible time-based filtering

### 🔄 Real-time Processing
- **Incremental Updates**: ETL workflows for continuous processing
- **Upsert Operations**: Efficient data updates without duplicates
- **Batch Processing**: Optimized for large datasets
- **Error Recovery**: Graceful handling of processing failures

## 🚀 Usage

### Prerequisites

```bash
# Set environment variables
export MILVUS_URL="https://your-cluster.zillizcloud.com"
export MILVUS_TOKEN="your_milvus_token"
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your_service_role_key"
export SUPABASE_DB_URL="postgresql://user:password@host:port/database"
export OPENAI_API_KEY="your_openai_api_key"
```

### Engineer Lens Processing

```bash
# Process engineer analytics for a specific repository
python engineer_lens_data_processor.py --repo "owner/repo"

# Process all repositories
python engineer_lens_data_processor.py --all-repos

# Force refresh (clear existing data)
python engineer_lens_data_processor.py --repo "owner/repo" --force-refresh
```

### What Shipped Processing

```bash
# Process shipping analytics for a specific repository
python what_shipped_data_processor.py --repo "owner/repo"

# Process all repositories
python what_shipped_data_processor.py

# Incremental update (default behavior)
python what_shipped_data_processor.py --repo "owner/repo" --incremental

# Force refresh all data
python what_shipped_data_processor.py --force-refresh
```

## 🗄️ Database Schema

### Engineer Lens Tables

#### `authors`
```sql
CREATE TABLE public.authors (
  id bigserial primary key,
  username text unique not null,
  display_name text,
  avatar_url text
);
```

#### `author_metrics_daily`
```sql
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
```

#### `author_metrics_window`
```sql
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
```

#### `author_file_ownership`
```sql
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
```

#### `author_prs_window`
```sql
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
```

### What Shipped Tables

#### `repo_prs`
```sql
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

## 📊 Processing Logic

### Engineer Lens Processing

1. **Data Extraction**: Fetches PR and file data from Milvus collections
2. **Author Identification**: Creates author profiles and metadata
3. **Daily Metrics**: Calculates daily rollups for each engineer
4. **Window Metrics**: Computes time-windowed snapshots (7/14/30/90 days)
5. **File Ownership**: Calculates file-level contribution percentages
6. **Feature Analysis**: Identifies and classifies features

### What Shipped Processing

1. **PR Data Extraction**: Fetches PR data from Milvus collections
2. **Feature Classification**: Identifies features using AI and rules
3. **Risk Assessment**: Calculates risk scores and reasons
4. **File Analysis**: Processes file changes and risky files
5. **Upsert Operations**: Updates database with new/updated PRs

## ⚙️ Configuration

### Environment Variables
- `MILVUS_URL`: Milvus cluster URL
- `MILVUS_TOKEN`: Milvus authentication token
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key
- `SUPABASE_DB_URL`: Direct PostgreSQL connection URL
- `OPENAI_API_KEY`: OpenAI API key for embeddings

### Processing Options
- **Incremental Mode**: Default behavior, updates existing data
- **Force Refresh**: Clears existing data and reprocesses all
- **Repository Filtering**: Process specific repositories
- **Batch Processing**: Configurable batch sizes for efficiency

## 🧪 Testing

### Test Engineer Lens Processing

```bash
# Test with a small repository
python engineer_lens_data_processor.py --repo "test/repo" --force-refresh

# Verify database tables
python -c "
from supabase import create_client
client = create_client('your_supabase_url', 'your_key')
result = client.table('authors').select('*').execute()
print(f'Authors: {len(result.data)}')
"
```

### Test What Shipped Processing

```bash
# Test with sample data
python what_shipped_data_processor.py --repo "test/repo" --incremental

# Check processing results
python -c "
from supabase import create_client
client = create_client('your_supabase_url', 'your_key')
result = client.table('repo_prs').select('*').execute()
print(f'PRs processed: {len(result.data)}')
"
```

## 📈 Performance

### Optimization Features
- **Batch Upserts**: Efficient database operations
- **Connection Pooling**: Optimized database connections
- **Memory Management**: Efficient data processing
- **Error Recovery**: Graceful failure handling

### Expected Performance
- **Small Repository** (< 1K PRs): 2-5 minutes
- **Medium Repository** (1K-10K PRs): 10-30 minutes
- **Large Repository** (> 10K PRs): 30-60 minutes

## 🔍 Example Output

### Engineer Lens Processing
```
[INFO] Processing repository: owner/repo
[INFO] Found 50 engineers in repository
[INFO] Processing 1,000 PRs for engineer analytics
[INFO] Calculating daily metrics for 30 days
[INFO] Computing window metrics (7, 14, 30, 90 days)
[INFO] Analyzing file ownership and contributions
[SUCCESS] Processed owner/repo: 50 engineers, 1,000 PRs, 150 features
```

### What Shipped Processing
```
[INFO] Processing repository: owner/repo
[INFO] Found 735 PRs in Milvus collection
[INFO] Processing PRs for feature classification
[INFO] Calculating risk scores and assessments
[INFO] Upserting 735 records to repo_prs table
[SUCCESS] Processed owner/repo: 735 PRs, 245 features, 45 high-risk
```

## 🆘 Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```
   Error: Failed to connect to Supabase
   Solution: Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
   ```

2. **Milvus Connection Errors**
   ```
   Error: Failed to connect to Milvus
   Solution: Check MILVUS_URL and MILVUS_TOKEN
   ```

3. **Schema Errors**
   ```
   Error: Table does not exist
   Solution: Run database setup SQL commands
   ```

4. **Memory Issues**
   ```
   Error: Out of memory
   Solution: Process smaller batches or repositories
   ```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python engineer_lens_data_processor.py --repo "owner/repo"
```

## 📚 Next Steps

After processing analytics data, you can:
1. View Engineer Lens dashboard (`../main.py` → `/engineering-lens`)
2. View What Shipped dashboard (`../main.py` → `/what-shipped`)
3. Query analytics data via API endpoints

## 🔗 Related Files

- `../git_data_download/github_pr_collector.py` - Data collection
- `../milvus_data_load/load_to_milvus.py` - Vector database loading
- `../main.py` - Web application with dashboards
- `../requirements.txt` - Dependencies

---

**Happy processing! 🚀**
