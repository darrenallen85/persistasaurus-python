#!/usr/bin/env python
"""Quick API test script."""
import urllib.request
import json

def test_api():
    base_url = "http://localhost:8000"
    
    print("Testing Persistasaurus API...")
    print("=" * 50)
    
    # Test 1: Create an execution
    print("\n1. Creating an execution...")
    data = {"workflow": "example", "input": "test data"}
    req = urllib.request.Request(
        f"{base_url}/executions",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            execution_id = result["id"]
            print(f"✓ Created execution: {execution_id}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return
    
    # Test 2: List executions
    print("\n2. Listing executions...")
    try:
        with urllib.request.urlopen(f"{base_url}/executions") as resp:
            executions = json.loads(resp.read().decode())
            print(f"✓ Found {len(executions)} execution(s)")
            for ex in executions:
                print(f"  - {ex['id']}: {ex['status']}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return
    
    # Test 3: Get specific execution
    print(f"\n3. Getting execution {execution_id}...")
    try:
        with urllib.request.urlopen(f"{base_url}/executions/{execution_id}") as resp:
            execution = json.loads(resp.read().decode())
            print(f"✓ Execution status: {execution['status']}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return
    
    # Test 4: Append a step
    print(f"\n4. Appending a step to execution {execution_id}...")
    step_data = {"step": "process", "data": "processing..."}
    req = urllib.request.Request(
        f"{base_url}/executions/{execution_id}/steps",
        data=json.dumps(step_data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            print(f"✓ Step added: {result}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return
    
    # Test 5: Mark as completed
    print(f"\n5. Marking execution {execution_id} as completed...")
    complete_data = {"result": {"status": "success", "output": "all done!"}}
    req = urllib.request.Request(
        f"{base_url}/executions/{execution_id}/complete",
        data=json.dumps(complete_data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            print(f"✓ Completed: {result}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return
    
    # Test 6: Verify completion
    print(f"\n6. Verifying final status...")
    try:
        with urllib.request.urlopen(f"{base_url}/executions/{execution_id}") as resp:
            execution = json.loads(resp.read().decode())
            print(f"✓ Final status: {execution['status']}")
            print(f"✓ Result: {execution['result']}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return
    
    print("\n" + "=" * 50)
    print("All tests passed! ✓")

if __name__ == "__main__":
    test_api()
