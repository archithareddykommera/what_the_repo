# 🚀 Vercel Deployment Guide

This guide will help you deploy "What the repo" to Vercel for serverless hosting.

## 📋 Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Repository**: Your code should be in a GitHub repository
3. **Environment Variables**: Prepare your API keys and configuration

## 🔧 Environment Variables

Before deploying, you'll need to set up these environment variables in Vercel:

### Required Variables

```bash
# Milvus Vector Database
MILVUS_URL=https://your-cluster.zillizcloud.com
MILVUS_TOKEN=your_milvus_token
COLLECTION_NAME=pr_index_what_the_repo

# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key

# Supabase (Optional for full features)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_DB_URL=postgresql://user:password@host:port/database
```

## 🚀 Deployment Steps

### Step 1: Connect to Vercel

1. **Install Vercel CLI** (optional):
   ```bash
   npm i -g vercel
   ```

2. **Connect your repository**:
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository

### Step 2: Configure Build Settings

Vercel will automatically detect the Python project and use the configuration from `vercel.json`:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "dest": "/api/static/$1"
    },
    {
      "src": "/(.*)",
      "dest": "/api/index.py"
    }
  ]
}
```

### Step 3: Set Environment Variables

In your Vercel project dashboard:

1. Go to **Settings** → **Environment Variables**
2. Add each environment variable:
   - `MILVUS_URL`
   - `MILVUS_TOKEN`
   - `OPENAI_API_KEY`
   - `COLLECTION_NAME`
   - `SUPABASE_URL` (optional)
   - `SUPABASE_SERVICE_ROLE_KEY` (optional)
   - `SUPABASE_DB_URL` (optional)

### Step 4: Deploy

1. **Automatic Deployment**: Push to your main branch
2. **Manual Deployment**: Use Vercel CLI:
   ```bash
   vercel --prod
   ```

## 📁 Project Structure for Vercel

```
what_the_repo/
├── api/
│   ├── index.py              # Main FastAPI application
│   ├── requirements.txt      # Python dependencies
│   └── static/              # Static files (if any)
├── vercel.json              # Vercel configuration
├── README.md                # Project documentation
└── requirements.txt         # Main requirements (not used by Vercel)
```

## 🔍 Key Differences for Vercel

### 1. **API Directory Structure**
- Main application is in `api/index.py`
- Static files are served from `api/static/`
- Routes are configured in `vercel.json`

### 2. **Serverless Limitations**
- **Cold Starts**: First request may be slower
- **Memory Limits**: 1024MB per function
- **Timeout**: 10 seconds for hobby plan, 60 seconds for pro
- **File System**: Read-only, no persistent storage

### 3. **Error Handling**
- Graceful degradation when services are unavailable
- Returns empty arrays instead of throwing errors
- Health check endpoint for monitoring

## 🧪 Testing Your Deployment

### 1. Health Check
```bash
curl https://your-app.vercel.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "milvus_connected": true,
  "openai_connected": true,
  "deployment": "vercel"
}
```

### 2. Home Page
```bash
curl https://your-app.vercel.app/
```

### 3. API Endpoints
```bash
# Get repositories
curl https://your-app.vercel.app/api/repositories

# Search PRs
curl "https://your-app.vercel.app/api/search?query=test&repo_name=owner/repo"
```

## 🔧 Custom Domain (Optional)

1. **Add Domain**: Go to Vercel dashboard → Settings → Domains
2. **Configure DNS**: Follow Vercel's DNS instructions
3. **SSL**: Automatically handled by Vercel

## 📊 Monitoring and Analytics

### Vercel Analytics
- **Function Logs**: View in Vercel dashboard
- **Performance**: Monitor function execution times
- **Errors**: Track function failures and timeouts

### Health Monitoring
```bash
# Set up monitoring for your health endpoint
curl -f https://your-app.vercel.app/health || echo "App is down"
```

## 🚨 Troubleshooting

### Common Issues

1. **Cold Start Timeouts**
   ```
   Error: Function timeout
   Solution: Optimize initialization, use connection pooling
   ```

2. **Memory Issues**
   ```
   Error: Function memory limit exceeded
   Solution: Reduce batch sizes, optimize data processing
   ```

3. **Environment Variables**
   ```
   Error: Missing environment variable
   Solution: Check Vercel dashboard → Settings → Environment Variables
   ```

4. **Milvus Connection**
   ```
   Error: Failed to connect to Milvus
   Solution: Verify MILVUS_URL and MILVUS_TOKEN
   ```

### Debug Mode

Enable debug logging by adding to your environment variables:
```bash
LOG_LEVEL=DEBUG
```

## 🔄 Continuous Deployment

### GitHub Integration
1. **Automatic Deployments**: Every push to main branch
2. **Preview Deployments**: Every pull request
3. **Rollback**: Easy rollback to previous versions

### Deployment Commands
```bash
# Deploy to preview
vercel

# Deploy to production
vercel --prod

# List deployments
vercel ls
```

## 📈 Performance Optimization

### 1. **Connection Pooling**
- Reuse database connections
- Implement connection caching
- Use connection pooling libraries

### 2. **Caching**
- Cache frequently accessed data
- Use Vercel's edge caching
- Implement response caching

### 3. **Code Splitting**
- Keep functions lightweight
- Minimize dependencies
- Use lazy loading where possible

## 🔐 Security Considerations

### 1. **Environment Variables**
- Never commit secrets to Git
- Use Vercel's environment variable encryption
- Rotate API keys regularly

### 2. **CORS Configuration**
- Configure allowed origins
- Restrict API access if needed
- Use proper authentication

### 3. **Rate Limiting**
- Implement rate limiting for API endpoints
- Monitor usage patterns
- Set up alerts for abuse

## 📞 Support

### Vercel Support
- **Documentation**: [vercel.com/docs](https://vercel.com/docs)
- **Community**: [github.com/vercel/vercel/discussions](https://github.com/vercel/vercel/discussions)
- **Status**: [vercel-status.com](https://vercel-status.com)

### Application Support
- **Issues**: Create GitHub issues in your repository
- **Logs**: Check Vercel function logs
- **Health**: Monitor `/health` endpoint

## 🎉 Success!

Once deployed, your application will be available at:
```
https://your-app.vercel.app
```

### Next Steps
1. **Test all endpoints** to ensure functionality
2. **Set up monitoring** for production use
3. **Configure custom domain** if needed
4. **Set up CI/CD** for automated deployments

---

**Happy deploying! 🚀**
