#!/usr/bin/env python3
"""
Check repository names in the data
"""

import json

def check_repo_names():
    with open('pr_data_20250808_115049.json', 'r') as f:
        data = json.load(f)
    
    print(f"Total PRs: {len(data)}")
    
    # Get unique repository names
    repo_names = set()
    for pr in data:
        repo_name = pr.get('repo_name', '')
        if repo_name:
            repo_names.add(repo_name)
    
    print(f"Repository names found: {repo_names}")
    
    # Check merged PRs by repository
    for repo_name in repo_names:
        merged_prs = [pr for pr in data if pr.get('repo_name') == repo_name and pr.get('is_merged')]
        print(f"\nRepository: {repo_name}")
        print(f"  Total PRs: {len([pr for pr in data if pr.get('repo_name') == repo_name])}")
        print(f"  Merged PRs: {len(merged_prs)}")
        
        # Check features in this repo
        features = [pr.get('feature', '') for pr in merged_prs if pr.get('feature')]
        print(f"  Merged PRs with features: {len(features)}")
        if features:
            print(f"  Sample features: {features[:5]}")

if __name__ == "__main__":
    check_repo_names()
