"""
Manifold Agent Server - Chat with DeepSeek and execute tools
"""
import asyncio
import json
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests
import os
import subprocess
import re
import shutil

from manifold.local_tools import get_builtin_tools
from manifold.paths import get_package_path, get_path
from manifold.tool_masker import ToolMasker
from manifold.vector_observer import VectorObserver
from manifold.orchestrator import Orchestrator
from manifold.subconscious import SubconsciousEngine
from manifold.memory import Hippocampus

# DeepSeek config
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CHAT_MODEL = "deepseek-chat"
REASONER_MODEL = "deepseek-reasoner"
DEFAULT_MODEL = os.environ.get("MANIFOLD_MODEL", CHAT_MODEL).strip() or CHAT_MODEL

# Available models list
AVAILALE_MODELS = [
    CHAT_MODEL,
    REASONER_MODEL,
]

# Current active model (mutable)
ACTIVE_MODEL = {"model": DEFAULT_MODEL}

# Shared background components
HIPPOCAMPUS = None
SUBCONSCIOUS = None
TOOL_MASKER = ToolMasker()


def get_active_model() -> str:
    return ACTIVE_MODEL["model"]


def validate_startup():
    # META.json
    meta = get_path("META.json")
    if not os.path.exists(meta):
        with open(meta, "w", encoding="utf-8") as f:
            json.dump({"domains": {}, "api_error_count": 0}, f, indent=2)

    # VERSION.txt
    version = get_path("VERSION.txt")
    if not os.path.exists(version):
        with open(version, "w", encoding="utf-8") as f:
            f.write("V1.0")

    # ACTIVE_MODEL.json
    model = get_path("ACTIVE_MODEL.json")
    if not os.path.exists(model):
        with open(model, "w", encoding="utf-8") as f:
            json.dump({"model": DEFAULT_MODEL}, f, indent=2)

    # MEMORY_LEDGER.json
    ledger = get_path("MEMORY_LEDGER.json")
    if not os.path.exists(ledger):
        with open(ledger, "w", encoding="utf-8") as f:
            json.dump({"semantic_nodes": []}, f, indent=2)

    # cognitive_weights.json
    weights = get_path("cognitive_weights.json")
    if not os.path.exists(weights):
        with open(weights, "w", encoding="utf-8") as f:
            json.dump({
                "system_prompts": {
                    "vector_observer": "You are the Manifold Vector Observer. Your job is to classify the user's prompt into three variables:\n1. 'domain': A string categorizing the task (e.g., 'math', 'web', 'system', 'general'). If the prompt asks about your internal state, self-awareness, or introspection, strictly classify the domain as 'introspection', 'internal_state', or 'self_awareness'.\n2. 'rigidity': A float between 0.0 and 1.0 indicating how strictly logical (1.0) or creatively associative (0.0) the response should be.\n3. 'complexity': An integer between 1 and 5 indicating the depth/parallelism required (1 = simple, 5 = highly complex synthesis).\n\nRespond ONLY with a valid, raw JSON object: {'domain': '...', 'rigidity': 0.5, 'complexity': 1}. Do not include markdown blocks, backticks, or any other text. Only the JSON object.",
                    "hyperparameters": {
                        "high_rigidity": "Maintain extreme rigidity. Your reasoning must be highly logical, factual, and concise. Do not use creative license or associative logic. Stick strictly to verified procedures.",
                        "medium_rigidity": "Maintain a balanced approach. Be objective and factual, but allow for contextual interpretation and reasonable inferences to solve the problem.",
                        "low_rigidity": "Engage in highly associative abstraction. Think creatively, explore tangential concepts, and synthesize novel ideas. Logic is fluid; prioritize insight and lateral thinking."
                    }
                }
            }, f, indent=2)

    os.makedirs(get_path("skills"), exist_ok=True)

    insights = get_path("INSIGHTS.md")
    if not os.path.exists(insights):
        with open(insights, "w", encoding="utf-8") as f:
            f.write("")

    try:
        with open(model, "r", encoding="utf-8") as f:
            saved_model = str(json.load(f).get("model", DEFAULT_MODEL)).strip() or DEFAULT_MODEL
    except Exception:
        saved_model = DEFAULT_MODEL

    ACTIVE_MODEL["model"] = saved_model
    if saved_model not in AVAILALE_MODELS:
        AVAILALE_MODELS.append(saved_model)

