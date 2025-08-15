#!/usr/bin/env python3
"""
Test script for the intelligent query routing system.
"""

import os
import sys
from time_parse import parse_time
from router import route_query

def test_time_parsing():
    """Test time parsing functionality"""
    print("🧪 Testing time parsing...")
    
    test_cases = [
        "changes last week",
        "features shipped last two weeks", 
        "what happened yesterday",
        "in July 2025",
        "this week's changes",
        "no time specified query"
    ]
    
    for query in test_cases:
        start, end = parse_time(query)
        print(f"  Query: '{query}' -> {start} to {end}")

def test_query_routing():
    """Test query routing functionality"""
    print("\n🧪 Testing query routing...")
    
    test_cases = [
        "changes last week",
        "features shipped last two weeks",
        "file that changed most last week",
        "auth features last month",
        "risky sql changes last week",
        "why was last week risky?",
        "show streaming features",
        "count of PRs merged yesterday",
        "top 10 most risky changes",
        "explain the database changes"
    ]
    
    for query in test_cases:
        plan = route_query(query)
        print(f"  Query: '{query}'")
        print(f"    Route: {plan['route']}")
        print(f"    Object: {plan['object']}")
        print(f"    Metric: {plan['metric']}")
        print(f"    Semantic terms: {plan.get('semantic_terms', [])}")
        print()

def test_integration():
    """Test full integration"""
    print("\n🧪 Testing full integration...")
    
    # Test direct route
    query = "changes last week"
    start, end = parse_time(query)
    plan = route_query(query)
    
    print(f"Query: '{query}'")
    print(f"Time window: {start} to {end}")
    print(f"Plan: {plan}")
    
    # Test hybrid route
    query = "auth features last month"
    start, end = parse_time(query)
    plan = route_query(query)
    
    print(f"\nQuery: '{query}'")
    print(f"Time window: {start} to {end}")
    print(f"Plan: {plan}")
    
    # Test vector route
    query = "why was last week risky?"
    start, end = parse_time(query)
    plan = route_query(query)
    
    print(f"\nQuery: '{query}'")
    print(f"Time window: {start} to {end}")
    print(f"Plan: {plan}")

if __name__ == "__main__":
    print("🚀 Testing Intelligent Query Routing System")
    print("=" * 50)
    
    try:
        test_time_parsing()
        test_query_routing()
        test_integration()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
