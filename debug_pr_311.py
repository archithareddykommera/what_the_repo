#!/usr/bin/env python3
"""
Debug script to check PR-311 and its files
"""

from milvus_client import get_milvus_client

def debug_pr_311():
    try:
        # Get Milvus client
        client = get_milvus_client()
        print("✅ Milvus client connected successfully")
        
        # Check if PR-311 exists
        pr_expr = 'repo_name == "DataExpert-io/data-engineer-handbook" and pr_number == 311'
        pr_fields = ["pr_number", "title", "merged_at", "author_name"]
        
        print(f"🔍 Checking PR-311...")
        print(f"   Expression: {pr_expr}")
        
        # Query PR
        pr_results = client.query_prs(pr_expr, pr_fields)
        print(f"📊 PR-311 found: {len(pr_results)}")
        
        if pr_results:
            pr_data = pr_results[0]
            print(f"📋 PR-311 details:")
            print(f"  Title: {pr_data.get('title')}")
            print(f"  Author: {pr_data.get('author_name')}")
            print(f"  Merged: {pr_data.get('merged_at')}")
            
            # Now check what files are in PR-311
            file_expr = 'repo_name == "DataExpert-io/data-engineer-handbook" and pr_number == 311'
            file_fields = ["file_id", "language", "lines_changed"]
            
            print(f"\n🔍 Files in PR-311:")
            file_results = client.query_files(file_expr, file_fields)
            print(f"📊 Files found: {len(file_results)}")
            
            if file_results:
                print(f"📋 File list:")
                for i, file_result in enumerate(file_results):
                    print(f"  {i+1}. {file_result.get('file_id')} ({file_result.get('language')}) - Lines: {file_result.get('lines_changed')}")
            else:
                print(f"❌ No files found for PR-311")
        else:
            print(f"❌ PR-311 not found")
            
            # Check what PRs exist around 311
            print(f"\n🔍 Checking PRs around 311...")
            for pr_num in range(305, 320):
                pr_expr_range = f'repo_name == "DataExpert-io/data-engineer-handbook" and pr_number == {pr_num}'
                pr_results_range = client.query_prs(pr_expr_range, pr_fields)
                if pr_results_range:
                    pr_data = pr_results_range[0]
                    print(f"  PR #{pr_num}: {pr_data.get('title')} (Author: {pr_data.get('author_name')})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_pr_311()