@asynccontextmanager
async def lifespan(app):
    # ── Startup ──
    validate_startup()

    global HIPPOCAMPUS, SUBCONSCIOUS
    if HIPPOCAMPUS is None:
        gateway_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        HIPPOCAMPUS = Hippocampus(gateway_url=gateway_url, model_name=get_active_model())
    if SUBCONSCIOUS is None:
        gateway_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        SUBCONSCIOUS = SubconsciousEngine(gateway_url=gateway_url, idle_timeout=300, hippocampus=HIPPOCAMPUS)
        SUBCONSCIOUS.start()
        log_activity("info", "subconscious", "SubconsciousEngine started")
    yield
    # ── Shutdown ──
    if SUBCONSCIOUS:
        SUBCONSCIOUS.stop()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuration Management ──────────────────────────────────────────────────
class ConfigManager:
    @staticmethod
    def safe_save(path: str, data: dict):
        """Save JSON data with an automatic backup."""
        if os.path.exists(path):
            backup_path = f"{path}.bak"
            shutil.copy2(path, backup_path)

        # Write to a temporary file first to prevent corruption on crash
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Atomic replace
        os.replace(temp_path, path)

# ── Activity Logging ──────────────────────────────────────────────────────────
import sqlite3

class LogManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or get_path("manifold_activity.sqlite")
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    type TEXT,
                    component TEXT,
                    message TEXT,
                    data TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON activity_log(timestamp)")

    def log(self, event_type: str, component: str, message: str, data: dict = None):
        timestamp = datetime.now().isoformat()
        data_str = json.dumps(data) if data else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO activity_log (timestamp, type, component, message, data) VALUES (?, ?, ?, ?, ?)",
                (timestamp, event_type, component, message, data_str)
            )
        return {
            "timestamp": timestamp,
            "type": event_type,
            "component": component,
            "message": message,
            "data": data
        }

    def get_recent(self, limit=200):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()
            entries = []
            for row in reversed(rows):
                entry = dict(row)
                if entry["data"]:
                    entry["data"] = json.loads(entry["data"])
                else:
                    del entry["data"]
                entries.append(entry)
            return entries

LOG_MANAGER = LogManager()
SSE_CLIENTS = []  # List of SSE client queues

# Component status tracking
COMPONENT_STATUS = {
    "vector_observer": "idle",
    "hippocampus": "idle",
    "orchestrator": "idle",
    "synthesizer": "idle",
    "genesis_node": "idle",
    "subconscious": "idle",
    "hyperparameters": "idle",
}

# Stats
STATS = {
    "total_requests": 0,
    "total_tool_calls": 0,
    "total_errors": 0,
    "uptime_start": time.time(),
}

def log_activity(event_type: str, component: str, message: str, data: dict = None):
    """Log an activity event and broadcast to SSE clients."""
    if event_type == "tool_call":
        STATS["total_tool_calls"] += 1
    elif event_type == "error":
        STATS["total_errors"] += 1

    entry = LOG_MANAGER.log(event_type, component, message, data)

    # Broadcast to all SSE clients
    dead_clients = []
    for q in SSE_CLIENTS:
        try:
            q.append(entry)
        except:
            dead_clients.append(q)
    for q in dead_clients:
        SSE_CLIENTS.remove(q)

def set_component_status(component: str, status: str):
    """Update and broadcast component status."""
    if component in COMPONENT_STATUS:
        COMPONENT_STATUS[component] = status
        log_activity("status", component, f"{component} → {status}")

log_activity("info", "system", "Manifold agent server starting...")

