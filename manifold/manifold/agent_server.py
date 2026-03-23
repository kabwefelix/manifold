"""
Manifold Agent Server - Chat with DeepSeek and execute tools
"""
import asyncio
import json
import time
import threading
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests
import os
import subprocess
import re

from manifold.vector_observer import VectorObserver
from manifold.orchestrator import Orchestrator
from manifold.subconscious import SubconsciousEngine
from manifold.memory import Hippocampus

# DeepSeek config
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL = "deepseek-reasoner"
CHAT_MODEL = "deepseek-chat"

# Available models list
AVAILALE_MODELS = [
    "deepseek-chat",
    "deepseek-reasoner",
]

# Current active model (mutable)
ACTIVE_MODEL = {"model": CHAT_MODEL}
if os.path.exists("ACTIVE_MODEL.json"):
    try:
        with open("ACTIVE_MODEL.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if "model" in data:
                ACTIVE_MODEL["model"] = data["model"]
    except Exception:
        pass

# Shared background components
HIPPOCAMPUS = None
SUBCONSCIOUS = None

@asynccontextmanager
async def lifespan(app):
    # ── Startup ──
    global HIPPOCAMPUS, SUBCONSCIOUS
    if HIPPOCAMPUS is None:
        gateway_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        HIPPOCAMPUS = Hippocampus(gateway_url=gateway_url, model_name=ACTIVE_MODEL["model"])
    if SUBCONSCIOUS is None:
        gateway_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        SUBCONSCIOUS = SubconsciousEngine(gateway_url=gateway_url, idle_timeout=900, hippocampus=HIPPOCAMPUS)
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
import shutil

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
    def __init__(self, db_path="manifold_activity.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
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
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file to read"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates or overwrites)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to run"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch and extract content from a URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"}
                },
                "required": ["url"]
            }
        }
    }
]

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

@app.get("/")
def root():
    return {"status": "Manifold Agent running", "model": MODEL}

@app.post("/chat")
async def chat(request: ChatRequest):
    # Check if manifold is enabled
    if not MANIFOLD_ENABLED["enabled"]:
        log_activity("error", "system", "Chat rejected: Manifold is disabled")
        return {"error": "Manifold is currently disabled", "enabled": False}

    if SUBCONSCIOUS:
        SUBCONSCIOUS.reset_timer()

    STATS["total_requests"] += 1
    user_msg = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
    log_activity("request", "orchestrator", f"New chat request", {"preview": (user_msg or "")[:100]})
    set_component_status("orchestrator", "active")
    set_component_status("vector_observer", "active")

    try:
        # 1. Vector Observer Analysis
        log_activity("info", "vector_observer", "Analyzing prompt for Domain, Rigidity, and Complexity")
        observer = VectorObserver(model_name=ACTIVE_MODEL["model"])
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
        set_component_status("vector_observer", "idle")

        # 2. Orchestrator Execution
        log_activity("info", "orchestrator", f"Executing passing with complexity {complexity}")
        set_component_status("orchestrator", "active")

        orch = Orchestrator(model_name=ACTIVE_MODEL["model"])
        final_response = await orch.run(user_msg, domain, rigidity, complexity)

        set_component_status("orchestrator", "idle")
        set_component_status("synthesizer", "idle")

        log_activity("response", "synthesizer", f"Final response generated", {"preview": final_response[:100]})
        return {
            "role": "assistant",
            "content": final_response
        }

    except Exception as e:
        set_component_status("orchestrator", "idle")
        set_component_status("vector_observer", "idle")
        log_activity("error", "orchestrator", f"Execution Failed: {str(e)}")
        return {
            "role": "assistant",
            "content": f"Manifold Core Error: {str(e)}"
        }

@app.get("/tools")
def get_tools():
    return {"tools": TOOLS}

@app.get("/status")
def get_status():
    uptime = int(time.time() - STATS["uptime_start"])
    return {
        "status": "online" if MANIFOLD_ENABLED["enabled"] else "disabled",
        "model": MODEL,
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
    return {"models": AVAILALE_MODELS, "active": ACTIVE_MODEL["model"]}

@app.get("/model")
def get_model():
    return {"model": ACTIVE_MODEL["model"]}

@app.post("/model")
def set_model(request: dict):
    new_model = request.get("model", "").strip()
    if not new_model:
        raise HTTPException(status_code=400, detail="model field required")
    ACTIVE_MODEL["model"] = new_model
    if new_model not in AVAILALE_MODELS:
        AVAILALE_MODELS.append(new_model)

    # Persist the change safely
    ConfigManager.safe_save("ACTIVE_MODEL.json", ACTIVE_MODEL)

    log_activity("info", "system", f"Model changed to {new_model}")
    return {"model": ACTIVE_MODEL["model"]}

@app.post("/log")
async def post_log(request: dict):
    """Allow external components (like OpenClaw gateway) to push activity to the manifold monitor."""
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
