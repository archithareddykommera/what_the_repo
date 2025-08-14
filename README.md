# 🚀 What the repo

A comprehensive GitHub PR analysis and engineering insights platform that provides AI-powered analytics, risk assessment, and "What Shipped" tracking for engineering teams.

## 📋 Features

- 🔍 **Engineer Lens**: AI-powered engineering analytics and insights
- 📦 **What Shipped**: Track and analyze what was deployed
- 🤖 **AI Analysis**: OpenAI-powered PR analysis and risk assessment
- 📊 **Vector Search**: Milvus-powered semantic search across PRs
- 🗄️ **Data Pipeline**: Complete ETL pipeline from GitHub to analytics
- 🌐 **Web Interface**: Beautiful, responsive web UI

## 🏗️ Project Structure

```
what_the_repo/
├── main.py                    # FastAPI web application
├── requirements.txt           # Railway deployment dependencies
├── runtime.txt               # Python version specification
├── Procfile                 # Railway start command
├── railway.json             # Railway configuration
├── RAILWAY_DEPLOYMENT.md    # Railway deployment guide
├── test_railway_deployment.py # Railway deployment testing
├── .gitignore               # Git ignore file
├── README.md                # This file
│
├── git_data_download/       # GitHub PR data collection
│   ├── requirements.txt     # GitHub API and data processing dependencies
│   └── README.md           # Data collection documentation
│
├── milvus_data_load/        # Vector database operations
│   ├── requirements.txt     # Milvus and embedding dependencies
│   └── README.md           # Vector database documentation
│
├── postgres_data_load/      # PostgreSQL analytics processing
│   ├── requirements.txt     # Database and analytics dependencies
│   └── README.md           # Analytics documentation
│
├── static/                  # Web assets and static files
│   ├── requirements.txt     # Static file serving dependencies
│   └── README.md           # Static files documentation
│
└── tests/                   # Test files and utilities
    └── README.md           # Testing documentation
```

## 🚀 Quick Start

### Railway Deployment (Recommended)

1. **Deploy to Railway**:
   ```bash
   # Follow RAILWAY_DEPLOYMENT.md for complete setup
   # 1. Connect GitHub repo to Railway
   # 2. Configure environment variables
   # 3. Deploy automatically
   ```

2. **Test Deployment**:
   ```bash
   python test_railway_deployment.py
   ```

### Local Development

1. **Install main dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install subfolder dependencies** (as needed):
   ```bash
   # For GitHub data collection
   pip install -r git_data_download/requirements.txt
   
   # For vector database operations
   pip install -r milvus_data_load/requirements.txt
   
   # For PostgreSQL analytics
   pip install -r postgres_data_load/requirements.txt
   
   # For static file serving
   pip install -r static/requirements.txt
   ```

3. **Run the application**:
   ```bash
   python main.py
   ```

## 📦 Dependency Structure

### Main Application (`requirements.txt`)
- **Core**: FastAPI, uvicorn, pydantic
- **Database**: PostgreSQL, Supabase, Milvus
- **AI**: OpenAI API
- **Utilities**: HTTP requests, logging, environment variables

### Git Data Download (`git_data_download/requirements.txt`)
- **GitHub API**: PyGithub
- **Data Processing**: pandas, numpy
- **AI Analysis**: OpenAI
- **Utilities**: HTTP requests, date handling, JSON processing

### Milvus Data Load (`milvus_data_load/requirements.txt`)
- **Vector Database**: pymilvus
- **Embeddings**: sentence-transformers, OpenAI
- **Data Processing**: pandas, numpy
- **Database**: PostgreSQL, Supabase

### Postgres Data Load (`postgres_data_load/requirements.txt`)
- **Database**: PostgreSQL, Supabase, SQLAlchemy
- **Data Processing**: pandas, numpy
- **AI Analysis**: OpenAI
- **Vector Operations**: pymilvus

### Static Files (`static/requirements.txt`)
- **Web Framework**: FastAPI
- **Utilities**: Environment variables
- **Development**: Testing and formatting tools

## 🔧 Environment Variables

### Required for Main Application
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

### Additional for Data Processing
```bash
# GitHub API (for git_data_download)
GITHUB_TOKEN=your_github_token

# Database (for postgres_data_load)
DATABASE_URL=your_database_url
```

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page with navigation |
| `/health` | GET | Health check and status |
| `/engineering-lens` | GET | Engineer Lens analytics page |
| `/what-shipped` | GET | What Shipped tracking page |
| `/api/engineers` | GET | Engineers data API |
| `/api/engineer-metrics` | GET | Engineer metrics API |
| `/api/what-shipped-data` | GET | What shipped data API |
| `/api/what-shipped-summary` | GET | What shipped summary API |
| `/api/what-shipped-authors` | GET | What shipped authors API |
| `/docs` | GET | Interactive API documentation |

## 🧪 Testing

### Railway Deployment Testing
```bash
python test_railway_deployment.py
```

### Local Testing
```bash
# Test main application
python -m pytest tests/

# Test specific modules
python -m pytest git_data_download/tests/
python -m pytest milvus_data_load/tests/
python -m pytest postgres_data_load/tests/
```

## 📊 Data Pipeline

1. **GitHub Data Collection** (`git_data_download/`)
   - Collect PR data from GitHub API
   - Process and enrich with AI analysis
   - Store in structured format

2. **Vector Database Loading** (`milvus_data_load/`)
   - Generate embeddings for PR content
   - Load into Milvus for semantic search
   - Index for fast retrieval

3. **Analytics Processing** (`postgres_data_load/`)
   - Process data for analytics dashboards
   - Generate Engineer Lens metrics
   - Create What Shipped summaries

4. **Web Application** (`main.py`)
   - Serve web interface
   - Provide API endpoints
   - Handle user interactions

## 🔍 Troubleshooting

### Common Issues

1. **Missing Dependencies**:
   ```bash
   # Install all subfolder dependencies
   pip install -r */requirements.txt
   ```

2. **Environment Variables**:
   ```bash
   # Check environment setup
   python -c "import os; print('MILVUS_URL:', os.getenv('MILVUS_URL'))"
   ```

3. **Database Connections**:
   ```bash
   # Test database connectivity
   python -c "import psycopg2; print('PostgreSQL available')"
   ```

### Debug Commands

```bash
# Check Python version
python --version

# Verify dependencies
pip list

# Test health endpoint
curl http://localhost:8000/health

# Check logs
tail -f logs/app.log
```

## 📈 Performance

- **Cold Start**: ~2-5 seconds (Railway)
- **Response Time**: <100ms for simple endpoints
- **Memory Usage**: ~50-100MB
- **Vector Search**: <500ms for semantic queries

## 🔐 Security

- Environment variables for all secrets
- Input validation with Pydantic
- CORS configuration for web access
- Database connection pooling
- Rate limiting on API endpoints

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Install dependencies for your module
4. Make your changes
5. Test thoroughly
6. Submit a pull request

## 📞 Support

- **Documentation**: Check individual README files in subfolders
- **Issues**: Create GitHub issues for bugs or feature requests
- **Deployment**: Follow `RAILWAY_DEPLOYMENT.md` for deployment help

---

**Happy analyzing! 🚀** 