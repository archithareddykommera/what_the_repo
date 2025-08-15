#!/usr/bin/env python3
"""
Vector handlers for explanation queries.
Uses vector search to provide insights and analysis.
"""

from typing import List, Dict, Any, Optional
from milvus_client import search_prs, search_files
from hybrid_handlers import get_embedding
import openai
import os

def vector_explanation(repo: str, start: int, end: int, query: str, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for explanation queries.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        query: Explanation query
        k: Number of results to return
        
    Returns:
        List of relevant PRs for explanation
    """
    # Build scalar filter expression (time and repo only)
    expr = f'merged_at >= {start} and merged_at <= {end} and repo_name == "{repo}"'
    
    # Query fields
    fields = [
        "repo_name", "pr_number", "title", "pr_summary", "merged_at", 
        "author_name", "risk_score", "high_risk", "risk_reasons", "feature"
    ]
    
    # Get embedding for query
    qvec = get_embedding(query)
    
    # Perform vector search
    hits = search_prs(qvec, expr, fields, k=k)
    
    # Sort by distance (closer is better)
    hits.sort(key=lambda r: r.get("_distance", 0))
    
    return hits

def vector_risk_analysis(repo: str, start: int, end: int, query: str, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for risk analysis queries.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        query: Risk analysis query
        k: Number of results to return
        
    Returns:
        List of risky files for analysis
    """
    # Build scalar filter expression
    expr = f'merged_at >= {start} and merged_at <= {end} and repo_name == "{repo}" and is_binary == false'
    
    # Query fields
    fields = [
        "repo_name", "pr_number", "file_id", "language", "risk_score_file", 
        "file_risk_reasons", "lines_changed", "merged_at"
    ]
    
    # Get embedding for query
    qvec = get_embedding(query)
    
    # Perform vector search
    files = search_files(qvec, expr, fields, k=k)
    
    # Sort by distance and then by risk score
    files.sort(key=lambda r: (r.get("_distance", 0), -(r.get("risk_score_file", 0))))
    
    return files

def vector_why_risky(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for "why was this risky" queries.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of high-risk changes with explanations
    """
    query = "why was this risky high risk vulnerability security issues"
    return vector_risk_analysis(repo, start, end, query, k)

def vector_streaming_features(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for streaming features.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of streaming-related features
    """
    query = "streaming real-time async concurrent parallel processing"
    return vector_explanation(repo, start, end, query, k)

def vector_complex_changes(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for complex changes.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of complex changes
    """
    query = "complex complicated refactor cleanup simplify architecture design"
    return vector_explanation(repo, start, end, query, k)

def vector_impact_analysis(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for impact analysis.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of high-impact changes
    """
    query = "impact effect influence change modification transformation"
    return vector_explanation(repo, start, end, query, k)

def vector_feature_explanation(repo: str, start: int, end: int, feature_terms: str, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for feature explanations.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        feature_terms: Feature-related terms
        k: Number of results to return
        
    Returns:
        List of feature-related changes
    """
    query = f"feature functionality {feature_terms} implementation"
    return vector_explanation(repo, start, end, query, k)

def vector_bug_explanation(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for bug explanations.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of bug-related changes
    """
    query = "bug fix error issue problem crash failure defect"
    return vector_explanation(repo, start, end, query, k)

def vector_performance_explanation(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for performance explanations.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of performance-related changes
    """
    query = "performance optimization speed fast slow bottleneck efficiency"
    return vector_explanation(repo, start, end, query, k)

def vector_security_explanation(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for security explanations.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of security-related changes
    """
    query = "security vulnerability risk encryption authentication authorization"
    return vector_explanation(repo, start, end, query, k)

def vector_architecture_explanation(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Vector search for architecture explanations.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of architecture-related changes
    """
    query = "architecture design pattern structure system organization"
    return vector_explanation(repo, start, end, query, k)

def generate_explanation_summary(results: List[Dict[str, Any]], query: str) -> str:
    """
    Generate a summary explanation based on search results.
    
    Args:
        results: List of search results
        query: Original query
        
    Returns:
        Generated explanation summary
    """
    if not results:
        return "No relevant changes found for this query."
    
    try:
        openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Prepare context from results
        context = []
        for i, result in enumerate(results[:10]):  # Use top 10 results
            context.append(f"{i+1}. PR #{result.get('pr_number', 'N/A')}: {result.get('title', 'N/A')}")
            if result.get('pr_summary'):
                context.append(f"   Summary: {result.get('pr_summary')}")
            if result.get('risk_reasons'):
                context.append(f"   Risk: {', '.join(result.get('risk_reasons', []))}")
        
        context_text = "\n".join(context)
        
        # Generate explanation
        prompt = f"""
Based on the following repository changes, please provide a clear explanation for the query: "{query}"

Repository Changes:
{context_text}

Please provide a concise explanation that:
1. Addresses the specific question asked
2. Highlights key patterns or insights
3. Mentions any notable risks or concerns
4. Is written in a clear, professional tone

Explanation:
"""
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that explains repository changes and code patterns."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error generating explanation: {e}")
        return f"Found {len(results)} relevant changes, but unable to generate detailed explanation due to an error."

def vector_search_with_explanation(repo: str, start: int, end: int, query: str, k: int = 50) -> Dict[str, Any]:
    """
    Perform vector search and generate explanation.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        query: Search query
        k: Number of results to return
        
    Returns:
        Dictionary with results and explanation
    """
    # Perform vector search
    results = vector_explanation(repo, start, end, query, k)
    
    # Generate explanation
    explanation = generate_explanation_summary(results, query)
    
    return {
        "results": results,
        "explanation": explanation,
        "query": query,
        "time_period": {
            "start": start,
            "end": end
        }
    }
