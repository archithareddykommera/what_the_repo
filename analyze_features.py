#!/usr/bin/env python3
"""
Analyze feature field in PR data
"""

import json

def analyze_features():
    with open('pr_data_20250808_115049.json', 'r') as f:
        data = json.load(f)
    
    print(f"Total PRs: {len(data)}")
    
    # Count PRs with features
    features = [pr.get('feature', '') for pr in data if pr.get('feature')]
    print(f"PRs with features: {len(features)}")
    
    # Count empty features
    empty_features = sum(1 for pr in data if not pr.get('feature') or pr.get('feature') == '')
    print(f"PRs with empty features: {empty_features}")
    
    # Show sample features
    print(f"Sample features: {features[:10]}")
    
    # Check for merged PRs with features
    merged_with_features = [pr for pr in data if pr.get('is_merged') and pr.get('feature')]
    print(f"Merged PRs with features: {len(merged_with_features)}")
    
    # Show some merged PRs with features
    print("\nSample merged PRs with features:")
    for pr in merged_with_features[:5]:
        print(f"PR #{pr.get('pr_number')}: {pr.get('title')} - Feature: '{pr.get('feature')}'")
    
    # Check time range for merged PRs
    merged_prs = [pr for pr in data if pr.get('is_merged')]
    if merged_prs:
        merged_dates = [pr.get('merged_at') for pr in merged_prs if pr.get('merged_at')]
        if merged_dates:
            print(f"\nMerged PRs date range: {min(merged_dates)} to {max(merged_dates)}")
    
    # Check recent merged PRs with features
    recent_merged_with_features = [pr for pr in merged_with_features if pr.get('merged_at', 0) > 1754003800]  # Last 2 weeks
    print(f"Recent merged PRs with features (last 2 weeks): {len(recent_merged_with_features)}")

if __name__ == "__main__":
    analyze_features()
