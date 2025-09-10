# Router System Explanation

## Overview

The router system in WhatTheRepo is an **intelligent query classification and routing engine** that analyzes natural language queries and determines the optimal search strategy. It acts as the brain of the search system, making intelligent decisions about how to process each user query to provide the most relevant and efficient results.

## Architecture

```mermaid
graph TB
    A[User Query] --> B[Router Engine]
    B --> C{Pattern Analysis}
    C --> D[Direct Route]
    C --> E[Hybrid Route]
    C --> F[Vector Route]
    
    D --> G[Direct Handlers]
    E --> H[Hybrid Handlers]
    F --> I[Vector Handlers]
    
    G --> J[Database Queries]
    H --> K[Semantic + Structured Search]
    I --> L[Vector Search + LLM]
    
    J --> M[Search Results]
    K --> M
    L --> M
    
    M --> N[Formatted Response]
    
    style B fill:#e1f5fe
    style C fill:#fff3e0
    style D fill:#e8f5e8
    style E fill:#fff8e1
    style F fill:#fce4ec
```

## Core Components

### 1. Main Router Function (`route_query`)

The primary entry point that processes all queries:

```python
def route_query(q: str) -> Dict[str, Any]:
    """
    Route a query to the appropriate search strategy.
    
    Returns:
        Dictionary with routing information including:
        - route: "direct", "hybrid", or "vector"
        - object: "prs", "features", or "files"
        - metric: "list", "top", "count", or "explain"
        - semantic_terms: List of semantic terms for hybrid/vector search
    """
```

### 2. Route Determination Functions

- `determine_direct_route()` - Handles structured, specific queries
- `determine_hybrid_route()` - Handles topic-based queries with semantic search
- `determine_vector_route()` - Handles explanatory and analytical queries

### 3. Helper Functions

- `extract_semantic_terms()` - Extracts technical terms from queries
- `is_explanation_query()` - Identifies explanation requests
- `is_count_query()` - Identifies count requests
- `is_top_query()` - Identifies top/most requests

## Detailed Flow Diagram

```mermaid
flowchart TD
    A[User Query Input] --> B[Convert to Lowercase]
    B --> C{Check Direct Patterns}
    
    C -->|Match Found| D[determine_direct_route]
    C -->|No Match| E{Check Hybrid Patterns}
    
    E -->|Match Found| F[determine_hybrid_route]
    E -->|No Match| G{Check File Patterns}
    
    G -->|Match Found| H[Return Hybrid File Route]
    G -->|No Match| I{Check File Keywords}
    
    I -->|Match Found| J[determine_hybrid_route]
    I -->|No Match| K{Check Vector Patterns}
    
    K -->|Match Found| L[determine_vector_route]
    K -->|No Match| M[Default to Hybrid]
    
    D --> N[Return Direct Route Plan]
    F --> O[Return Hybrid Route Plan]
    H --> P[Return File-Specific Plan]
    J --> Q[Return Hybrid Route Plan]
    L --> R[Return Vector Route Plan]
    M --> S[Return Default Hybrid Plan]
    
    N --> T[Add Time & Filters]
    O --> T
    P --> T
    Q --> T
    R --> T
    S --> T
    
    T --> U[Execute Route Handler]
    U --> V[Return Search Results]
    
    style A fill:#e3f2fd
    style B fill:#f3e5f5
    style C fill:#fff3e0
    style D fill:#e8f5e8
    style E fill:#fff8e1
    style F fill:#fce4ec
    style G fill:#f1f8e9
    style H fill:#fff8e1
    style I fill:#f1f8e9
    style J fill:#fff8e1
    style K fill:#fce4ec
    style L fill:#fce4ec
    style M fill:#fff8e1
    style T fill:#e0f2f1
    style U fill:#e8eaf6
    style V fill:#e8f5e8
```

## Route Types

### 1. Direct Route

**Purpose**: Handle specific, structured queries that can be answered with direct database queries.

**Patterns Recognized**:
```python
direct_patterns = [
    r'\b(count|top|most|list|merged)\b',
    r'features?\s+shipped',
    r'what\s+was\s+shipped',
    r'file\s+that\s+changed',
    r'how\s+many',
    r'pr\s+\d+',
    r'\b(riskiest|high\s+risk|most\s+risky)\b',
    r'\b(largest|biggest|most\s+changes)\b'
]
```

