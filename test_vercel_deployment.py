#!/usr/bin/env python3
"""
Test script to verify Vercel deployment functionality.
This script tests the core features that work in the Vercel environment.
"""

import os
import sys
import requests
import json
from datetime import datetime

def test_health_endpoint(base_url):
    """Test the health endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_home_page(base_url):
    """Test the home page"""
    print("🔍 Testing home page...")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        if response.status_code == 200:
            content = response.text
            if "What the repo" in content and "FastAPI" in content:
                print("✅ Home page loaded successfully")
                return True
            else:
                print("❌ Home page content not as expected")
                return False
        else:
            print(f"❌ Home page failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Home page error: {e}")
        return False

def test_repositories_endpoint(base_url):
    """Test the repositories endpoint"""
    print("🔍 Testing repositories endpoint...")
    try:
        response = requests.get(f"{base_url}/api/repositories", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Repositories endpoint: {len(data)} repositories found")
            return True
        else:
            print(f"❌ Repositories endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Repositories endpoint error: {e}")
        return False

def test_example_queries_endpoint(base_url):
    """Test the example queries endpoint"""
    print("🔍 Testing example queries endpoint...")
    try:
        response = requests.get(f"{base_url}/api/example-queries?repo=test/repo", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "queries" in data:
                print(f"✅ Example queries endpoint: {len(data['queries'])} queries found")
                return True
            else:
                print("❌ Example queries response format not as expected")
                return False
        else:
            print(f"❌ Example queries endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Example queries endpoint error: {e}")
        return False

def test_search_endpoint(base_url):
    """Test the search endpoint"""
    print("🔍 Testing search endpoint...")
    try:
        response = requests.get(
            f"{base_url}/api/search?query=test&repo_name=test/repo&limit=5", 
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Search endpoint: {len(data)} results found")
            return True
        else:
            print(f"❌ Search endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Search endpoint error: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Vercel Deployment Test")
    print("=" * 50)
    
    # Get base URL from command line or use default
    if len(sys.argv) > 1:
        base_url = sys.argv[1].rstrip('/')
    else:
        base_url = "http://localhost:8000"
    
    print(f"📍 Testing against: {base_url}")
    print(f"⏰ Test started at: {datetime.now()}")
    print()
    
    # Run tests
    tests = [
        ("Health Endpoint", lambda: test_health_endpoint(base_url)),
        ("Home Page", lambda: test_home_page(base_url)),
        ("Repositories Endpoint", lambda: test_repositories_endpoint(base_url)),
        ("Example Queries Endpoint", lambda: test_example_queries_endpoint(base_url)),
        ("Search Endpoint", lambda: test_search_endpoint(base_url)),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"🧪 {test_name}")
        print("-" * 30)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
        print()
    
    # Summary
    print("📊 Test Summary")
    print("=" * 50)
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print()
    print(f"🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Vercel deployment is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the deployment configuration.")
        return 1

if __name__ == "__main__":
    exit(main())
