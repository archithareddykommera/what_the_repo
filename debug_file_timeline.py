#!/usr/bin/env python3
"""
Debug script to check file changes across different time periods
"""

from milvus_client import get_milvus_client

def debug_file_timeline():
    try:
        # Get Milvus client
        client = get_milvus_client()
        print("✅ Milvus client connected successfully")
        
        # Check for the specific file without time constraints
        expr = 'repo_name == "DataExpert-io/data-engineer-handbook" and file_id like "%monthly_user_site_hits_job.py%"'
        fields = ["file_id", "pr_number", "merged_at"]
        
        print(f"🔍 Searching for 'monthly_user_site_hits_job.py' without time constraints...")
        print(f"   Expression: {expr}")
        
        # Query files
        results = client.query_files(expr, fields)
        print(f"📊 Files found: {len(results)}")
        
        if results:
            print(f"📋 File results:")
            for i, file_result in enumerate(results):
                print(f"  {i+1}. {file_result.get('file_id')} (PR #{file_result.get('pr_number')}) - Merged: {file_result.get('merged_at')}")
        else:
            print(f"❌ No files found with exact name 'monthly_user_site_hits_job.py'")
            
            # Try broader search
            print(f"\n🔍 Trying broader search...")
            
            # Search for files containing parts of the name
            parts = ["monthly", "user", "site", "hits", "job"]
            for part in parts:
                expr_part = f'repo_name == "DataExpert-io/data-engineer-handbook" and file_id like "%{part}%"'
                results_part = client.query_files(expr_part, fields)
                print(f"  Files containing '{part}': {len(results_part)}")
                if results_part:
                    for file_result in results_part[:3]:  # Show first 3
                        print(f"    - {file_result.get('file_id')} (PR #{file_result.get('pr_number')})")
            
            # Check for similar file names
            print(f"\n🔍 Checking for similar file patterns...")
            similar_patterns = [
                "%monthly%",
                "%user%",
                "%site%",
                "%hits%",
                "%job%",
                "%monthly_user%",
                "%user_site%",
                "%site_hits%",
                "%hits_job%"
            ]
            
            for pattern in similar_patterns:
                expr_similar = f'repo_name == "DataExpert-io/data-engineer-handbook" and file_id like "{pattern}"'
                results_similar = client.query_files(expr_similar, fields)
                if results_similar:
                    print(f"  Pattern '{pattern}': {len(results_similar)} files")
                    for file_result in results_similar[:2]:  # Show first 2
                        print(f"    - {file_result.get('file_id')} (PR #{file_result.get('pr_number')})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_file_timeline()