**Example Queries**:
- "What was shipped in the last two weeks?"
- "Show me the top 10 riskiest PRs"
- "Count total PRs merged this month"
- "Find changes by author alice"
- "PR #123 summary"

**Flow Diagram**:
```mermaid
flowchart TD
    A[Direct Query] --> B{Feature Query?}
    B -->|Yes| C[Return: direct/features/list]
    B -->|No| D{Count Query?}
    D -->|Yes| E[Return: direct/prs/count]
    D -->|No| F{Risk Query?}
    F -->|Yes| G[Extract Limit]
    G --> H[Return: direct/prs/riskiest]
    F -->|No| I{Size Query?}
    I -->|Yes| J[Extract Limit]
    J --> K[Return: direct/prs/largest]
    I -->|No| L{PR Number?}
    L -->|Yes| M[Extract PR Number]
    M --> N[Return: direct/prs/list]
    L -->|No| O{Author Query?}
    O -->|Yes| P[Extract Author]
    P --> Q[Return: direct/prs/list]
    O -->|No| R[Return: direct/prs/list]
    
    style A fill:#e8f5e8
    style C fill:#c8e6c9
    style E fill:#c8e6c9
    style H fill:#c8e6c9
    style K fill:#c8e6c9
    style N fill:#c8e6c9
    style Q fill:#c8e6c9
    style R fill:#c8e6c9
```

### 2. Hybrid Route

**Purpose**: Handle topic-based queries that combine semantic search with structured filters.

**Patterns Recognized**:
```python
hybrid_patterns = [
    r'\b(auth|authentication|authorization)\b',
    r'\b(payment|billing|invoice)\b',
    r'\b(pipeline|ci|cd|deploy)\b',
    r'\b(security|vulnerability|risk)\b',
    r'\b(database|sql|query)\b',
    r'\b(api|endpoint|route)\b',
    r'\b(ui|ux|frontend|backend)\b',
    r'\b(test|testing|tested)\b',
    r'\b(performance|optimization|speed)\b',
    r'\b(error|bug|fix|issue)\b'
]
```

**Example Queries**:
- "Find authentication changes"
- "Show me database schema changes"
- "What API changes were made?"
- "Find performance optimizations"

**Flow Diagram**:
```mermaid
flowchart TD
    A[Hybrid Query] --> B{File-Centric?}
    B -->|Yes| C[Return: hybrid/files/list]
    B -->|No| D{Feature-Centric?}
    D -->|Yes| E[Return: hybrid/features/list]
    D -->|No| F[Return: hybrid/prs/list]
    
    style A fill:#fff8e1
    style C fill:#fff9c4
    style E fill:#fff9c4
    style F fill:#fff9c4
```

### 3. Vector Route

**Purpose**: Handle explanatory and analytical queries that require semantic understanding.

**Patterns Recognized**:
```python
vector_patterns = [
    r'\bwhy\b',
    r'\bexplain\b',
    r'\bhow\s+does\b',
    r'\bwhat\s+is\b',
    r'\brisky\s+because\b',
    r'\bshow\s+me\b',
    r'\btell\s+me\b',
    r'\bdescribe\b',
    r'\bunderstand\b',
    r'\bstreaming\s+features?\b',
    r'\bcomplex\s+changes?\b',
    r'\bimpact\s+of\b'
]
```

**Example Queries**:
- "Why is this PR risky?"
- "Explain the impact of these changes"
- "How does this authentication system work?"
- "Tell me about the streaming features"

**Flow Diagram**:
```mermaid
flowchart TD
    A[Vector Query] --> B{Explanation Query?}
    B -->|Yes| C[Return: vector/prs/explain]
    B -->|No| D{Risk Analysis?}
    D -->|Yes| E[Return: vector/files/explain]
    D -->|No| F[Return: vector/prs/explain]
    
    style A fill:#fce4ec
    style C fill:#f8bbd9
    style E fill:#f8bbd9
    style F fill:#f8bbd9
```

## File-Specific Routing