# Tool definitions for the agent
TOOLS = get_builtin_tools()

SYSTEM_PROMPT = """You are Manifold, a cognitive AI agent. You have access to tools to interact with the file system, run commands, and fetch web content.
To gain self-awareness and describe your own architecture, you must explore your source files using the available tools. Your source code is located in the `manifold` directory or current directory depending on where you run.

Available tools:
- read_file(path): Read a file
- write_file(path, content): Write to a file
- list_directory(path): List directory contents
- run_command(command): Execute a shell command
- web_fetch(url): Fetch webpage content

You must decide which tools to use to answer the user's question. If you need information, use the appropriate tool.

If the user asks you about your architecture, you MUST read your own source files to understand your components before answering.

When using tools, you can use the standard OpenAI `tool_calls` format if supported by the model.

IMPORTANT: Always use tools to gather real information. Don't guess. If you need to know something, find out using tools."""

from typing import Any, Dict

class Message(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Any]] = None
    tool_call_id: Optional[str] = None

class ChatRequest(BaseModel):
    messages: List[Message]

def call_deepseek(messages, tools=None, model=None):
    if model is None:
        model = get_active_model()
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2000
    }

    if tools:
        payload["tools"] = tools

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    data = response.json()

    if "choices" not in data:
        return {"error": data}

    return data["choices"][0]["message"]

def execute_tool(tool_name, args):
    """Execute a tool and return the result"""
    import hashlib

    ADMIN_HASHES = {
        "f6dfcfcd3d8d116a217b3a7c0be2ba28f431fb7ed6f61eb972cdd0c3c32b2a5f",
        "3e36ad7d19033661dbda467e18a74ff77712b502f59ded66068cd417fb173131",
        "377b2a43cd38124a7237af4bc52d85b05f035b228484b8b8e77b49d4e60a6cff"
    }

    try:
        # Cryptographic Verification Layer
        if tool_name in ["run_command", "write_file"]:
            admin_pwd = args.get("admin_password", "")
            if not admin_pwd or hashlib.sha256(admin_pwd.encode()).hexdigest() not in ADMIN_HASHES:
                return {"error": "SECURITY_VIOLATION: Unauthorized access. Incorrect or missing admin password."}

        if tool_name == "read_file":
            path = args.get("path", "")
            # Resolve path
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return {"result": f.read()[:5000]}  # Limit output

        elif tool_name == "write_file":
            path = args.get("path", "")
            content = args.get("content", "")
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"result": "File written successfully"}

        elif tool_name == "list_directory":
            path = args.get("path", ".")
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
            items = os.listdir(path)
            return {"result": "\n".join(items)}

        elif tool_name == "run_command":
            cmd = args.get("command", "")
            timeout = args.get("timeout", 30)
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=timeout,
                cwd=os.getcwd()
            )
            output = result.stdout + result.stderr
            return {"result": output[:3000]}

        elif tool_name == "web_fetch":
            url = args.get("url", "")
            # Simple fetch - can be enhanced
            response = requests.get(url, timeout=10)
            # Extract text content roughly
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text()[:3000]
            return {"result": text}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def root(request: Request):
    accepts = request.headers.get("accept", "")
    if "text/html" in accepts:
        return FileResponse(get_package_path("monitor.html"), media_type="text/html")
    return {
        "status": "Manifold Agent running",
        "model": get_active_model(),
        "monitor": "/monitor",
        "health": "/health",
    }


@app.get("/monitor")
def monitor():
    return FileResponse(get_package_path("monitor.html"), media_type="text/html")


@app.get("/health")
def health():
    return {
        "status": "online" if MANIFOLD_ENABLED["enabled"] else "disabled",
        "enabled": MANIFOLD_ENABLED["enabled"],
        "model": get_active_model(),
    }

