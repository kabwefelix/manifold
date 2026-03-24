import requests
import json
import time

url = "http://127.0.0.1:18790/chat"
payload = {
    "messages": [
        {"role": "user", "content": "What are the current prices of silver and gold right now?"}
    ]
}

print("Sending request to Orchestrator...")
start = time.time()
try:
    response = requests.post(url, json=payload, timeout=120)
    print(f"Time taken: {time.time() - start:.2f} seconds")
    print(f"Status Code: {response.status_code}")
    print("\n--- RESPONSE ---")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
