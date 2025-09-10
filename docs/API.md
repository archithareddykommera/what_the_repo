# What the Repo - API Documentation

**How to read this doc**: This document describes the public API endpoints, request/response formats, and provides examples for the What the Repo application.

## Base URL

```
https://your-railway-app.railway.app
```

## Authentication

All endpoints use service role authentication via environment variables. No API keys are required for public endpoints.

## Endpoints

### 1. Ask Repo-GPT

**Endpoint**: `POST /ask`

**Purpose**: Natural language Q&A about repository activity

**Request Body**:
```json
{
  "query": "What features shipped last month?",
  "repo_name": "optional-repo-name",
  "limit": 5
}
```

**Response**:
```json
{
  "results": [
    {
      "type": "feature",
      "title": "Add user authentication",
      "pr_number": 123,
      "author": "john-doe",
      "risk_score": 3.2,
      "feature_rule": "label-allow",
      "feature_confidence": 0.9,
      "created_at": "2024-01-15T10:30:00Z",
      "merged_at": "2024-01-16T14:20:00Z",
      "explanation": "This PR implements user authentication using OAuth2..."
    }
  ],
  "query_type": "hybrid",
  "time_range": "last month",
  "total_results": 15
}
```

**Example Queries**:
- "What features shipped last month?"
- "File that changed most last week"
- "How many PRs were merged by john-doe?"
- "Show me high risk changes in the last 30 days"

### 2. Get Engineer Metrics

**Endpoint**: `GET /api/engineer-metrics`

**Purpose**: Retrieve engineer analytics and insights

**Query Parameters**:
- `username` (required): Engineer's GitHub username
- `window_days` (optional): Time window (7, 15, 30, 60, 90, 999 for all_time)
- `repo_name` (optional): Specific repository filter

**Response**:
```json
{
  "engineer": {
    "username": "john-doe",
    "display_name": "John Doe",
    "avatar_url": "https://github.com/john-doe.png"
  },
  "metrics": {
    "prs_submitted": 25,
    "prs_merged": 22,
    "high_risk_prs": 3,
    "high_risk_rate": 13.6,
    "lines_changed": 15420,
    "features_merged": 8
  },
  "file_ownership": [
    {
      "file_path": "src/auth/authentication.py",
      "ownership_pct": 85.2,
      "author_lines": 1250,
      "total_lines": 1468,
      "last_touched": "2024-01-20T16:45:00Z"
    }
  ],
  "recent_prs": [
    {
      "pr_number": 456,
      "title": "Fix authentication bug",
      "risk_score": 2.1,
      "feature_rule": "excluded",
      "merged_at": "2024-01-20T14:30:00Z"
    }
  ]
}
```

### 3. Get What Shipped Data

**Endpoint**: `GET /api/what-shipped`

**Purpose**: Retrieve PR data for What Shipped page

**Query Parameters**:
- `repo_name` (optional): Repository filter
- `time_range` (optional): Time filter (e.g., "last 30 days")
- `author` (optional): Author filter
- `risk_level` (optional): Risk filter (high, medium, low)
- `limit` (optional): Number of results (default: 50, max: 1000)

**Response**:
```json
{
  "prs": [
    {
      "pr_number": 789,
      "title": "Implement payment processing",
      "author": "jane-smith",
      "created_at": "2024-01-18T09:15:00Z",
      "merged_at": "2024-01-19T11:30:00Z",
      "is_merged": true,
      "additions": 450,
      "deletions": 23,
      "changed_files": 12,
      "risk_score": 6.8,
      "high_risk": false,
      "feature_rule": "label-allow",
      "feature_confidence": 0.9,
      "risk_reasons": ["payment processing", "external API integration"],
      "top_risky_files": [
        {
          "file_path": "src/payment/processor.py",
          "risk": 7.2,
          "lines": 320,
          "status": "modified"
        }
      ]
    }
  ],
  "summary": {
    "total_prs": 45,
    "features": 12,
    "high_risk": 8,
    "merged": 42
  },
  "filters": {
    "time_range": "last 30 days",
    "repo_name": "my-app",
    "author": null,
    "risk_level": null
  }
}
```

### 4. Get Repository List

**Endpoint**: `GET /api/repositories`

**Purpose**: Get list of available repositories

**Response**:
```json
{
  "repositories": [
    {
      "name": "my-app",
      "description": "Main application repository",
      "pr_count": 156,
      "last_updated": "2024-01-20T16:45:00Z"
    },
    {
      "name": "my-app-api",
      "description": "API service repository",
      "pr_count": 89,
      "last_updated": "2024-01-19T14:20:00Z"
    }
  ]
}
```

### 5. Health Check

**Endpoint**: `GET /`

**Purpose**: Application health check

**Response**:
```json
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

## Error Responses

### Standard Error Format
```json
{
  "error": "Error message",
  "detail": "Detailed error information",
  "status_code": 400
}
```

### Common Error Codes
- `400 Bad Request`: Invalid query parameters or request body
- `404 Not Found`: Repository or engineer not found
- `500 Internal Server Error`: Server-side processing error
- `503 Service Unavailable`: External service (Milvus, Supabase) unavailable

## Query Routing Examples

### Direct Queries
```json
{
  "query": "How many PRs were merged last week?",
  "route": "direct",
  "object": "prs",
  "metric": "count"
}
```

### Hybrid Queries
```json
{
  "query": "Show me authentication changes in the last month",
  "route": "hybrid",
  "object": "features",
  "metric": "list",
  "semantic_terms": ["auth", "authentication"]
}
```

### Vector Queries
```json
{
  "query": "What are the most complex changes made recently?",
  "route": "vector",
  "object": "prs",
  "metric": "explain"
}
```

## Rate Limits

- **GitHub API**: 5000 requests/hour (authenticated)
- **OpenAI API**: Token-based rate limits
- **Application**: No explicit rate limiting configured

## Pagination

For endpoints returning lists, pagination is handled via:
- `limit` parameter: Number of results (default: 50, max: 1000)
- `offset` parameter: Skip N results (for large datasets)

## Time Range Parsing

The API supports natural language time parsing:
- "last week", "last month", "last 30 days"
- "yesterday", "today", "this week"
- "2024-01-01 to 2024-01-31"

## Gaps & Assumptions

### Missing Features
- No API versioning strategy
- No bulk operations endpoints
- No real-time updates (WebSocket)
- No explicit caching headers

### Assumptions
- Single-tenant architecture
- GitHub as primary data source
- All timestamps in UTC
- JSON responses only