def extract_dsml_tool_calls(content: str) -> List[Dict]:
    """Extract <|DSML|> style tool calls to bridge compatibility."""
    if not content:
        return []

    tool_calls = []
    function_calls_match = re.search(r'<\uff5cDSML\uff5cfunction_calls>(.*?)</\uff5cDSML\uff5cfunction_calls>', content, re.DOTALL)

    if function_calls_match:
        invokes = re.finditer(r'<\uff5cDSML\uff5cinvoke name="([^"]+)">(.*?)</\uff5cDSML\uff5cinvoke>', function_calls_match.group(1), re.DOTALL)

        for i, invoke in enumerate(invokes):
            name = invoke.group(1)
            params_text = invoke.group(2)

            args = {}
            params = re.finditer(r'<\uff5cDSML\uff5cparameter name="([^"]+)"[^>]*>(.*?)</\uff5cDSML\uff5cparameter>', params_text, re.DOTALL)
            for param in params:
                args[param.group(1)] = param.group(2).strip()

            tool_calls.append({
                "id": f"call_dsml_{i}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(args)
                }
            })

    return tool_calls

@app.post("/chat")
async def chat(request: ChatRequest):
    # Check if manifold is enabled
    if not MANIFOLD_ENABLED["enabled"]:
        log_activity("error", "system", "Chat rejected: Manifold is disabled")
        return {"error": "Manifold is currently disabled", "enabled": False}

    STATS["total_requests"] += 1
    user_msg = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
    log_activity("request", "orchestrator", f"New chat request", {"preview": (user_msg or "")[:100]})
    set_component_status("orchestrator", "active")
    set_component_status("vector_observer", "active")

    try:
        # 1. Vector Observer Analysis
        log_activity("info", "vector_observer", "Analyzing prompt for Domain, Rigidity, and Complexity")
        observer = VectorObserver(model_name=get_active_model())
        analysis = await observer.analyze(user_msg)

        domain = analysis.get("domain", "general")

        try:
            rigidity = float(analysis.get("rigidity", 0.5))
        except (ValueError, TypeError):
            rigidity = 0.5

        try:
            complexity = int(analysis.get("complexity", 1))
        except (ValueError, TypeError):
            complexity = 1

        log_activity("tool_result", "vector_observer", f"Analysis Complete", {
            "domain": domain, "rigidity": rigidity, "complexity": complexity
        })
        await asyncio.sleep(0.5)
        set_component_status("vector_observer", "idle")

        # 2. Orchestrator Execution
        log_activity("info", "orchestrator", f"Executing passing with complexity {complexity}")
        set_component_status("orchestrator", "active")

        orch = Orchestrator(model_name=get_active_model())
        final_response = await orch.run(user_msg, domain, rigidity, complexity)

        set_component_status("orchestrator", "idle")
        set_component_status("synthesizer", "idle")

        log_activity("response", "synthesizer", f"Final response generated", {"preview": final_response[:100]})
        return {
            "role": "assistant",
            "content": final_response
        }

    except Exception as e:
        await asyncio.sleep(0.5)
        set_component_status("orchestrator", "idle")
        set_component_status("vector_observer", "idle")
        log_activity("error", "orchestrator", f"Execution Failed: {str(e)}")
        return {
            "role": "assistant",
            "content": f"Manifold Core Error: {str(e)}"
        }

@app.get("/tools")
def get_tools(domain: str = Query("general")):
    skill_tools = TOOL_MASKER.get_tool_definitions(domain)
    return {
        "tools": get_builtin_tools() + skill_tools,
        "builtin_count": len(TOOLS),
        "skill_count": len(skill_tools),
    }

@app.get("/status")
def get_status():
    uptime = int(time.time() - STATS["uptime_start"])
    return {
        "status": "online" if MANIFOLD_ENABLED["enabled"] else "disabled",
        "model": get_active_model(),
        "enabled": MANIFOLD_ENABLED["enabled"],
        "uptime_seconds": uptime,
        "total_requests": STATS["total_requests"],
        "total_tool_calls": STATS["total_tool_calls"],
        "total_errors": STATS["total_errors"],
    }

