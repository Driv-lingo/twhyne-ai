#!/usr/bin/env python3

import requests
import time
import json

def test_system():
    """Test the SNF-AI Windsurf system."""
    print("🧪 Testing SNF-AI Windsurf System...")
    
    base_url = "http://localhost:5002"
    
    # Test 1: Health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/status", timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Test 2: Get nodes
    print("2. Testing node listing...")
    try:
        response = requests.get(f"{base_url}/nodes", timeout=5)
        if response.status_code == 200:
            nodes = response.json()
            print(f"✅ Found {len(nodes)} nodes")
            for node in nodes:
                print(f"   - {node['name']}: {node['status']}")
        else:
            print(f"❌ Node listing failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Node listing failed: {e}")
        return False
    
    # Test 3: Simple query
    print("3. Testing simple query...")
    try:
        query_data = {
            "prompt": "What is 2+2?",
            "conversation_history": []
        }
        response = requests.post(f"{base_url}/query", json=query_data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Query successful: {result.get('result', 'No result')[:100]}...")
            print(f"   Processed by: {result.get('node_id', 'Unknown')}")
        else:
            print(f"❌ Query failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Query failed: {e}")
        return False
    
    # Test 4: Code query
    print("4. Testing code query...")
    try:
        query_data = {
            "prompt": "Write a simple Python function to add two numbers",
            "conversation_history": []
        }
        response = requests.post(f"{base_url}/query", json=query_data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Code query successful: {result.get('result', 'No result')[:100]}...")
            print(f"   Processed by: {result.get('node_id', 'Unknown')}")
        else:
            print(f"❌ Code query failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Code query failed: {e}")
        return False
    
    print("🎉 All tests passed! System is working correctly.")
    return True

if __name__ == "__main__":
    test_system()
