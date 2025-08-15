#!/usr/bin/env python3
"""
Query router module for determining search strategy.
Routes queries to direct, hybrid, or vector retrieval based on content analysis.
"""

import re
from typing import Dict, List, Any, Optional

def route_query(q: str) -> Dict[str, Any]:
    """
    Route a query to the appropriate search strategy.
    
    Args:
        q: Natural language query string
        
    Returns:
        Dictionary with routing information including:
        - route: "direct", "hybrid", or "vector"
        - object: "prs", "features", or "files"
        - metric: "list", "top", "count", or "explain"
        - semantic_terms: List of semantic terms for hybrid/vector search
    """
    q_lower = q.lower()
    
    # Direct route patterns (scalar filters + client-side reduce)
    direct_patterns = [
        r'\b(count|top|most|list|merged)\b',
        r'features?\s+shipped',
        r'shipped\s+features?',
        r'what\s+was\s+shipped',
        r'what\s+shipped',
        r'changes?\s+last',
        r'changes?\s+(made|done)\s+by',
        r'file\s+that\s+changed',
        r'how\s+many',
        r'number\s+of',
        r'total\s+(prs?|changes?|features?)',
        r'prs?\s+merged',
        r'files?\s+modified',
        r'pr\s+\d+',
        r'summarize\s+pr\s+\d+',
        r'pr\s+#\s*\d+',
        r'summarize\s+pr\s+#\s*\d+',
        r'\b(largest|biggest|most\s+changes)\b',
        r'\b(riskiest|high\s+risk|most\s+risky)\b'
    ]
    
    # Check for direct route patterns
    for pattern in direct_patterns:
        if re.search(pattern, q_lower):
            return determine_direct_route(q_lower)
    
    # Hybrid route patterns (topic-based with semantic terms)
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
    
    # Check for hybrid route patterns
    semantic_terms = []
    for pattern in hybrid_patterns:
        match = re.search(pattern, q_lower)
        if match:
            semantic_terms.append(match.group(1))
    
    if semantic_terms:
        return determine_hybrid_route(q_lower, semantic_terms)
    
    # Check for specific file queries first (before vector patterns)
    # Look for patterns like "show changes in filename.py" or "changes to filename"
    file_patterns = [
        r'show\s+changes?\s+in\s+([a-zA-Z0-9_.-]+)',
        r'changes?\s+to\s+([a-zA-Z0-9_.-]+)',
        r'changes?\s+in\s+([a-zA-Z0-9_.-]+)',
        r'file\s+([a-zA-Z0-9_.-]+)',
        r'([a-zA-Z0-9_.-]+\.(py|js|java|cpp|c|h|ts|jsx|tsx|html|css|sql|json|yaml|yml|md|txt))'
    ]
    
    for pattern in file_patterns:
        match = re.search(pattern, q_lower)
        if match:
            filename = match.group(1)
            return {
                "route": "hybrid",
                "object": "files",
                "metric": "list",
                "semantic_terms": [filename],
                "specific_file": filename
            }
    
    # Check for general file-specific queries
    file_keywords = ['file', 'files', '.py', '.js', '.java', '.cpp', '.c', '.h', '.ts', '.jsx', '.tsx', '.html', '.css', '.sql', '.json', '.yaml', '.yml', '.md', '.txt']
    if any(keyword in q_lower for keyword in file_keywords):
        return determine_hybrid_route(q_lower, [q])
    
    # Vector route patterns (explanations, "why" questions, fuzzy asks)
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
    
    for pattern in vector_patterns:
        if re.search(pattern, q_lower):
            return determine_vector_route(q_lower)
    
    # Default to hybrid if no clear pattern
    result = determine_hybrid_route(q_lower, [q])
    
    print(f"🎯 Router Results:")
    print(f"   Query: '{q}'")
    print(f"   Route: {result['route']}")
    print(f"   Object: {result['object']}")
    print(f"   Metric: {result['metric']}")
    print(f"   Semantic terms: {result.get('semantic_terms', [])}")
    
    return result

