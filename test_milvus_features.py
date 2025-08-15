#!/usr/bin/env python3
"""
Test script to check Milvus connection and feature data
"""

import os
from milvus_client import get_milvus_client

def test_milvus_features():
    try:
        # Get Milvus client
        client = get_milvus_client()
        print("✅ Milvus client connected successfully")
        
        # Test query for merged PRs in the last 2 weeks
        start_time = 1754003800  # 2 weeks ago
        end_time = 1755213400    # now
        
        # Query without feature filter first
        expr = f'merged_at >= {start_time} and merged_at <= {end_time} and is_merged == true and repo_name == "DataExpert-io/data-engineer-handbook"'
        fields = ["repo_name", "pr_number", "title", "merged_at", "author_name", "feature"]
        
        print(f"🔍 Testing query: {expr}")
        
        # Query PRs
        results = client.query_prs(expr, fields)
        print(f"📊 Total merged PRs in time window: {len(results)}")
        
        if results:
            print(f"📋 Sample results:")
            for i, pr in enumerate(results[:5]):
                print(f"  PR #{pr.get('pr_number')}: {pr.get('title')}")
                print(f"    Feature: '{pr.get('feature')}'")
                print(f"    Author: {pr.get('author_name')}")
                print(f"    Merged: {pr.get('merged_at')}")
                print()
            
            # Check feature distribution
            features = [pr.get('feature', '') for pr in results if pr.get('feature')]
            empty_features = sum(1 for pr in results if not pr.get('feature') or pr.get('feature') == '')
            null_features = sum(1 for pr in results if pr.get('feature') is None)
            
            print(f"📈 Feature distribution:")
            print(f"  PRs with features: {len(features)}")
            print(f"  PRs with empty features: {empty_features}")
            print(f"  PRs with null features: {null_features}")
            print(f"  Sample features: {features[:10]}")
            
            # Test with feature filter
            expr_with_feature = expr + ' and feature != ""'
            print(f"\n🔍 Testing with feature filter: {expr_with_feature}")
            
            feature_results = client.query_prs(expr_with_feature, fields)
            print(f"📊 PRs with feature filter: {len(feature_results)}")
            
            if feature_results:
                print(f"📋 Sample feature results:")
                for i, pr in enumerate(feature_results[:3]):
                    print(f"  PR #{pr.get('pr_number')}: {pr.get('title')}")
                    print(f"    Feature: '{pr.get('feature')}'")
                    print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_milvus_features()
