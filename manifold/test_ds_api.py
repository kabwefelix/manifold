import os, requests, json
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

url = "https://api.deepseek.com/v1/chat/completions"
headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

for model in ["deepseek-chat", "deepseek-reasoner"]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a desktop agent. You MUST use tools."},
            {"role": "user", "content": "Open chrome."}
        ],
        "tools": [{"type": "function", "function": {"name": "run_command", "description": "Run shell"}}]
    }
    r = requests.post(url, headers=headers, json=payload)
    print(f"Model: {model}")
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        msg = r.json()["choices"][0]["message"]
        print(f"Response: {msg.get('content', '')[:100]}")
        print(f"Tool Calls: {msg.get('tool_calls', None)}")
    else:
        print(r.text[:200])
    print("-" * 50)
