#!/usr/bin/env python3
"""
Test router patterns
"""

from router import route_query

def test_router():
    test_queries = [
        "shipped features in last two weeks",
        "features shipped in last two weeks", 
        "features shipped last month",
        "shipped features last month",
        "show changes in monthly_user_site_hits_job.py",
        "auth features last month",
        "why was last week risky",
        "changes made by xinran-waibel in last two weeks",
        "changes made by cybermaxs last month",
        "changes done by xinran-waibel in last two weeks",
        "changes done by cybermaxs last month"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Testing query: '{query}'")
        try:
            result = route_query(query)
            print(f"   Route: {result['route']}")
            print(f"   Object: {result['object']}")
            print(f"   Metric: {result['metric']}")
            if 'semantic_terms' in result:
                print(f"   Semantic terms: {result['semantic_terms']}")
            if 'specific_file' in result:
                print(f"   Specific file: {result['specific_file']}")
            if 'author' in result:
                print(f"   Author: {result['author']}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_router()
