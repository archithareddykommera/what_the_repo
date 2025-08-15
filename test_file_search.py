#!/usr/bin/env python3
"""
Test script to check file search without time constraints
"""

from milvus_client import get_milvus_client
import datetime

def test_file_search():
    try:
        # Get Milvus client
        client = get_milvus_client()
        print("✅ Milvus client connected successfully")
        
        # Test 1: Search for the file without time constraints
        expr_no_time = 'repo_name == "DataExpert-io/data-engineer-handbook" and file_id like "%monthly_user_site_hits_job.py%"'
        fields = ["file_id", "pr_number", "merged_at"]
        
        print(f"🔍 Test 1: Search without time constraints")
        print(f"   Expression: {expr_no_time}")
        
        results_no_time = client.query_files(expr_no_time, fields)
        print(f"📊 Files found: {len(results_no_time)}")
        
        if results_no_time:
            print(f"📋 File results:")
            for i, file_result in enumerate(results_no_time):
                merge_time = file_result.get('merged_at')
                merge_date = datetime.datetime.fromtimestamp(merge_time) if merge_time else "Unknown"
                print(f"  {i+1}. {file_result.get('file_id')} (PR #{file_result.get('pr_number')}) - Merged: {merge_date}")
        
        # Test 2: Check what time range we need
        print(f"\n🔍 Test 2: Check time ranges")
        
        # Get all files in the repo to see the time range
        expr_all = 'repo_name == "DataExpert-io/data-engineer-handbook"'
        results_all = client.query_files(expr_all, ["merged_at"])
        
        if results_all:
            merge_times = [r.get('merged_at') for r in results_all if r.get('merged_at')]
            if merge_times:
                min_time = min(merge_times)
                max_time = max(merge_times)
                min_date = datetime.datetime.fromtimestamp(min_time)
                max_date = datetime.datetime.fromtimestamp(max_time)
                
                print(f"   Earliest merge: {min_date} ({min_time})")
                print(f"   Latest merge: {max_date} ({max_time})")
                
                # Check if PR-311 is in this range
                pr_311_time = 1751307789  # From debug output
                pr_311_date = datetime.datetime.fromtimestamp(pr_311_time)
                print(f"   PR-311 merge time: {pr_311_date} ({pr_311_time})")
                
                if min_time <= pr_311_time <= max_time:
                    print(f"   ✅ PR-311 is within the data range")
                else:
                    print(f"   ❌ PR-311 is outside the data range")
        
        # Test 3: Search with a very wide time range
        print(f"\n🔍 Test 3: Search with wide time range")
        
        # Use a very wide time range (last 2 years)
        now = datetime.datetime.now()
        start_time = int((now - datetime.timedelta(days=730)).timestamp())
        end_time = int(now.timestamp())
        
        expr_wide = f'merged_at >= {start_time} and merged_at <= {end_time} and repo_name == "DataExpert-io/data-engineer-handbook" and file_id like "%monthly_user_site_hits_job.py%"'
        
        print(f"   Expression: {expr_wide}")
        print(f"   Time range: {datetime.datetime.fromtimestamp(start_time)} to {datetime.datetime.fromtimestamp(end_time)}")
        
        results_wide = client.query_files(expr_wide, fields)
        print(f"📊 Files found: {len(results_wide)}")
        
        if results_wide:
            print(f"📋 File results:")
            for i, file_result in enumerate(results_wide):
                merge_time = file_result.get('merged_at')
                merge_date = datetime.datetime.fromtimestamp(merge_time) if merge_time else "Unknown"
                print(f"  {i+1}. {file_result.get('file_id')} (PR #{file_result.get('pr_number')}) - Merged: {merge_date}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_file_search()
