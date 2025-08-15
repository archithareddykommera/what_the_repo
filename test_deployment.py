#!/usr/bin/env python3
"""
Test script to verify all dependencies are available for Railway deployment.
"""

def test_imports():
    """Test that all required dependencies can be imported."""
    try:
        print("Testing core dependencies...")
        import fastapi
        import uvicorn
        import pydantic
        print("✅ Core FastAPI dependencies imported successfully")
        
        print("Testing database dependencies...")
        import pymilvus
        import supabase
        import psycopg2
        print("✅ Database dependencies imported successfully")
        
        print("Testing AI dependencies...")
        import openai
        print("✅ AI dependencies imported successfully")
        
        print("Testing utility dependencies...")
        import numpy
        import requests
        import httpx
        import structlog
        import dotenv
        print("✅ Utility dependencies imported successfully")
        
        print("Testing application modules...")
        from time_parse import parse_time
        from router import route_query
        from milvus_client import get_milvus_client
        print("✅ Application modules imported successfully")
        
        print("🎉 All dependencies imported successfully!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    exit(0 if success else 1)