Special handling for file-specific queries:

```mermaid
flowchart TD
    A[File Query] --> B{File Pattern Match?}
    B -->|Yes| C[Extract Filename]
    C --> D[Return: hybrid/files/list]
    D --> E[Add specific_file parameter]
    B -->|No| F{File Keywords?}
    F -->|Yes| G[Return: hybrid/files/list]
    F -->|No| H[Continue to other patterns]
    
    style A fill:#f1f8e9
    style C fill:#c5e1a5
    style D fill:#c5e1a5
    style E fill:#c5e1a5
    style G fill:#c5e1a5
```

**Patterns**:
```python
file_patterns = [
    r'show\s+changes?\s+in\s+([a-zA-Z0-9_.-]+)',
    r'changes?\s+to\s+([a-zA-Z0-9_.-]+)',
    r'changes?\s+in\s+([a-zA-Z0-9_.-]+)',
    r'file\s+([a-zA-Z0-9_.-]+)',
    r'([a-zA-Z0-9_.-]+\.(py|js|java|cpp|c|h|ts|jsx|tsx|html|css|sql|json|yaml|yml|md|txt))'
]
```

## Parameter Extraction

The router automatically extracts various parameters from queries:

### Limit Extraction
```python
# From: "Show me the top 5 riskiest PRs"
top_match = re.search(r'top\s+(\d+)', query_lower)
limit = int(top_match.group(1)) if top_match else 20
# Result: limit = 5
```

### Author Extraction
```python
# From: "Changes made by john_doe"
author_match = re.search(r'changes?\s+(made|done)\s+by\s+([a-zA-Z0-9_-]+)', query_lower)
author = author_match.group(2) if author_match else None
# Result: author = "john_doe"
```

### PR Number Extraction
```python
# From: "PR #123" or "PR 456"
pr_match = re.search(r'pr\s+(?:#\s*)?(\d+)', query_lower)
pr_number = int(pr_match.group(1)) if pr_match else None
# Result: pr_number = 123 or 456
```

## Semantic Terms Extraction

The router extracts technical terms for hybrid and vector searches:

```python
technical_terms = [
    'auth', 'authentication', 'authorization', 'login', 'logout',
    'payment', 'billing', 'invoice', 'transaction', 'money',
    'pipeline', 'ci', 'cd', 'deploy', 'deployment', 'build',
    'security', 'vulnerability', 'risk', 'secure', 'encryption',
    'database', 'sql', 'query', 'schema', 'migration', 'table',
    'api', 'endpoint', 'route', 'rest', 'graphql', 'webhook',
    'ui', 'ux', 'frontend', 'backend', 'interface', 'component',
    'test', 'testing', 'tested', 'unit', 'integration', 'e2e',
    'performance', 'optimization', 'speed', 'fast', 'slow',
    'error', 'bug', 'fix', 'issue', 'problem', 'crash',
    'streaming', 'real-time', 'async', 'concurrent', 'parallel',
    'complex', 'complicated', 'refactor', 'cleanup', 'simplify'
]
```

## Integration with Main Application

### Search Endpoint Integration

```python
@app.post("/search")
async def search_prs(request: SearchRequest):
    # Step 1: Route the query
    plan = route_query(request.query)
    
    # Step 2: Parse time window
    start, end = parse_time(request.query)
    plan["time"] = {"start": start, "end": end}
    plan["filters"] = {"repo": request.repo_name}
    
    # Step 3: Execute based on route
    if plan["route"] == "direct":
        if plan["object"] == "features":
            data = direct_features_list(request.repo_name, start, end, None, request.limit)
        elif plan["metric"] == "riskiest":
            data = direct_prs_list(request.repo_name, start, end, sort_by_riskiest=True)
            
    elif plan["route"] == "hybrid":
        if plan["object"] == "features":
            data = hybrid_features(request.repo_name, start, end, terms, request.limit)
            
    elif plan["route"] == "vector":
        data = vector_explanation(request.repo_name, start, end, terms, request.limit)
```

### Handler Mapping