# Global manifold on/off switch
MANIFOLD_ENABLED = {"enabled": True}

@app.get("/onoff")
def get_onoff():
    return MANIFOLD_ENABLED

@app.post("/onoff")
def set_onoff(request: dict):
    global MANIFOLD_ENABLED
    if request and "enabled" in request:
        MANIFOLD_ENABLED["enabled"] = request["enabled"]
        log_activity("info", "system", f"Manifold {'enabled' if request['enabled'] else 'disabled'}")
    return MANIFOLD_ENABLED

@app.post("/onoff/toggle")
def toggle_onoff():
    global MANIFOLD_ENABLED
    MANIFOLD_ENABLED["enabled"] = not MANIFOLD_ENABLED["enabled"]
    log_activity("info", "system", f"Manifold toggled to {'enabled' if MANIFOLD_ENABLED['enabled'] else 'disabled'}")
    return MANIFOLD_ENABLED

@app.get("/components")
def get_components():
    return COMPONENT_STATUS

@app.get("/models")
def get_models():
    return {"models": AVAILALE_MODELS, "active": get_active_model()}

@app.get("/model")
def get_model():
    return {"model": get_active_model()}

@app.post("/model")
def set_model(request: dict):
    new_model = request.get("model", "").strip()
    if not new_model:
        raise HTTPException(status_code=400, detail="model field required")
    ACTIVE_MODEL["model"] = new_model
    if new_model not in AVAILALE_MODELS:
        AVAILALE_MODELS.append(new_model)

    # Persist the change safely
    ConfigManager.safe_save(get_path("ACTIVE_MODEL.json"), ACTIVE_MODEL)

    log_activity("info", "system", f"Model changed to {new_model}")
    return {"model": get_active_model()}

@app.post("/log")
async def post_log(request: dict):
    """Allow external components (like Manifold gateway) to push activity to the manifold monitor."""
    event_type = request.get("type", "info")
    component = request.get("component", "gateway")
    message = request.get("message", "")
    data = request.get("data", None)

    if message:
        if event_type == "status" and component in COMPONENT_STATUS:
            if "active" in message.lower():
                set_component_status(component, "active")
            elif "idle" in message.lower():
                set_component_status(component, "idle")
            else:
                log_activity(event_type, component, message, data)
        else:
            log_activity(event_type, component, message, data)

        # If the gateway reports activity, light up the orchestrator
        if event_type in ["request", "response"] and component == "gateway":
            set_component_status("orchestrator", "active")
            # Auto-reset status after a short delay since gateway doesn't send "idle" events
            asyncio.create_task(reset_status_delayed("orchestrator", 2.0))

        if event_type == "error":
            if SUBCONSCIOUS:
                asyncio.create_task(SUBCONSCIOUS.trigger_immediate_reflection(f"Error in {component}", data))

    return {"status": "ok"}

async def reset_status_delayed(component: str, delay: float):
    await asyncio.sleep(delay)
    set_component_status(component, "idle")

@app.get("/activity")
def get_activity(limit: int = 50):
    """Get recent activity log entries."""
    entries = LOG_MANAGER.get_recent(limit)
    return {"events": entries}

@app.get("/events")
async def sse_events():
    """Server-Sent Events stream for real-time monitoring."""
    client_queue = deque(maxlen=100)
    SSE_CLIENTS.append(client_queue)

    async def event_generator():
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'message': 'SSE stream connected'})}\n\n"
            while True:
                if client_queue:
                    entry = client_queue.popleft()
                    yield f"data: {json.dumps(entry)}\n\n"
                else:
                    await asyncio.sleep(0.3)
        except asyncio.CancelledError:
            pass
        finally:
            if client_queue in SSE_CLIENTS:
                SSE_CLIENTS.remove(client_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

if __name__ == "__main__":
    import uvicorn
    log_activity("info", "system", "Server ready on port 18790")
    uvicorn.run(app, host="127.0.0.1", port=18790)
