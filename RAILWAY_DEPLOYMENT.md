# 🚂 Railway Deployment Guide - What the repo

Complete guide for deploying the "What the repo" application on Railway.

## 📋 Prerequisites

- [Railway Account](https://railway.app/)
- GitHub repository with your code
- Environment variables ready

## 🏗️ Project Structure

```
what_the_repo/
├── main.py              # FastAPI application
├── requirements.txt     # Railway-optimized dependencies
├── runtime.txt         # Python version specification
├── Procfile           # Railway start command
├── railway.json       # Railway configuration
├── .gitignore         # Git ignore file
└── RAILWAY_DEPLOYMENT.md # This file
```

## 🚀 Quick Deployment

### 1. **Connect to Railway**

1. Go to [railway.app](https://railway.app/)
2. Sign in with GitHub
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose your `what_the_repo` repository

### 2. **Configure Environment Variables**

In Railway dashboard, add these environment variables:

```bash
# Milvus Configuration
MILVUS_URL=your_milvus_url
MILVUS_TOKEN=your_milvus_token
COLLECTION_NAME=your_collection_name

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SUPABASE_DB_URL=your_supabase_db_url
```

### 3. **Deploy**

Railway will automatically:
- Read `runtime.txt` for Python version
- Install dependencies from `requirements.txt`
- Use `Procfile` for start command
- Apply `railway.json` configuration

## ⚙️ Configuration Files

### `runtime.txt`
```txt
python-3.12.4
```
Specifies Python version for Railway.

### `Procfile`
```procfile
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```
Defines the start command for Railway.

### `railway.json`
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 300,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

## 🔧 Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MILVUS_URL` | Milvus cluster URL | `https://your-cluster.zilliz.com` |
| `MILVUS_TOKEN` | Milvus API token | `your_milvus_token` |
| `COLLECTION_NAME` | Milvus collection name | `pr_data` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `SUPABASE_URL` | Supabase project URL | `https://your-project.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | `eyJ...` |
| `SUPABASE_DB_URL` | Supabase database URL | `postgresql://...` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Application port | Set by Railway |
| `RAILWAY_ENVIRONMENT` | Deployment environment | `production` |

## 🧪 Testing Deployment

### Health Check
```bash
curl https://your-app.railway.app/health
```

### API Endpoints
```bash
# Home page
curl https://your-app.railway.app/

# Engineer Lens
curl https://your-app.railway.app/engineering-lens

# What Shipped
curl https://your-app.railway.app/what-shipped

# API documentation
curl https://your-app.railway.app/docs
```

## 📊 Monitoring

### Railway Dashboard
- **Logs**: Real-time application logs
- **Metrics**: CPU, memory, network usage
- **Deployments**: Deployment history and status
- **Environment**: Variable management

### Health Check Endpoint
```json
{
  "status": "healthy",
  "timestamp": "2025-01-13T22:30:00.000000",
  "environment": "production",
  "python_version": "3.12.4",
  "platform": "Linux-x86_64"
}
```

## 🔍 Troubleshooting

### Common Issues

1. **Build Fails**
   ```bash
   # Check requirements.txt syntax
   pip install -r requirements.txt
   
   # Verify Python version
   python --version
   ```

2. **Application Won't Start**
   ```bash
   # Check logs in Railway dashboard
   # Verify environment variables
   # Test start command locally
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

3. **Database Connection Issues**
   ```bash
   # Verify Supabase credentials
   # Check Milvus connection
   # Test database connectivity
   ```

### Debug Commands

```bash
# Local testing
python main.py

# Check dependencies
pip list

# Test health endpoint
curl http://localhost:8000/health

# Verify environment
python -c "import os; print(os.environ.get('MILVUS_URL'))"
```

## 🚀 Performance Optimization

### Railway-Specific Optimizations

1. **Cold Start Reduction**
   - Use specific dependency versions
   - Minimize package size
   - Optimize imports

2. **Memory Management**
   - Monitor memory usage
   - Use connection pooling
   - Implement caching

3. **Response Time**
   - Optimize database queries
   - Use async operations
   - Implement caching

## 🔐 Security

### Best Practices

1. **Environment Variables**
   - Never commit secrets to Git
   - Use Railway's secure variable storage
   - Rotate keys regularly

2. **API Security**
   - Validate all inputs
   - Implement rate limiting
   - Use HTTPS in production

3. **Database Security**
   - Use connection pooling
   - Implement proper authentication
   - Regular security updates

## 📈 Scaling

### Railway Scaling Options

1. **Auto-scaling**: Configure based on traffic
2. **Manual scaling**: Set specific resource limits
3. **Custom domains**: Add your own domain
4. **CDN**: Enable for static assets

## 🔄 Continuous Deployment

### GitHub Integration

1. **Automatic Deployments**
   - Push to main branch triggers deployment
   - Preview deployments for pull requests
   - Rollback to previous versions

2. **Deployment Strategies**
   - Blue-green deployment
   - Rolling updates
   - Canary releases

## 📞 Support

### Railway Resources

- [Railway Documentation](https://docs.railway.app/)
- [Railway Discord](https://discord.gg/railway)
- [Railway Status](https://status.railway.app/)

### Application Support

- Check application logs in Railway dashboard
- Monitor health check endpoint
- Review error responses

---

**Happy deploying on Railway! 🚂**
