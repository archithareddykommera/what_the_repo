#!/usr/bin/env python3
"""
Test time parsing for different queries
"""

from time_parse import parse_time

def test_time_parsing():
    # Test queries
    queries = [
        "show changes in monthly_user_site_hits_job.py",
        "show changes in monthly_user_site_hits_job.py in the last two weeks",
        "show changes in monthly_user_site_hits_job.py last week",
        "show changes in monthly_user_site_hits_job.py in July 2025",
        "features shipped last month",
        "PRs that merged yesterday"
    ]
    
    for query in queries:
        print(f"\n🔍 Testing query: '{query}'")
        try:
            start, end = parse_time(query)
            print(f"   Time window: {start} to {end}")
            
            # Convert to readable dates
            from datetime import datetime
            start_date = datetime.fromtimestamp(start)
            end_date = datetime.fromtimestamp(end)
            print(f"   Start: {start_date}")
            print(f"   End: {end_date}")
            print(f"   Duration: {end_date - start_date}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_time_parsing()
