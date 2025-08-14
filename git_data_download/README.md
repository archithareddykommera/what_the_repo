# 🔽 git_data_download/

**Purpose**: Collects comprehensive pull request data from GitHub repositories with AI-powered analysis.

## 📋 Overview

This directory contains the GitHub PR data collection system that fetches pull request information from GitHub repositories and enhances it with AI-powered analysis including summaries and risk assessments.

## 🗂️ Files

- `github_pr_collector.py` - Main data collection script

## ✨ Features

### 🔍 Complete PR Data Collection
- **Metadata**: PR ID, number, title, description, timestamps
- **Status Tracking**: Open, closed, merged states
- **User Information**: Authors, assignees, reviewers
- **File Changes**: Detailed file-level information
- **Statistics**: Additions, deletions, changed files

### 🤖 AI-Powered Analysis
- **File Summaries**: AI-generated summaries of file changes using OpenAI GPT
- **PR Summaries**: Comprehensive PR-level analysis
- **Risk Assessment**: File-level and PR-level risk scoring (0-10)
- **Feature Classification**: Automatic feature detection and labeling

### 📊 Enhanced File Information
- **Language Detection**: Automatic programming language identification
- **File Classification**: Source code, config, docs, tests, binary files
- **Change Analysis**: Additions, deletions, net changes
- **Content Processing**: Post-change content extraction

### ⚠️ Risk Assessment System
- **File-Level Scoring**: Individual file risk assessment
- **PR-Level Aggregation**: Weighted risk scoring across files
- **High-Risk Detection**: Automatic flagging of dangerous changes
- **Confidence Scoring**: Reliability indicators for assessments

## 🚀 Usage

### Prerequisites

```bash
# Set environment variables
export GITHUB_TOKEN="your_github_token"
export OPENAI_API_KEY="your_openai_api_key"
```

### Basic Usage

```bash
# Collect all PRs from a repository
python github_pr_collector.py owner/repo --state all --output pr_data.json

# Collect only open PRs
python github_pr_collector.py owner/repo --state open --output open_prs.json

# Collect only closed PRs
python github_pr_collector.py owner/repo --state closed --output closed_prs.json
```

### Command Line Options

- `owner/repo`: Repository name in format "owner/repo"
- `--state`: PR state filter (open, closed, all)
- `--output`: Output JSON filename
- `--limit`: Maximum number of PRs to collect (optional)

## 📊 Output Structure

The script generates a comprehensive JSON file with:

### Summary Statistics
- Total PRs, open/closed/merged counts
- File statistics and language distribution
- Risk assessment summaries
- Feature classification statistics

### Pull Request Data
- Complete PR metadata
- File-level information with AI summaries
- Risk assessments for files and PRs
- Feature classification and descriptions

### File Information
- Language detection and classification
- Change statistics and content
- AI-generated summaries
- Risk assessment with scoring and reasons

## ⚙️ Configuration

### Environment Variables
- `GITHUB_TOKEN`: GitHub personal access token
- `OPENAI_API_KEY`: OpenAI API key for AI analysis

### Rate Limiting
- Respects GitHub API rate limits
- Built-in delays between requests
- Handles rate limit errors gracefully

## 🔧 Risk Assessment Rules

### File-Level Scoring (0-10)
- **Size**: +0 (≤49 lines), +1 (50-199), +2 (200-599), +3 (≥600)
- **Security**: +2 for auth/ACL/PII/crypto/secrets
- **Schema Changes**: +3 for SQL/DDL changes
- **API Changes**: +3 for API surface modifications
- **Validation**: +2 for guard/validation removal
- **Tests**: -2 for test-only files, -1 for tests added elsewhere

### PR-Level Aggregation
- Weighted average by file change size
- Hard conditions for high-risk changes
- Test coverage adjustments
- Confidence scoring

## 🧪 Testing

```bash
# Test with limited PRs
python github_pr_collector.py owner/repo --state all --output test_data.json

# Verify output structure
python -c "import json; data=json.load(open('test_data.json')); print(f'PRs: {len(data[\"pull_requests\"])}')"
```

## 📈 Performance

- **Rate Limiting**: Respects GitHub API limits
- **Batch Processing**: Efficient handling of large repositories
- **Memory Management**: Processes files in chunks
- **Error Handling**: Graceful degradation for API failures

## 🔍 Example Output

```json
{
  "summary": {
    "total_prs": 1000,
    "merged_prs": 900,
    "file_statistics": {
      "total_files_changed": 5000,
      "languages_distribution": {
        "TypeScript": 2000,
        "JavaScript": 1500
      }
    },
    "risk_assessment_summary": {
      "total_high_risk_files": 150,
      "average_risk_score": 3.2
    }
  },
  "pull_requests": [
    {
      "pr_id": 123456789,
      "title": "Add new authentication system",
      "files": [
        {
          "filename": "src/auth.ts",
          "ai_summary": "Added comprehensive authentication system...",
          "risk_assessment": {
            "risk_score_file": 7.5,
            "high_risk_flag": true,
            "reasons": ["Authentication changes", "Security-sensitive code"]
          }
        }
      ]
    }
  ]
}
```

## 🆘 Troubleshooting

### Common Issues
1. **Missing GitHub Token**: Set `GITHUB_TOKEN` environment variable
2. **Rate Limiting**: Script automatically handles rate limits
3. **Large Repositories**: Use `--limit` option for testing
4. **API Errors**: Check repository permissions and token scope

### Error Messages
- `401 Unauthorized`: Check GitHub token validity
- `403 Forbidden`: Verify repository access permissions
- `404 Not Found`: Check repository name format

## 📚 Next Steps

After collecting data, you can:
1. Load to Milvus for vector search (`../milvus_data_load/`)
2. Process for analytics (`../postgres_data_load/`)
3. Use in the web application (`../main.py`)

---

**Happy collecting! 🎉**
