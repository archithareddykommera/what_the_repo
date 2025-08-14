#!/usr/bin/env python3
"""
Startup script for the GitHub PR Analyzer FastAPI application.
"""

import os
import sys

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = {
        'MILVUS_URL': 'Milvus connection URL',
        'MILVUS_TOKEN': 'Milvus authentication token', 
        'OPENAI_API_KEY': 'OpenAI API key for embeddings',
        'COLLECTION_NAME': 'Milvus collection name (optional, defaults to test_embeddings)'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if var != 'COLLECTION_NAME' and not os.getenv(var):
            missing_vars.append(f"{var} ({description})")
    
    if missing_vars:
        print("[ERROR] Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these environment variables before running the application.")
        return False
    
    return True

def main():
    """Main startup function"""
    print("=" * 60)
    print("[START] GitHub PR Analyzer - FastAPI Application")
    print("=" * 60)
    
    # Check environment variables
    if not check_environment():
        return 1
    
    collection_name = os.getenv('COLLECTION_NAME', 'test_embeddings')
    print(f"[INFO] Using Milvus collection: {collection_name}")
    print(f"[INFO] OpenAI model: text-embedding-ada-002")
    print(f"[INFO] Application will be available at: http://localhost:8000")
    print()
    
    try:
        import uvicorn
        print("[INFO] Starting FastAPI application...")
        print("[INFO] Press Ctrl+C to stop the server")
        print("=" * 60)
        
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
        
    except ImportError:
        print("[ERROR] FastAPI dependencies not installed.")
        print("Please install them with: pip install -r requirements_fastapi.txt")
        return 1
    except KeyboardInterrupt:
        print("\n[INFO] Application stopped by user")
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to start application: {e}")
        return 1

if __name__ == "__main__":
    exit(main())