```mermaid
graph LR
    A[Router Plan] --> B{Route Type}
    B -->|Direct| C[Direct Handlers]
    B -->|Hybrid| D[Hybrid Handlers]
    B -->|Vector| E[Vector Handlers]
    
    C --> F[direct_prs_list]
    C --> G[direct_features_list]
    C --> H[direct_top_file_by_lines]
    C --> I[direct_pr_count]
    C --> J[direct_top_prs_by_risk]
    
    D --> K[hybrid_features]
    D --> L[hybrid_risky_files]
    D --> M[hybrid_auth_features]
    D --> N[hybrid_payment_features]
    D --> O[hybrid_security_changes]
    
    E --> P[vector_explanation]
    E --> Q[vector_risk_analysis]
    E --> R[vector_why_risky]
    E --> S[vector_streaming_features]
    E --> T[vector_complex_changes]
    
    style A fill:#e3f2fd
    style B fill:#fff3e0
    style C fill:#e8f5e8
    style D fill:#fff8e1
    style E fill:#fce4ec
```

## Example Query Processing

### Example 1: Direct Route

**Input Query**: `"Show me the top 10 riskiest PRs from last month"`

**Processing Flow**:
```mermaid
flowchart TD
    A["Show me the top 10 riskiest PRs from last month"] --> B[Convert to lowercase]
    B --> C[Check direct patterns]
    C --> D[Match: 'top' and 'riskiest']
    D --> E[determine_direct_route]
    E --> F[Extract limit: 10]
    F --> G[Return plan]
    G --> H[Add time parsing]
    H --> I[Execute direct_prs_list with sort_by_riskiest=True]
    I --> J[Return top 10 riskiest PRs]
    
    style A fill:#e3f2fd
    style D fill:#e8f5e8
    style F fill:#c8e6c9
    style G fill:#c8e6c9
    style I fill:#c8e6c9
    style J fill:#e8f5e8
```

**Router Output**:
```python
{
    "route": "direct",
    "object": "prs",
    "metric": "riskiest",
    "limit": 10,
    "semantic_terms": [],
    "time": {"start": timestamp, "end": timestamp}
}
```

### Example 2: Hybrid Route

**Input Query**: `"Find authentication changes in the last week"`

**Processing Flow**:
```mermaid
flowchart TD
    A["Find authentication changes in the last week"] --> B[Convert to lowercase]
    B --> C[Check direct patterns - No match]
    C --> D[Check hybrid patterns]
    D --> E[Match: 'auth']
    E --> F[determine_hybrid_route]
    F --> G[Extract semantic terms: ['auth']]
    G --> H[Return plan]
    H --> I[Add time parsing]
    I --> J[Execute hybrid_auth_features]
    J --> K[Return authentication-related PRs]
    
    style A fill:#e3f2fd
    style E fill:#fff8e1
    style G fill:#fff9c4
    style H fill:#fff9c4
    style J fill:#fff9c4
    style K fill:#fff8e1
```

**Router Output**:
```python
{
    "route": "hybrid",
    "object": "features",
    "metric": "list",
    "semantic_terms": ["auth"],
    "time": {"start": timestamp, "end": timestamp}
}
```

### Example 3: Vector Route

**Input Query**: `"Why is this PR risky?"`

**Processing Flow**:
```mermaid
flowchart TD
    A["Why is this PR risky?"] --> B[Convert to lowercase]
    B --> C[Check direct patterns - No match]
    C --> D[Check hybrid patterns - No match]
    D --> E[Check file patterns - No match]
    E --> F[Check vector patterns]
    F --> G[Match: 'why']
    G --> H[determine_vector_route]
    H --> I[Return plan]
    I --> J[Add time parsing]
    J --> K[Execute vector_explanation]
    K --> L[Return LLM-generated explanation]
    
    style A fill:#e3f2fd
    style G fill:#fce4ec
    style H fill:#f8bbd9
    style I fill:#f8bbd9
    style K fill:#f8bbd9
    style L fill:#fce4ec
```

**Router Output**:
```python
{
    "route": "vector",
    "object": "prs",
    "metric": "explain",
    "semantic_terms": ["Why is this PR risky?"],
    "time": {"start": timestamp, "end": timestamp}
}
```

## Performance Characteristics

### Pattern Matching Efficiency

