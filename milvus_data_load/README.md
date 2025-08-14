# 🔽 milvus_data_load/

**Purpose**: Loads processed PR data into Milvus vector database for semantic search and analysis.

## 📋 Overview

This directory contains the Milvus data loading system that takes processed GitHub PR data and creates vector embeddings for semantic search capabilities. It transforms PR data into searchable vectors using OpenAI's embedding models.

## 🗂️ Files

- `load_to_milvus.py` - Vector database loader script

## ✨ Features

### 🔢 Vector Embeddings
- **3072-Dimensional Vectors**: Using OpenAI's text-embedding-3-large model
- **Multiple Text Types**: Creates separate embeddings for different content types
- **Smart Content Processing**: Handles content limits and text extraction
- **Batch Processing**: Efficient batch insertion with configurable sizes

### 📝 Content Types
- **title_body**: PR title and description combined
- **pr_summary**: AI-generated PR summary
- **code_chunk**: Individual function/block definitions from changed files

### 🧠 Smart Processing
- **Function Extraction**: Language-specific pattern matching for code blocks
- **Content Limits**: Respects 16,384 character content limit
- **Status Handling**: Different processing for merged vs closed PRs
- **Rate Limiting**: Built-in API call management

## 🚀 Usage

### Prerequisites

```bash
# Set environment variables
export MILVUS_URL="https://your-cluster.zillizcloud.com"
export MILVUS_TOKEN="your_milvus_token"
export OPENAI_API_KEY="your_openai_api_key"
export COLLECTION_NAME="github_prs"  # optional, defaults to github_prs
```

### Basic Usage

```bash
# Load data to Milvus
python load_to_milvus.py path/to/pr_data.json

# With custom collection name
python load_to_milvus.py path/to/pr_data.json --collection my_collection

# With custom batch size
python load_to_milvus.py path/to/pr_data.json --batch-size 50
```

### Command Line Options

- `json_file`: Path to JSON file with PR data (required)
- `--url`: Milvus URL (or set MILVUS_URL env var)
- `--token`: Milvus API token (or set MILVUS_TOKEN env var)
- `--collection`: Collection name (or set COLLECTION_NAME env var, default: github_prs)
- `--batch-size`: Number of rows to insert per batch (default: 100)

## 🗄️ Milvus Schema

The script creates a collection with the following schema:

| Field Name | Type | Description |
|------------|------|-------------|
| primary_key | INT64 | Auto-incrementing primary key |
| vector | FLOAT_VECTOR(3072) | Embedding vector |
| repo_name | VARCHAR(256) | Repository name (e.g., "org/repo") |
| file_path | VARCHAR(256) | File path for code chunks |
| repo_id | INT64 | GitHub repository ID |
| pr_id | INT64 | GitHub PR number |
| function_name | VARCHAR(128) | Function/block name (empty for summaries) |
| change_type | VARCHAR(32) | added/modified/deleted |
| text_type | VARCHAR(32) | title_body/pr_summary/code_chunk |
| content | VARCHAR(16384) | Full text content |
| status | VARCHAR(64) | open/closed/merged |
| author | VARCHAR(128) | GitHub username |
| created_at | INT64 | UNIX epoch seconds |
| merged_at | INT64 | UNIX epoch seconds (0 if not merged) |
| is_merged | BOOL | Merge status flag |
| is_closed | BOOL | Close status flag |
| author_id | VARCHAR(128) | GitHub user ID |

## 📊 Data Processing Rules

### Row Generation Logic

1. **Title + Body**: 1 row per PR (always created)
2. **PR Summary**: 1 row per PR (if AI summary available)
3. **Code Chunks**: 0-N rows per PR (one per function/block)

### Content Processing

- **Text Truncation**: Content limited to 16,384 characters
- **Function Extraction**: Uses language-specific patterns
- **Empty Content**: Skips rows with empty content
- **Encoding**: Handles UTF-8 encoding properly

### Supported Languages for Function Extraction

