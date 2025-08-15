#!/usr/bin/env python3
"""
Debug script to check what files exist in the database
"""

from milvus_client import get_milvus_client

def debug_files():
    try:
        # Get Milvus client
        client = get_milvus_client()
        print("✅ Milvus client connected successfully")
        
        # Query all files in the repository
        expr = 'repo_name == "DataExpert-io/data-engineer-handbook"'
        fields = ["file_id", "pr_number", "merged_at"]
        
        print(f"🔍 Querying all files in repository...")
        print(f"   Expression: {expr}")
        
        # Query files
        results = client.query_files(expr, fields)
        print(f"📊 Total files found: {len(results)}")
        
        if results:
            print(f"📋 Sample files:")
            for i, file_result in enumerate(results[:20]):  # Show first 20
                print(f"  {i+1}. {file_result.get('file_id', 'unknown')} (PR #{file_result.get('pr_number', 'unknown')})")
            
            # Check for files containing "monthly" or "user" or "hits" or "job"
            print(f"\n🔍 Searching for files containing keywords:")
            keywords = ["monthly", "user", "hits", "job", "site"]
            
            for keyword in keywords:
                matching_files = [f for f in results if keyword.lower() in f.get('file_id', '').lower()]
                print(f"  Files containing '{keyword}': {len(matching_files)}")
                if matching_files:
                    for file_result in matching_files[:5]:  # Show first 5
                        print(f"    - {file_result.get('file_id')} (PR #{file_result.get('pr_number')})")
            
            # Check for Python files
            python_files = [f for f in results if f.get('file_id', '').endswith('.py')]
            print(f"\n🐍 Python files found: {len(python_files)}")
            if python_files:
                print(f"  Sample Python files:")
                for i, file_result in enumerate(python_files[:10]):  # Show first 10
                    print(f"    {i+1}. {file_result.get('file_id')} (PR #{file_result.get('pr_number')})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_files()
