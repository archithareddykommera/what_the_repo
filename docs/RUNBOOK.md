# What the Repo - Operations Runbook

**How to read this doc**: This document provides operational procedures for running, monitoring, and troubleshooting the What the Repo application in production and development environments.

## Local Development Setup

### Prerequisites

**Required Software**:
- Python 3.11+
- Git
- Railway CLI (for deployment)
- Docker (optional)

**Required Accounts**:
- GitHub (for API access)
- Supabase (for database)
- Milvus/Zilliz (for vector database)
- OpenAI (for embeddings and analysis)

### Environment Setup

**1. Clone Repository**:
```bash
git clone https://github.com/your-org/what-the-repo.git
cd what-the-repo
```

**2. Install Dependencies**:
```bash
# Main application
pip install -r requirements.txt

# Data processing
pip install -r postgres_data_load/requirements.txt
pip install -r milvus_data_load/requirements.txt
pip install -r git_data_download/requirements.txt
```

**3. Environment Variables**:
```bash
# Create .env file
cp .env.example .env

# Required variables
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_DB_URL=postgresql://postgres:password@host:port/database

MILVUS_URL=https://your-milvus-instance.zilliz.com
MILVUS_TOKEN=your-milvus-token

OPENAI_API_KEY=your-openai-api-key

GITHUB_TOKEN=your-github-token
```

**4. Run Application**:
```bash
python main.py
```

## ETL Pipeline Operations

### Data Collection

**GitHub Data Collection**:
```bash
# Collect PR data from GitHub
cd git_data_download
python github_pr_collector.py --repo your-org/your-repo --output pr_data.json
```

**Parameters**:
- `--repo`: Repository in format `owner/repo`
- `--output`: Output JSON file path
- `--since`: Start date (YYYY-MM-DD)
- `--until`: End date (YYYY-MM-DD)

### Data Processing

**Engineer Metrics ETL**:
```bash
# Process engineer metrics
cd postgres_data_load
python engineer_lens_data_processor.py --update-table all --force-refresh
```

**What Shipped ETL**:
```bash
# Process What Shipped data
python what_shipped_data_processor.py
```

**Available Options**:
- `--update-table`: Specific table (authors, author_metrics_daily, author_metrics_window, author_prs_window, author_file_ownership, all)
- `--force-refresh`: Force complete refresh
- `--repo-name`: Specific repository filter

### Vector Database Operations

**Load Embeddings to Milvus**:
```bash
cd milvus_data_load
python load_embeddings.py --collection pr_index --data pr_data.json
```

**Parameters**:
- `--collection`: Target collection name
- `--data`: Input JSON file
- `--batch-size`: Batch size for processing (default: 100)

## Production Deployment

### Railway Deployment

**1. Connect Repository**:
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Link project
railway link
```

**2. Configure Environment**:
```bash
# Set environment variables
railway variables set SUPABASE_URL=https://your-project.supabase.co
railway variables set SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
railway variables set MILVUS_URL=https://your-milvus-instance.zilliz.com
railway variables set MILVUS_TOKEN=your-milvus-token
railway variables set OPENAI_API_KEY=your-openai-api-key
```

**3. Deploy**:
```bash
# Deploy to Railway
railway up

# Check deployment status
railway status
```

### Health Checks

**Application Health**:
```bash
# Check application health
curl https://your-app.railway.app/

# Expected response
{
  "status": "healthy",
  "timestamp": "2024-01-20T16:45:00Z",
  "version": "1.0.0",
  "services": {
    "supabase": "connected",
    "milvus": "connected",
    "openai": "connected"
  }
}
```

**Service Connectivity**:
```bash
# Test Supabase connection
python -c "
from supabase import create_client
client = create_client('$SUPABASE_URL', '$SUPABASE_SERVICE_ROLE_KEY')
print('Supabase: OK')
"

# Test Milvus connection
python -c "
from pymilvus import connections
connections.connect('default', '$MILVUS_URL', token='$MILVUS_TOKEN')
print('Milvus: OK')
"
```

## Monitoring & Observability

### Log Analysis

**Application Logs**:
```bash
# View Railway logs
railway logs

# Filter by error level
railway logs --level error

# Follow logs in real-time
railway logs --follow
```

**ETL Logs**:
```bash
# Engineer Lens processing logs
tail -f engineer_lens_processor.log

# What Shipped processing logs
tail -f what_shipped_processor.log

# Debug logs
tail -f engineer_lens_debug.log
```

### Performance Monitoring

**Key Metrics**:
- **Query Response Time**: < 2s for direct queries, < 5s for vector queries
- **ETL Processing Time**: < 30 minutes for full repository
- **Database Connection Pool**: Monitor connection usage
- **API Rate Limits**: Track GitHub and OpenAI API usage

**Monitoring Commands**:
```bash
# Check database performance
psql $SUPABASE_DB_URL -c "
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats 
WHERE schemaname = 'public'
ORDER BY tablename, attname;
"

# Check Milvus collection stats
python -c "
from pymilvus import Collection
collection = Collection('pr_index_what_the_repo')
print(f'Collection size: {collection.num_entities}')
print(f'Index info: {collection.index().params}')
"
```

## Troubleshooting

### Common Issues

**1. Database Connection Errors**

**Symptoms**: `psycopg2.OperationalError: connection to server failed`

**Solutions**:
```bash
# Check Supabase status
curl https://status.supabase.com/

# Verify connection string
echo $SUPABASE_DB_URL

# Test connection
psql $SUPABASE_DB_URL -c "SELECT 1;"
```

**2. Milvus Connection Errors**

**Symptoms**: `pymilvus.exceptions.ConnectionException`

**Solutions**:
```bash
# Check Milvus status
curl https://your-milvus-instance.zilliz.com/health