- **JavaScript/TypeScript**: Function declarations, arrow functions, classes
- **Python**: Function definitions, class definitions
- **Java**: Method declarations, class definitions
- **C++**: Function definitions, class definitions
- **Go**: Function declarations, method definitions
- **Ruby**: Method definitions, class definitions
- **PHP**: Function definitions, class definitions

## ⚙️ Configuration

### Environment Variables
- `MILVUS_URL`: Milvus/Zilliz Cloud cluster URL
- `MILVUS_TOKEN`: Milvus API authentication token
- `OPENAI_API_KEY`: OpenAI API key for embeddings
- `COLLECTION_NAME`: Milvus collection name (default: github_prs)

### Performance Settings
- **Batch Size**: Configurable batch insertion (default: 100)
- **Rate Limiting**: Built-in OpenAI API rate limiting
- **Memory Management**: Efficient memory usage for large datasets
- **Error Handling**: Graceful error recovery and logging

## 🧪 Testing

### Test with Sample Data

```bash
# Test with a small dataset
python load_to_milvus.py ../test_github_pr_collector_output.json --batch-size 10

# Verify collection creation
python -c "
from pymilvus import connections, Collection
connections.connect(uri='your_milvus_url', token='your_token')
collection = Collection('github_prs')
print(f'Collection exists: {collection.is_empty}')
"
```

### Verify Embeddings

```bash
# Check collection statistics
python -c "
from pymilvus import connections, Collection
connections.connect(uri='your_milvus_url', token='your_token')
collection = Collection('github_prs')
collection.load()
print(f'Total rows: {collection.num_entities}')
"
```

## 📈 Performance

### Optimization Tips
- **Batch Size**: Adjust based on your Milvus cluster capacity
- **Rate Limiting**: Respect OpenAI API limits
- **Memory Usage**: Monitor memory consumption for large datasets
- **Network**: Ensure stable connection to Milvus cluster

### Expected Performance
- **Small Dataset** (< 1K PRs): 5-10 minutes
- **Medium Dataset** (1K-10K PRs): 30-60 minutes
- **Large Dataset** (> 10K PRs): 2-4 hours

## 🔍 Example Output

### Collection Statistics
```
✅ Collection 'github_prs' created successfully
📊 Collection schema:
  - primary_key: INT64 (Primary Key)
  - vector: FLOAT_VECTOR(3072)
  - repo_name: VARCHAR(256)
  - file_path: VARCHAR(256)
  - pr_id: INT64
  - text_type: VARCHAR(32)
  - content: VARCHAR(16384)
  - status: VARCHAR(64)
  - author: VARCHAR(128)

📈 Processing statistics:
  - Total PRs processed: 1,000
  - Total rows created: 5,250
  - Title/body rows: 1,000
  - Summary rows: 950
  - Code chunk rows: 3,300
  - Processing time: 45 minutes
```

## 🆘 Troubleshooting

### Common Issues

1. **Connection Errors**
   ```
   Error: Failed to connect to Milvus
   Solution: Check MILVUS_URL and MILVUS_TOKEN
   ```

2. **OpenAI API Errors**
   ```
   Error: OpenAI API rate limit exceeded
   Solution: Script automatically handles rate limiting
   ```

3. **Memory Issues**
   ```
   Error: Out of memory
   Solution: Reduce batch size with --batch-size 50
   ```

4. **Collection Already Exists**
   ```
   Error: Collection already exists
   Solution: Use different collection name or delete existing
   ```

### Error Recovery
- **Automatic Retries**: Built-in retry logic for API failures
- **Partial Success**: Continues processing after individual failures
- **Logging**: Detailed logs for debugging
- **Progress Tracking**: Shows processing progress

## 📚 Next Steps

After loading data to Milvus, you can:
1. Use semantic search in the web application (`../main.py`)
2. Process analytics data (`../postgres_data_load/`)
3. Query vectors for similarity search

## 🔗 Related Files

- `../git_data_download/github_pr_collector.py` - Data collection
- `../main.py` - Web application with search
- `../requirements.txt` - Dependencies

---

**Happy vectorizing! 🚀**
