#!/usr/bin/env python3
"""
Test the file search fix
"""

from time_parse import parse_time
from router import route_query

def test_file_search_fix():
    # Test the query that was failing
    query = "show changes in monthly_user_site_hits_job.py"
    
    print(f"🔍 Testing query: '{query}'")
    
    # Test routing
    plan = route_query(query)
    print(f"🎯 Routing plan: {plan}")
    
    # Test time parsing
    start, end = parse_time(query)
    print(f"⏰ Time window: {start} to {end}")
    
    # Check if it's detected as file-specific
    if plan.get("specific_file"):
        print(f"✅ Detected as file-specific search for: {plan['specific_file']}")
    else:
        print(f"❌ Not detected as file-specific search")
    
    # Test with the actual file search
    if plan.get("specific_file"):
        from hybrid_handlers import hybrid_file_search
        from milvus_client import get_milvus_client
        
        client = get_milvus_client()
        filename = plan["specific_file"]
        
        print(f"🔍 Testing file search for: {filename}")
        results = hybrid_file_search("DataExpert-io/data-engineer-handbook", start, end, filename, 10)
        
        print(f"📊 Results found: {len(results)}")
        if results:
            print(f"📋 Sample result:")
            result = results[0]
            print(f"  PR #{result.get('pr_number')}: {result.get('title')}")
            print(f"  Author: {result.get('author_name')}")
            print(f"  Merged: {result.get('merged_at')}")

if __name__ == "__main__":
    test_file_search_fix()