# Verify credentials
echo $MILVUS_TOKEN

# Test connection
python -c "
from pymilvus import connections
try:
    connections.connect('default', '$MILVUS_URL', token='$MILVUS_TOKEN')
    print('Connection successful')
except Exception as e:
    print(f'Connection failed: {e}')
"
```

**3. OpenAI API Errors**

**Symptoms**: `openai.RateLimitError` or `openai.AuthenticationError`

**Solutions**:
```bash
# Check API key
echo $OPENAI_API_KEY | cut -c1-10

# Test API access
python -c "
import openai
openai.api_key = '$OPENAI_API_KEY'
try:
    response = openai.Embedding.create(
        model='text-embedding-ada-002',
        input='test'
    )
    print('API access successful')
except Exception as e:
    print(f'API error: {e}')
"
```

**4. ETL Processing Failures**

**Symptoms**: Processing stops with errors in logs

**Solutions**:
```bash
# Check data file integrity
python -c "
import json
with open('pr_data_20250811_235048.json', 'r') as f:
    data = json.load(f)
print(f'Data file loaded: {len(data)} records')
"

# Restart with smaller batch size
python engineer_lens_data_processor.py --update-table author_metrics_daily --batch-size 50

# Check for specific table issues
python -c "
from supabase import create_client
client = create_client('$SUPABASE_URL', '$SUPABASE_SERVICE_ROLE_KEY')
result = client.table('author_metrics_daily').select('*').limit(1).execute()
print('Table accessible')
"
```

### Recovery Procedures

**1. Database Recovery**

**Corrupted Data**:
```bash
# Backup current data
pg_dump $SUPABASE_DB_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
psql $SUPABASE_DB_URL < backup_20240120_164500.sql

# Re-run ETL for specific date range
python engineer_lens_data_processor.py --update-table all --since 2024-01-01 --until 2024-01-20
```

**2. Vector Database Recovery**

**Collection Issues**:
```bash
# Recreate collection
python -c "
from pymilvus import utility, Collection
if utility.has_collection('pr_index_what_the_repo'):
    utility.drop_collection('pr_index_what_the_repo')
# Recreate collection with proper schema
"

# Reload embeddings
python milvus_data_load/load_embeddings.py --collection pr_index --data pr_data.json
```

**3. Application Recovery**

**Service Restart**:
```bash
# Restart Railway service
railway service restart

# Check service status
railway status

# Monitor logs for errors
railway logs --follow
```

## Cron Recommendations

### Scheduled Tasks

**Daily ETL**:
```bash
# Add to crontab
0 2 * * * cd /path/to/what-the-repo && python postgres_data_load/engineer_lens_data_processor.py --update-table author_metrics_daily >> /var/log/etl_daily.log 2>&1
```

**Weekly Full Refresh**:
```bash
# Add to crontab
0 3 * * 0 cd /path/to/what-the-repo && python postgres_data_load/engineer_lens_data_processor.py --update-table all --force-refresh >> /var/log/etl_weekly.log 2>&1
```

**Monthly Data Collection**:
```bash
# Add to crontab
0 1 1 * * cd /path/to/what-the-repo/git_data_download && python github_pr_collector.py --repo your-org/your-repo --output pr_data_$(date +%Y%m).json >> /var/log/data_collection.log 2>&1
```

### Monitoring Cron Jobs

**Log Rotation**:
```bash
# Add to crontab
0 0 * * 0 find /var/log/ -name "*.log" -mtime +7 -delete
```

**Health Check Alerts**:
```bash
# Add to crontab
*/5 * * * * curl -f https://your-app.railway.app/ || echo "Application down" | mail -s "What the Repo Alert" admin@example.com
```

## Cost & Latency Optimization

### Batch Size Tuning

**ETL Batch Sizes**:
```python
# Optimal batch sizes for different operations
BATCH_SIZES = {
    'author_metrics_daily': 1000,
    'author_metrics_window': 500,
    'author_prs_window': 200,
    'author_file_ownership': 100,
    'repo_prs': 500
}
```

**Vector Search Parameters**:
```python
# Milvus search optimization
SEARCH_PARAMS = {
    'ef': 64,        # Higher = more accurate, slower
    'limit': 50,     # Results per query
    'nprobe': 16     # Search partitions
}
```

### Rate Limiting

**GitHub API**:
- **Limit**: 5000 requests/hour (authenticated)
- **Strategy**: Batch requests, use conditional requests
- **Monitoring**: Track remaining rate limit

**OpenAI API**:
- **Limit**: Token-based rate limits
- **Strategy**: Batch embeddings, cache results
- **Cost**: ~$0.0001 per 1K tokens

### Database Optimization

**Connection Pooling**:
```python
# Supabase connection optimization
SUPABASE_CONFIG = {
    'pool_size': 10,
    'max_overflow': 20,
    'pool_timeout': 30,
    'pool_recycle': 3600
}
```

**Query Optimization**:
```sql
-- Add indexes for common queries
CREATE INDEX idx_author_metrics_window_username ON author_metrics_window(username);
CREATE INDEX idx_author_metrics_window_repo ON author_metrics_window(repo_name);
CREATE INDEX idx_repo_prs_created_at ON repo_prs(created_at);
```

## Gaps & Assumptions

### Missing Operational Tools
- No automated backup procedures
- No comprehensive alerting system
- No performance dashboards
- No automated rollback procedures

### Assumptions
- Railway platform reliability
- External service availability
- Data consistency across services
- Manual intervention for complex failures
