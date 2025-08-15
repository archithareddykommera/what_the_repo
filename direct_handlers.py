#!/usr/bin/env python3
"""
Direct handlers for scalar queries (no vector search).
Handles PR lists, features shipped, and file analysis.
"""

from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
from milvus_client import query_prs, query_files

def direct_prs_list(repo: str, start: int, end: int, author: Optional[str] = None, pr_number: Optional[int] = None, limit: int = 100, sort_by_largest: bool = False, sort_by_riskiest: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Get list of PRs with summary statistics.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        author: Optional author filter
        pr_number: Optional specific PR number filter
        limit: Maximum number of results
        
    Returns:
        Tuple of (PR list, summary statistics)
    """
    # Build expression
    expr_parts = [
        f'merged_at >= {start}',
        f'merged_at <= {end}',
        'is_merged == true',
        f'repo_name == "{repo}"'
    ]
    
    if author:
        expr_parts.append(f'author_name == "{author}"')
    
    if pr_number:
        expr_parts.append(f'pr_number == {pr_number}')
    
    expr = " and ".join(expr_parts)
    
    # Query fields - include pr_id for uniqueness
    fields = [
        "repo_name", "pr_number", "pr_id", "title", "pr_summary", "created_at", "merged_at", 
        "author_name", "risk_score", "high_risk", "feature", "changed_files", "additions", "deletions"
    ]
    
    # Execute query
    rows = query_prs(expr, fields)
    
    print(f"📊 Direct PRs List Query Results:")
    print(f"   Query expression: {expr}")
    print(f"   Raw rows returned: {len(rows)}")
    
    # Check for duplicates by PR ID (more unique than PR number)
    pr_ids = [r.get('pr_id') for r in rows]
    unique_pr_ids = set(pr_ids)
    print(f"   Unique PR IDs: {len(unique_pr_ids)}")
    print(f"   Duplicate PR IDs: {len(pr_ids) - len(unique_pr_ids)}")
    
    if len(pr_ids) != len(unique_pr_ids):
        print(f"   🔍 Duplicate PR IDs found:")
        from collections import Counter
        pr_count = Counter(pr_ids)
        duplicates = {pr: count for pr, count in pr_count.items() if count > 1}
        for pr_id, count in duplicates.items():
            print(f"     PR ID {pr_id}: {count} times")
    
    # Remove duplicates by PR ID (keep the first occurrence)
    seen_prs = set()
    unique_rows = []
    for row in rows:
        pr_id = row.get('pr_id')
        if pr_id not in seen_prs:
            seen_prs.add(pr_id)
            unique_rows.append(row)
    
    print(f"   After deduplication: {len(unique_rows)} rows")
    
    # Sort by appropriate criteria
    if sort_by_riskiest:
        # Sort by risk score (highest first)
        unique_rows.sort(key=lambda r: r.get("risk_score", 0.0), reverse=True)
        print(f"   Sorted by risk score (highest first)")
    elif sort_by_largest:
        # Sort by total changes (additions + deletions + files changed) - largest first
        unique_rows.sort(key=lambda r: (
            r.get("additions", 0) + r.get("deletions", 0) + r.get("changed_files", 0)
        ), reverse=True)
        print(f"   Sorted by largest changes (total modifications)")
    else:
        # Sort by merged_at (newest first)
        unique_rows.sort(key=lambda r: r.get("merged_at", 0), reverse=True)
        print(f"   Sorted by merge date (newest first)")
    
    # Limit results
    limited_rows = unique_rows[:limit]
    
    # Calculate summary statistics using deduplicated rows
    total_prs = len(unique_rows)
    features_shipped = sum(1 for r in unique_rows if r.get("feature") and r.get("feature").strip())
    high_risk_prs = sum(1 for r in unique_rows if r.get("high_risk"))
    
    summary = {
        "prs_merged": total_prs,
        "features_shipped": features_shipped,
        "high_risk_prs": high_risk_prs,
        "time_period": {
            "start": start,
            "end": end
        }
    }
    
    return limited_rows, summary

def direct_features_list(repo: str, start: int, end: int, author: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get list of features shipped.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        author: Optional author filter
        limit: Maximum number of results
        
    Returns:
        List of feature PRs
    """
    # Build expression
    expr_parts = [
        f'merged_at >= {start}',
        f'merged_at <= {end}',
        'is_merged == true',
        f'repo_name == "{repo}"',
        'feature != ""'
    ]
    
    if author:
        expr_parts.append(f'author_name == "{author}"')
    
    expr = " and ".join(expr_parts)
    
    # Query fields
    fields = [
        "repo_name", "pr_number", "pr_id", "title", "pr_summary", "created_at", "merged_at", 
        "author_name", "risk_score", "high_risk", "feature", "changed_files", "additions", "deletions"
    ]
    
    # Execute query
    rows = query_prs(expr, fields)
    
    print(f"📊 Direct Features Query Results:")
    print(f"   Query expression: {expr}")
    print(f"   Raw rows returned: {len(rows)}")
    if rows:
        print(f"   Sample row: {rows[0]}")
        print(f"   Features found: {sum(1 for r in rows if r.get('feature') and r.get('feature').strip())}")
        
        # Debug: Show all feature values
        print(f"   🔍 Feature values found:")
        feature_values = [r.get('feature', '') for r in rows if r.get('feature')]
        print(f"   Feature values: {feature_values[:10]}")  # Show first 10
        print(f"   Empty features: {sum(1 for r in rows if not r.get('feature') or r.get('feature') == '')}")
        print(f"   Null features: {sum(1 for r in rows if r.get('feature') is None)}")
    
    # Check for duplicates by PR ID (more unique than PR number)
    pr_ids = [r.get('pr_id') for r in rows]
    unique_pr_ids = set(pr_ids)
    print(f"   Unique PR IDs: {len(unique_pr_ids)}")
    print(f"   Duplicate PR IDs: {len(pr_ids) - len(unique_pr_ids)}")
    
    if len(pr_ids) != len(unique_pr_ids):
        print(f"   🔍 Duplicate PR IDs found:")
        from collections import Counter
        pr_count = Counter(pr_ids)
        duplicates = {pr: count for pr, count in pr_count.items() if count > 1}
        for pr_id, count in duplicates.items():
            print(f"     PR ID {pr_id}: {count} times")
    
    # Remove duplicates by PR ID (keep the first occurrence)
    seen_prs = set()
    unique_rows = []
    for row in rows:
        pr_id = row.get('pr_id')
        if pr_id not in seen_prs:
            seen_prs.add(pr_id)
            unique_rows.append(row)
    
    print(f"   After deduplication: {len(unique_rows)} rows")
    
    # Filter to only include PRs with actual features (using the feature field)
    feature_rows = [r for r in unique_rows if r.get('feature') and r.get('feature').strip()]
    print(f"   After feature filtering: {len(feature_rows)} rows")
    
    # Sort by merged_at (newest first)
    feature_rows.sort(key=lambda r: r.get("merged_at", 0), reverse=True)
    
    # Limit results
    limited_rows = feature_rows[:limit]
    print(f"   Limited to {len(limited_rows)} results")
    
    return limited_rows

def direct_top_file_by_lines(repo: str, start: int, end: int) -> Optional[Dict[str, Any]]:
    """
    Find the file that changed most (by lines) in the given time period.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        
    Returns:
        File information with total lines changed, or None if no files found
    """
    # Build expression
    expr = f'merged_at >= {start} and merged_at <= {end} and repo_name == "{repo}" and is_binary == false'
    
    # Query fields
    fields = ["file_id", "lines_changed", "pr_number"]
    
    # Execute query
    rows = query_files(expr, fields)
    
    if not rows:
        return None
    
    # Aggregate lines changed by file
    file_totals = defaultdict(lambda: {"file_path": "", "lines": 0, "pr_count": 0})
    
    for row in rows:
        file_id = row.get("file_id")
        if file_id:
            file_totals[file_id]["file_path"] = file_id  # Use file_id as file_path since file_path doesn't exist
            file_totals[file_id]["lines"] += int(row.get("lines_changed") or 0)
            file_totals[file_id]["pr_count"] += 1
    
    if not file_totals:
        return None
    
    # Find file with most lines changed
    top_file_id = max(file_totals, key=lambda k: file_totals[k]["lines"])
    top_file = file_totals[top_file_id]
    
    return {
        "file_id": top_file_id,
        "file_path": top_file["file_path"],
        "total_lines_changed": top_file["lines"],
        "pr_count": top_file["pr_count"]
    }

def direct_pr_count(repo: str, start: int, end: int, author: Optional[str] = None) -> Dict[str, Any]:
    """
    Get count of PRs with breakdowns.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        author: Optional author filter
        
    Returns:
        Dictionary with PR counts and breakdowns
    """
    # Build expression
    expr_parts = [
        f'merged_at >= {start}',
        f'merged_at <= {end}',
        f'repo_name == "{repo}"'
    ]
    
    if author:
        expr_parts.append(f'author_name == "{author}"')
    
    expr = " and ".join(expr_parts)
    
    # Query fields
    fields = [
        "is_merged", "is_closed", "feature", "high_risk", 
        "risk_score", "author_name"
    ]
    
    # Execute query
    rows = query_prs(expr, fields)
    
    # Calculate counts
    total_prs = len(rows)
    merged_prs = sum(1 for r in rows if r.get("is_merged"))
    closed_prs = sum(1 for r in rows if r.get("is_closed"))
    feature_prs = sum(1 for r in rows if r.get("feature") and r.get("feature").strip())
    high_risk_prs = sum(1 for r in rows if r.get("high_risk"))
    
    # Author breakdown
    author_counts = defaultdict(int)
    for row in rows:
        author = row.get("author_name", "Unknown")
        author_counts[author] += 1
    
    top_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Risk distribution
    risk_distribution = {"low": 0, "medium": 0, "high": 0}
    for row in rows:
        risk_score = row.get("risk_score", 0)
        if risk_score >= 7.0:
            risk_distribution["high"] += 1
        elif risk_score >= 4.0:
            risk_distribution["medium"] += 1
        else:
            risk_distribution["low"] += 1
    
    return {
        "total_prs": total_prs,
        "merged_prs": merged_prs,
        "closed_prs": closed_prs,
        "feature_prs": feature_prs,
        "high_risk_prs": high_risk_prs,
        "top_authors": [{"author": author, "count": count} for author, count in top_authors],
        "risk_distribution": risk_distribution,
        "time_period": {
            "start": start,
            "end": end
        }
    }

def direct_top_prs_by_risk(repo: str, start: int, end: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get top PRs by risk score.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        limit: Maximum number of results
        
    Returns:
        List of high-risk PRs
    """
    # Build expression
    expr = f'merged_at >= {start} and merged_at <= {end} and repo_name == "{repo}" and is_merged == true'
    
    # Query fields
    fields = [
        "repo_name", "pr_number", "title", "pr_summary", "merged_at", 
        "author_name", "risk_score", "high_risk", "risk_reasons"
    ]
    
    # Execute query
    rows = query_prs(expr, fields)
    
    # Sort by risk score (highest first)
    rows.sort(key=lambda r: r.get("risk_score", 0), reverse=True)
    
    # Limit results
    return rows[:limit]

def direct_file_changes_summary(repo: str, start: int, end: int) -> Dict[str, Any]:
    """
    Get summary of file changes in the time period.
    
    Args:
        repo: Repository name
        start: Start timestamp (epoch)
        end: End timestamp (epoch)
        
    Returns:
        Summary of file changes
    """
    # Build expression
    expr = f'merged_at >= {start} and merged_at <= {end} and repo_name == "{repo}"'
    
    # Query fields
    fields = [
        "file_id", "language", "lines_changed", "is_binary", 
        "risk_score_file", "file_risk_reasons"
    ]
    
    # Execute query
    rows = query_files(expr, fields)
    
    if not rows:
        return {
            "total_files": 0,
            "total_lines_changed": 0,
            "language_breakdown": {},
            "risk_breakdown": {"low": 0, "medium": 0, "high": 0}
        }
    
    # Calculate statistics
    total_files = len(rows)
    total_lines = sum(int(row.get("lines_changed") or 0) for row in rows)
    
    # Language breakdown
    language_counts = defaultdict(int)
    for row in rows:
        language = row.get("language", "unknown")
        language_counts[language] += 1
    
    # Risk breakdown
    risk_breakdown = {"low": 0, "medium": 0, "high": 0}
    for row in rows:
        risk_score = row.get("risk_score_file", 0)
        if risk_score >= 7.0:
            risk_breakdown["high"] += 1
        elif risk_score >= 4.0:
            risk_breakdown["medium"] += 1
        else:
            risk_breakdown["low"] += 1
    
    return {
        "total_files": total_files,
        "total_lines_changed": total_lines,
        "language_breakdown": dict(language_counts),
        "risk_breakdown": risk_breakdown,
        "time_period": {
            "start": start,
            "end": end
        }
    }
