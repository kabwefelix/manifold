import asyncio
import aiohttp
import os
import json
from manifold.paths import get_path
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

# Default to DeepSeek model
DEFAULT_MODEL = os.environ.get("MANIFOLD_MODEL", "deepseek-reasoner")
DEFAULT_GATEWAY = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

def post_log(event_type: str, component: str, message: str, data: dict = None):
    try:
        requests.post("http://127.0.0.1:18790/log", json={
            "type": event_type,
            "component": component,
            "message": message,
            "data": data
        }, timeout=1)
    except:
        pass

class Hippocampus:
    """
    Manifold's Native Memory System.
    Handles short-term working memory and long-term semantic consolidation 
    during Subconscious Dream Cycles.
    """
    def __init__(self, gateway_url: str = None, model_name: str = None):
        self.gateway_url = gateway_url or DEFAULT_GATEWAY
        self.model = model_name or DEFAULT_MODEL
        self.api_key = DEFAULT_API_KEY
        self.ledger_file = get_path("MEMORY_LEDGER.json")
        
        # In-memory short-term buffer (lasts for duration of active server session)
        self.short_term_buffer: List[Dict[str, str]] = []
        
        # Ensure ledger exists
        if not os.path.exists(self.ledger_file):
            with open(self.ledger_file, "w", encoding="utf-8") as f:
                json.dump({"semantic_nodes": []}, f, indent=2)
                
    def add_short_term(self, prompt: str, response: str):
        """Adds a turn to the immediate short-term buffer."""
        self.short_term_buffer.append({
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "response": response
        })
        # Keep buffer manageable (last 10 interactions)
        if len(self.short_term_buffer) > 10:
            self.short_term_buffer.pop(0)

    def _get_api_url(self) -> str:
        url = self.gateway_url
        if not url.endswith("/v1/chat/completions"):
            url = f"{url.rstrip('/')}/v1/chat/completions"
        return url

    async def retrieve_context(self, current_prompt: str) -> str:
        """
        Scans both the short-term buffer and the heavily compressed Long-Term Semantic Node Ledger
        to inject context before the Orchestrator splits threads.
        """
        post_log("status", "hippocampus", "active")
        print(f"[Hippocampus] Retrieving semantic resonance for prompt...")

        context_blocks = []

        # 1. Grab immediate short-term history directly (last 3 interactions max)
        if self.short_term_buffer:
            recent_turns = self.short_term_buffer[-3:]
            recent_text = "\n".join([f"User: {t['prompt']}\nManifold: {t['response'][:200]}..." for t in recent_turns])
            context_blocks.append(f"--- RECENT IMPLICIT CONTEXT ---\n{recent_text}")

        # 2. Check Long Term Memory Ledger
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            
            nodes = ledger.get("semantic_nodes", [])
            if nodes:
                # Ask the LLM to quickly score relevance of nodes
                system = (
                    "You are the Hippocampus Retrieval Engine. Review the following Permanent Semantic Nodes "
                    "and select ONLY those highly relevant to the User's Current Prompt. "
                    "Output the exact nodes that match, separated by newlines. If none are highly relevant, output 'NONE'."
                )
                
                nodes_text = "\n".join([f"- {n['fact']} (Certainty: {n['certainty']})" for n in nodes])
                user_msg = f"User Prompt: '{current_prompt}'\n\nSemantic Nodes:\n{nodes_text}"

                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg}
                    ],
                    "temperature": 0.0,
                    "stream": False
                }
                
                headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                async with aiohttp.ClientSession() as session:
                    async with session.post(self._get_api_url(), json=payload, headers=headers, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            relevant = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                            if relevant and relevant != "NONE":
                                context_blocks.append(f"--- PERMANENT SEMANTIC MEMORY ---\n{relevant}")
        except Exception as e:
            print(f"[Hippocampus] Error retrieving long-term memory: {e}")

        post_log("status", "hippocampus", "idle")
        
        if context_blocks:
            return "\n\n".join(context_blocks)
        return ""

    async def consolidate_memory(self):
        """
        Triggered by SubconsciousEngine during idle dream cycles.
        Compresses recent short-term buffers into permanent Semantic Nodes.
        """
        if not self.short_term_buffer:
            return

        post_log("status", "hippocampus", "active")
        print(f"[Hippocampus] Subconscious Consolidation Running on {len(self.short_term_buffer)} short-term memories...")

        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except:
            ledger = {"semantic_nodes": []}

        # Format recent history for compression
        history_text = "\n\n".join([f"Q: {t['prompt']}\nA: {t['response']}" for t in self.short_term_buffer])
        
        system = (
            "You are the Hippocampus Consolidation Engine. Review this recent conversation history between the User and Manifold. "
            "Extract ONLY permanent, absolute facts about the User (preferences, names, strict continuous state, etc) or "
            "major objective discoveries made during the chat. "
            "Format your output strictly as a JSON list of strings. If no permanent facts should be saved, output an empty list: []"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": history_text}
            ],
            "temperature": 0.1,
            "stream": False
        }

        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            async with aiohttp.ClientSession() as session:
                async with session.post(self._get_api_url(), json=payload, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        
                        # Clean JSON
                        if content.startswith("```json"): content = content[7:]
                        if content.startswith("```"): content = content[3:]
                        if content.endswith("```"): content = content[:-3]
                        
                        facts = json.loads(content.strip())
                        
                        if facts and isinstance(facts, list):
                            for f in facts:
                                # We treat new consolidations as high confidence
                                ledger["semantic_nodes"].append({
                                    "fact": str(f),
                                    "certainty": 0.9,
                                    "timestamp": datetime.now().isoformat()
                                })
                            
                            with open(self.ledger_file, "w", encoding="utf-8") as f:
                                json.dump(ledger, f, indent=2)
                            print(f"[Hippocampus] Consolidated {len(facts)} new Semantic Nodes.")
                            post_log("info", "hippocampus", f"Consolidated {len(facts)} new semantic memory nodes during dream cycle.")
                            
                            # Clear buffer after successful consolidation
                            self.short_term_buffer = []

        except Exception as e:
            print(f"[Hippocampus] Consolidation failed: {e}")

        post_log("status", "hippocampus", "idle")
