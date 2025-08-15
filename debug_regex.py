#!/usr/bin/env python3
"""
Debug regex pattern for time expressions
"""

import re

def test_regex():
    # Test the patterns from time_parse.py
    patterns = [
        r'last\s+(\d+)\s+(day|week|month|year)s?',
        r'last\s+(one|two|three|four|five|six|seven|eight|nine|ten)\s+(day|week|month|year)s?',
        r'last\s+(day|week|month|year)',
    ]
    
    test_queries = [
        "last two weeks",
        "last 2 weeks", 
        "last week",
        "last month",
        "last year",
        "last 3 days",
        "last one month"
    ]
    
    print(f"Testing all patterns:")
    for i, pattern in enumerate(patterns, 1):
        print(f"\nPattern {i}: '{pattern}'")
        for test_query in test_queries:
            match = re.search(pattern, test_query)
            if match:
                print(f"  ✅ '{test_query}' → '{match.group(0)}'")
            else:
                print(f"  ❌ '{test_query}' → No match")

if __name__ == "__main__":
    test_regex()
