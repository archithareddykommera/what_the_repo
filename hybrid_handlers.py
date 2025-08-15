#!/usr/bin/env python3
"""
Hybrid handlers for combining scalar filters with vector search.
Handles topic-based queries with semantic terms.
"""

from typing import List, Dict, Any, Optional
from milvus_client import search_prs, search_files, query_files, query_prs
import openai
import os

def get_embedding(text: str) -> List[float]:
    """
    Get embedding for text using OpenAI.
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding vector
    """
    try:
        openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        # Return zero vector as fallback
        return [0.0] * 1536

def hybrid_features(repo: str, start: int, end: int, terms: str, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for features with semantic terms.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        terms: Semantic terms for vector search
        k: Number of results to return
        
    Returns:
        List of feature PRs ranked by semantic similarity
    """
    # Build scalar filter expression
    expr = f'merged_at >= {start} and merged_at <= {end} and is_merged == true and repo_name == "{repo}" and feature != ""'
    
    # Query fields
    fields = [
        "repo_name", "pr_number", "title", "pr_summary", "merged_at", 
        "author_name", "risk_score", "high_risk", "feature"
    ]
    
    # Get embedding for semantic terms
    qvec = get_embedding(terms)
    
    # Perform hybrid search
    hits = search_prs(qvec, expr, fields, k=k)
    
    # Sort by distance (closer is better) and then by recency
    hits.sort(key=lambda r: (r.get("_distance", 0), -r.get("merged_at", 0)))
    
    return hits

def hybrid_risky_files(repo: str, start: int, end: int, terms: str, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for risky files with semantic terms.
    Returns PRs that contain the matching files.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        terms: Semantic terms for vector search
        k: Number of results to return
        
    Returns:
        List of PRs containing risky files, ranked by semantic similarity
    """
    # Build scalar filter expression for files
    file_expr = f'merged_at >= {start} and merged_at <= {end} and repo_name == "{repo}" and is_binary == false'
    
    # Query fields for files
    file_fields = [
        "repo_name", "pr_number", "file_id", "language", "risk_score_file", 
        "file_risk_reasons", "lines_changed", "merged_at"
    ]
    
    # Get embedding for semantic terms
    qvec = get_embedding(terms)
    
    # Perform hybrid search on files
    files = search_files(qvec, file_expr, file_fields, k=k*2)  # Get more files to find unique PRs
    
    print(f"🔍 Hybrid file search debugging:")
    print(f"   Files found: {len(files)}")
    if files:
        print(f"   Sample file result: {files[0]}")
        print(f"   File result keys: {list(files[0].keys())}")
    
    # Extract unique PR numbers from the file results
    pr_numbers = set()
    for file_result in files:
        pr_num = file_result.get('pr_number')
        print(f"   File {file_result.get('file_id', 'unknown')}: PR #{pr_num}")
        if pr_num:
            pr_numbers.add(pr_num)
    
    print(f"   Unique PR numbers found: {pr_numbers}")
    
    if not pr_numbers:
        print(f"   ⚠️ No PR numbers found in file results")
        return []
    
    # Now query the PRs that contain these files
    # Build OR expression for PR numbers
    pr_conditions = []
    for pr_num in pr_numbers:
        pr_conditions.append(f'pr_number == {pr_num}')
    
    pr_expr = f'merged_at >= {start} and merged_at <= {end} and repo_name == "{repo}" and is_merged == true and ({(" or ".join(pr_conditions))})'
    
    # Query fields for PRs
    pr_fields = [
        "repo_name", "pr_number", "pr_id", "title", "pr_summary", "merged_at", 
        "author_name", "risk_score", "high_risk", "feature"
    ]
    
    # Get the PRs
    print(f"   PR query expression: {pr_expr}")
    prs = query_prs(pr_expr, pr_fields)
    print(f"   PRs found: {len(prs)}")
    
    # Sort by merged_at (newest first)
    prs.sort(key=lambda r: r.get("merged_at", 0), reverse=True)
    
    return prs[:k]

def hybrid_file_search(repo: str, start: int, end: int, filename: str, k: int = 50) -> List[Dict[str, Any]]:
    """
    Direct search for a specific file by name.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        filename: Name of the file to search for
        k: Number of results to return
        
    Returns:
        List of PRs that contain the specified file
    """
    # Build expression to find the specific file
    file_expr = f'merged_at >= {start} and merged_at <= {end} and repo_name == "{repo}" and file_id like "%{filename}%"'
    
    # Query fields for files
    file_fields = [
        "repo_name", "pr_number", "file_id", "language", "risk_score_file", 
        "file_risk_reasons", "lines_changed", "merged_at"
    ]
    
    # Query files directly
    files = query_files(file_expr, file_fields)
    
    print(f"🔍 Direct file search for '{filename}':")
    print(f"   File query expression: {file_expr}")
    print(f"   Files found: {len(files)}")
    if files:
        print(f"   Sample file result: {files[0]}")
    
    # Extract unique PR numbers from the file results
    pr_numbers = set()
    for file_result in files:
        pr_num = file_result.get('pr_number')
        if pr_num:
            pr_numbers.add(pr_num)
    
    print(f"   Unique PR numbers found: {pr_numbers}")
    
    if not pr_numbers:
        print(f"   ⚠️ No PR numbers found for file '{filename}'")
        return []
    
    # Now query the PRs that contain these files
    pr_conditions = []
    for pr_num in pr_numbers:
        pr_conditions.append(f'pr_number == {pr_num}')
    
    pr_expr = f'merged_at >= {start} and merged_at <= {end} and repo_name == "{repo}" and is_merged == true and ({(" or ".join(pr_conditions))})'
    
    # Query fields for PRs
    pr_fields = [
        "repo_name", "pr_number", "pr_id", "title", "pr_summary", "merged_at", 
        "author_name", "risk_score", "high_risk", "feature"
    ]
    
    # Get the PRs
    print(f"   PR query expression: {pr_expr}")
    prs = query_prs(pr_expr, pr_fields)
    print(f"   PRs found: {len(prs)}")
    
    # Sort by merged_at (newest first)
    prs.sort(key=lambda r: r.get("merged_at", 0), reverse=True)
    
    return prs[:k]

def hybrid_auth_features(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for authentication-related features.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of auth-related features
    """
    return hybrid_features(repo, start, end, "authentication authorization login logout security", k)

def hybrid_payment_features(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for payment-related features.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of payment-related features
    """
    return hybrid_features(repo, start, end, "payment billing invoice transaction money", k)

def hybrid_security_changes(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for security-related changes.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of security-related changes
    """
    return hybrid_risky_files(repo, start, end, "security vulnerability risk encryption secure", k)

def hybrid_database_changes(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for database-related changes.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of database-related changes
    """
    return hybrid_risky_files(repo, start, end, "database sql query schema migration table", k)

def hybrid_api_changes(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for API-related changes.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of API-related changes
    """
    return hybrid_features(repo, start, end, "api endpoint route rest graphql webhook", k)

def hybrid_test_changes(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for test-related changes.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of test-related changes
    """
    return hybrid_features(repo, start, end, "test testing tested unit integration e2e", k)

def hybrid_performance_changes(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for performance-related changes.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of performance-related changes
    """
    return hybrid_features(repo, start, end, "performance optimization speed fast slow", k)

def hybrid_bug_fixes(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for bug fix changes.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of bug fix changes
    """
    return hybrid_features(repo, start, end, "error bug fix issue problem crash", k)

def hybrid_complex_changes(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for complex changes.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of complex changes
    """
    return hybrid_features(repo, start, end, "complex complicated refactor cleanup simplify", k)

def hybrid_streaming_features(repo: str, start: int, end: int, k: int = 50) -> List[Dict[str, Any]]:
    """
    Hybrid search for streaming features.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        k: Number of results to return
        
    Returns:
        List of streaming features
    """
    return hybrid_features(repo, start, end, "streaming real-time async concurrent parallel", k)
