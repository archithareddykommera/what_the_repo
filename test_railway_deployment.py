#!/usr/bin/env python3
"""
Test script for Railway deployment of WhatTheRepo application.
Run this to verify the application works before and after deployment.
"""

import requests
import json
import time
from datetime import datetime
import os

def test_endpoint(base_url, endpoint, expected_status=200, method="GET", data=None, description=""):
    """Test a single endpoint"""
    print(f"🔍 Testing {method} {endpoint}...")
    if description:
        print(f"   📝 {description}")
    
    try:
        if method == "GET":
            response = requests.get(f"{base_url}{endpoint}", timeout=30)
        elif method == "POST":
            response = requests.post(f"{base_url}{endpoint}", json=data, timeout=30)
        
        if response.status_code == expected_status:
            print(f"✅ {method} {endpoint} - Status: {response.status_code}")
            
            # Try to parse JSON response
            try:
                json_data = response.json()
                print(f"   📄 Response: {json.dumps(json_data, indent=2)[:300]}...")
            except:
                print(f"   📄 Response: {response.text[:300]}...")
            
            return True
        else:
            print(f"❌ {method} {endpoint} - Expected {expected_status}, got {response.status_code}")
            print(f"   📄 Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ {method} {endpoint} - Error: {e}")
        return False

def test_environment_variables():
    """Test if required environment variables are set"""
    print("🔧 Testing Environment Variables...")
    
    required_vars = [
        "MILVUS_URL",
        "MILVUS_TOKEN", 
        "COLLECTION_NAME",
        "OPENAI_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_DB_URL"
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * min(len(value), 10)}...")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ All required environment variables are set")
        return True

def main():
    """Main test function"""
    print("🚂 Railway Deployment Test - WhatTheRepo")
    print("=" * 60)
    
    # Test configuration
    base_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "http://localhost:8000")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"
    
    print(f"📍 Testing against: {base_url}")
    print(f"⏰ Test started at: {datetime.now()}")
    print()
    
    # Test environment variables
    env_test = test_environment_variables()
    print()
    
    # Test endpoints
    tests = [
        ("/", "GET", 200, None, "Home page"),
        ("/health", "GET", 200, None, "Health check"),
        ("/engineering-lens", "GET", 200, None, "Engineer Lens page"),
        ("/what-shipped", "GET", 200, None, "What Shipped page"),
        ("/api/engineers", "GET", 200, None, "Engineers API"),
        ("/api/engineer-metrics", "GET", 200, None, "Engineer metrics API"),
        ("/api/what-shipped-data", "GET", 200, None, "What shipped data API"),
        ("/api/what-shipped-summary", "GET", 200, None, "What shipped summary API"),
        ("/api/what-shipped-authors", "GET", 200, None, "What shipped authors API"),
        ("/docs", "GET", 200, None, "API documentation"),
    ]
    
    results = []
    for test in tests:
        if len(test) == 3:
            endpoint, method, expected_status = test
            data = None
            description = ""
        elif len(test) == 4:
            endpoint, method, expected_status, description = test
            data = None
        else:
            endpoint, method, expected_status, data, description = test
        
        result = test_endpoint(base_url, endpoint, expected_status, method, data, description)
        results.append((endpoint, result))
        print()
        time.sleep(1)  # Small delay between requests
    
    # Summary
    print("📊 Test Summary")
    print("=" * 60)
    passed = 0
    total = len(results)
    
    for endpoint, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {endpoint}")
        if result:
            passed += 1
    
    print()
    print(f"🎯 Results: {passed}/{total} tests passed")
    print(f"🔧 Environment: {'✅ Ready' if env_test else '❌ Issues'}")
    
    if passed == total and env_test:
        print("\n🎉 All tests passed! Your Railway deployment is working correctly.")
        print("\n📋 Deployment Status:")
        print("✅ Environment variables configured")
        print("✅ All endpoints responding")
        print("✅ Application healthy")
        print("✅ Ready for production use")
        return 0
    else:
        print("\n⚠️ Some tests failed. Check your Railway deployment.")
        if not env_test:
            print("   - Environment variables need to be configured")
        if passed < total:
            print(f"   - {total - passed} endpoints are not responding correctly")
        return 1

if __name__ == "__main__":
    exit(main())