The router uses **priority-based pattern matching** to ensure optimal performance:

1. **Direct patterns** (fastest) - Simple regex matches for structured queries
2. **Hybrid patterns** (medium) - Topic-based matching with semantic terms
3. **Vector patterns** (slowest) - Complex analysis requiring LLM processing

### Caching Strategy

```mermaid
flowchart LR
    A[Query Input] --> B[Pattern Cache]
    B --> C{Cached?}
    C -->|Yes| D[Return Cached Route]
    C -->|No| E[Pattern Analysis]
    E --> F[Store in Cache]
    F --> G[Return Route]
    
    style A fill:#e3f2fd
    style B fill:#e0f2f1
    style D fill:#c8e6c9
    style E fill:#fff3e0
    style F fill:#e0f2f1
    style G fill:#c8e6c9
```

## Error Handling

### Fallback Strategy

```mermaid
flowchart TD
    A[Query Input] --> B[Pattern Analysis]
    B --> C{Any Pattern Match?}
    C -->|Yes| D[Use Matched Route]
    C -->|No| E[Default to Hybrid]
    E --> F[Use Entire Query as Semantic Terms]
    F --> G[Return Generic Plan]
    
    style A fill:#e3f2fd
    style C fill:#fff3e0
    style D fill:#e8f5e8
    style E fill:#fff8e1
    style F fill:#fff9c4
    style G fill:#fff9c4
```

### Error Recovery

1. **Invalid Parameters**: Default to safe values (limit=20, no specific filters)
2. **Pattern Failures**: Fallback to hybrid route with full query
3. **Time Parsing Errors**: Use default time window (last 30 days)
4. **Handler Failures**: Return empty results with error message

## Debugging and Logging

### Router Debug Output

```python
print(f"🎯 Router Results:")
print(f"   Query: '{q}'")
print(f"   Route: {result['route']}")
print(f"   Object: {result['object']}")
print(f"   Metric: {result['metric']}")
print(f"   Semantic terms: {result.get('semantic_terms', [])}")
```

### Example Debug Output

```
🎯 Router Results:
   Query: 'Show me the top 5 riskiest PRs'
   Route: direct
   Object: prs
   Metric: riskiest
   Semantic terms: []
```

## Extensibility

### Adding New Patterns

To add new routing patterns:

1. **Add to pattern lists**:
```python
direct_patterns.append(r'\bnew_pattern\b')
hybrid_patterns.append(r'\bnew_topic\b')
vector_patterns.append(r'\bnew_analysis\b')
```

2. **Update determination functions**:
```python
def determine_direct_route(query: str) -> Dict[str, Any]:
    # Add new pattern handling
    if re.search(r'new_pattern', query_lower):
        return {
            "route": "direct",
            "object": "prs",
            "metric": "new_metric",
            "semantic_terms": []
        }
```

3. **Add corresponding handlers**:
```python
# In direct_handlers.py
def direct_new_metric(repo_name, start, end, limit):
    # Implementation for new metric
    pass
```

### Adding New Route Types

To add a new route type:

1. **Define new patterns**
2. **Create determination function**
3. **Add to main router logic**
4. **Create corresponding handlers**
5. **Update main application integration**

## Best Practices

### Pattern Design

1. **Use word boundaries** (`\b`) to avoid partial matches
2. **Order patterns by specificity** (most specific first)
3. **Use case-insensitive matching** for user-friendly queries
4. **Include variations** (singular/plural, synonyms)

### Performance Optimization

1. **Cache frequently used patterns**
2. **Use compiled regex patterns** for repeated matching
3. **Limit semantic terms extraction** to relevant domains
4. **Implement early exit** for obvious matches

### Maintainability

1. **Document pattern purposes** with comments
2. **Group related patterns** logically
3. **Use descriptive variable names**
4. **Add comprehensive logging** for debugging

## Conclusion

The router system provides a sophisticated, extensible foundation for intelligent query processing in WhatTheRepo. By combining pattern matching, parameter extraction, and semantic analysis, it ensures that each user query is processed by the most appropriate search strategy, optimizing both performance and result relevance.

The modular design allows for easy extension and maintenance, while the comprehensive logging and error handling ensure robust operation in production environments.