def determine_direct_route(query: str) -> Dict[str, Any]:
    """Determine specific direct route based on query content"""
    query_lower = query.lower()
    
    # Features shipped (specific feature queries)
    if re.search(r'features?\s+shipped', query_lower) or re.search(r'shipped\s+features?', query_lower):
        return {
            "route": "direct",
            "object": "features",
            "metric": "list",
            "semantic_terms": []
        }
    
    # What was shipped (general shipped changes)
    if re.search(r'what\s+was\s+shipped', query_lower) or re.search(r'what\s+shipped', query_lower):
        return {
            "route": "direct",
            "object": "prs",
            "metric": "list",
            "semantic_terms": []
        }
    
    # File that changed most
    if re.search(r'file\s+that\s+changed\s+most', query_lower):
        return {
            "route": "direct",
            "object": "files",
            "metric": "top",
            "semantic_terms": []
        }
    
    # Count queries
    if re.search(r'\b(count|how\s+many|number\s+of|total)\b', query_lower):
        return {
            "route": "direct",
            "object": "prs",
            "metric": "count",
            "semantic_terms": []
        }
    
    # Riskiest queries
    if re.search(r'\b(riskiest|high\s+risk|most\s+risky)\b', query_lower):
        # Check for "top N" pattern in riskiest queries
        top_match = re.search(r'top\s+(\d+)', query_lower)
        limit = int(top_match.group(1)) if top_match else 20
        return {
            "route": "direct",
            "object": "prs",
            "metric": "riskiest",
            "semantic_terms": [],
            "limit": limit
        }
    
    # Largest/Biggest queries
    if re.search(r'\b(largest|biggest|most\s+changes)\b', query_lower):
        # Check for "top N" pattern in largest queries
        top_match = re.search(r'top\s+(\d+)', query_lower)
        limit = int(top_match.group(1)) if top_match else 20
        return {
            "route": "direct",
            "object": "prs",
            "metric": "largest",
            "semantic_terms": [],
            "limit": limit
        }
    
    # Top/Most queries
    if re.search(r'\b(top|most)\b', query_lower):
        # Extract number from "top N" pattern
        top_match = re.search(r'top\s+(\d+)', query_lower)
        limit = int(top_match.group(1)) if top_match else 20
        return {
            "route": "direct",
            "object": "prs",
            "metric": "top",
            "semantic_terms": [],
            "limit": limit
        }
    
    # Specific PR number queries
    pr_match = re.search(r'pr\s+(?:#\s*)?(\d+)', query_lower)
    if pr_match:
        pr_number = int(pr_match.group(1))
        return {
            "route": "direct",
            "object": "prs",
            "metric": "list",
            "semantic_terms": [],
            "pr_number": pr_number
        }
    
    # Changes made/done by specific author
    author_match = re.search(r'changes?\s+(made|done)\s+by\s+([a-zA-Z0-9_-]+)', query_lower)
    if author_match:
        author = author_match.group(2)  # Group 2 is the author name
        return {
            "route": "direct",
            "object": "prs",
            "metric": "list",
            "semantic_terms": [],
            "author": author
        }
    
    # Default to PR list
    result = {
        "route": "direct",
        "object": "prs",
        "metric": "list",
        "semantic_terms": []
    }
    
    print(f"🎯 Direct Route Determination:")
    print(f"   Query: '{query}'")
    print(f"   Route: {result['route']}")
    print(f"   Object: {result['object']}")
    print(f"   Metric: {result['metric']}")
    
    return result

def determine_hybrid_route(query: str, semantic_terms: List[str]) -> Dict[str, Any]:
    """Determine specific hybrid route based on query content and semantic terms"""
    query_lower = query.lower()
    
    # File-centric queries
    file_keywords = ['file', 'files', 'sql', 'database', 'schema', 'migration', '.py', '.js', '.java', '.cpp', '.c', '.h', '.ts', '.jsx', '.tsx', '.html', '.css', '.json', '.yaml', '.yml', '.md', '.txt']
    if any(keyword in query_lower for keyword in file_keywords):
        return {
            "route": "hybrid",
            "object": "files",
            "metric": "list",
            "semantic_terms": semantic_terms
        }
    
    # Feature-centric queries
    feature_keywords = ['feature', 'features', 'auth', 'payment', 'api', 'endpoint']
    if any(keyword in query_lower for keyword in feature_keywords):
        return {
            "route": "hybrid",
            "object": "features",
            "metric": "list",
            "semantic_terms": semantic_terms
        }
    
    # Default to PR-centric
    return {
        "route": "hybrid",
        "object": "prs",
        "metric": "list",
        "semantic_terms": semantic_terms
    }

def determine_vector_route(query: str) -> Dict[str, Any]:
    """Determine specific vector route based on query content"""
    query_lower = query.lower()
    
    # Explanation queries
    if re.search(r'\b(why|explain|how\s+does|what\s+is)\b', query_lower):
        return {
            "route": "vector",
            "object": "prs",
            "metric": "explain",
            "semantic_terms": [query]
        }
    
    # Risk analysis queries
    if re.search(r'\b(risky|risk|vulnerability|security)\b', query_lower):
        return {
            "route": "vector",
            "object": "files",
            "metric": "explain",
            "semantic_terms": [query]
        }
    
    # Default to PR-centric explanation
    return {
        "route": "vector",
        "object": "prs",
        "metric": "explain",
        "semantic_terms": [query]
    }

def extract_semantic_terms(query: str) -> List[str]:
    """
    Extract semantic terms from query for hybrid/vector search.
    
    Args:
        query: Natural language query string
        
    Returns:
        List of semantic terms to use for vector search
    """
    query_lower = query.lower()
    
    # Common technical terms
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
    
    found_terms = []
    for term in technical_terms:
        if term in query_lower:
            found_terms.append(term)
    
    # If no technical terms found, use the entire query
    if not found_terms:
        found_terms = [query]
    
    return found_terms

def is_explanation_query(query: str) -> bool:
    """Check if query is asking for explanation/analysis"""
    explanation_patterns = [
        r'\bwhy\b',
        r'\bexplain\b',
        r'\bhow\s+does\b',
        r'\bwhat\s+is\b',
        r'\brisky\s+because\b',
        r'\bimpact\s+of\b',
        r'\bcause\s+of\b',
        r'\breason\s+for\b'
    ]
    
    return any(re.search(pattern, query.lower()) for pattern in explanation_patterns)

def is_count_query(query: str) -> bool:
    """Check if query is asking for counts/numbers"""
    count_patterns = [
        r'\bcount\b',
        r'\bhow\s+many\b',
        r'\bnumber\s+of\b',
        r'\btotal\b',
        r'\bsum\b',
        r'\bamount\b'
    ]
    
    return any(re.search(pattern, query.lower()) for pattern in count_patterns)

def is_top_query(query: str) -> bool:
    """Check if query is asking for top/most items"""
    top_patterns = [
        r'\btop\b',
        r'\bmost\b',
        r'\bbest\b',
        r'\bhighest\b',
        r'\blargest\b',
        r'\bmaximum\b'
    ]
    
    return any(re.search(pattern, query.lower()) for pattern in top_patterns)
