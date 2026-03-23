import asyncio
import aiofiles
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

SELF_DEV_EVENTS_FILE = "SELF_DEV_EVENTS.jsonl"
SELF_DEV_ACTIONS_FILE = "SELF_DEV_ACTIONS.jsonl"
SELF_DEV_HISTORY_FILE = "SELF_DEV_HISTORY.jsonl"
SELF_DEV_LOCK = asyncio.Lock()

DEFAULT_MODEL = os.environ.get("MANIFOLD_MODEL", "deepseek-reasoner")
DEFAULT_GATEWAY = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def _get_api_url(base_url: str) -> str:
    if base_url.endswith("/v1/chat/completions"):
        return base_url
    return f"{base_url.rstrip('/')}/v1/chat/completions"


async def log_event(event: Dict[str, Any]) -> None:
    """
    Appends a structured event to the self-development event log.
    """
    payload = dict(event)
    payload.setdefault("ts", _utc_now())
    async with SELF_DEV_LOCK:
        async with aiofiles.open(SELF_DEV_EVENTS_FILE, "a", encoding="utf-8") as f:
            await f.write(json.dumps(payload) + "\n")


def _read_recent_jsonl(path: str, max_lines: int) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        recent = lines[-max_lines:]
        parsed: List[Dict[str, Any]] = []
        for line in recent:
            try:
                parsed.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return parsed
    except Exception:
        return []


def _read_excerpt(path: str, max_chars: int = 2000) -> str:
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > max_chars:
            return content[:max_chars] + "\n[TRUNCATED]"
        return content
    except Exception:
        return ""


class SelfDevelopmentEngine:
    """
    Reflects on recent system events, memory, and logs to propose safe, incremental improvements.
    """

    def __init__(
        self,
        gateway_url: str = None,
        model_name: str = None,
        max_events: int = 50,
        min_confidence: float = 0.6
    ):
        self.gateway_url = gateway_url or DEFAULT_GATEWAY
        self.model = model_name or DEFAULT_MODEL
        self.api_key = DEFAULT_API_KEY
        self.max_events = max_events
        self.min_confidence = min_confidence

    async def reflect_and_queue(self) -> None:
        """
        Uses the LLM to analyze recent events/logs and propose safe actions.
        Writes actions to SELF_DEV_ACTIONS_FILE.
        """
        import aiohttp

        events = _read_recent_jsonl(SELF_DEV_EVENTS_FILE, self.max_events)
        if not events:
            return

        meta_excerpt = _read_excerpt("META.json", 1200)
        weights_excerpt = _read_excerpt("cognitive_weights.json", 1200)
        insights_excerpt = _read_excerpt("INSIGHTS.md", 1200)
        memory_excerpt = _read_excerpt("MEMORY_LEDGER.json", 1200)

        system_prompt = (
            "You are the Manifold Self-Development Analyst. "
            "Your job is to find recurring failure patterns and propose SMALL, SAFE changes. "
            "Never propose destructive or irreversible actions. "
            "Only use the allowed action schema. "
            "If no safe actions are warranted, return actions: []."
        )

        allowed_actions = (
            "Allowed action types:\n"
            "1) append_vector_observer_constraint: {type, instruction, rationale, confidence}\n"
            "2) adjust_domain_rigidity_bias: {type, domain, target_rigidity (0-1), rationale, confidence}\n"
            "3) note_only: {type, message, rationale, confidence}\n"
        )

        user_prompt = (
            "Recent Events (JSONL):\n"
            f"{json.dumps(events, indent=2)}\n\n"
            "META.json Excerpt:\n"
            f"{meta_excerpt}\n\n"
            "cognitive_weights.json Excerpt:\n"
            f"{weights_excerpt}\n\n"
            "INSIGHTS.md Excerpt:\n"
            f"{insights_excerpt}\n\n"
            "MEMORY_LEDGER.json Excerpt:\n"
            f"{memory_excerpt}\n\n"
            f"{allowed_actions}\n"
            "Return STRICT JSON only, no markdown, with the shape:\n"
            "{\n"
            "  \"findings\": [{\"pattern\": \"...\", \"evidence\": \"...\", \"severity\": \"low|medium|high\"}],\n"
            "  \"actions\": [{...}],\n"
            "  \"confidence\": 0.0\n"
            "}\n"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "temperature": 0.1,
            "top_p": 0.2,
            "presence_penalty": 0.0
        }

        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"} if self.api_key else {}
            async with aiohttp.ClientSession() as session:
                async with session.post(_get_api_url(self.gateway_url), json=payload, headers=headers, timeout=60) as response:
                    if response.status != 200:
                        await log_event({
                            "type": "self_dev_reflection_error",
                            "status": response.status
                        })
                        return

                    data = await response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    cleaned = _strip_code_fences(content)
                    try:
                        parsed = json.loads(cleaned)
                    except json.JSONDecodeError:
                        await log_event({
                            "type": "self_dev_reflection_parse_error",
                            "raw": cleaned[:500]
                        })
                        return

        except Exception as e:
            await log_event({
                "type": "self_dev_reflection_exception",
                "error": str(e)
            })
            return

        actions = parsed.get("actions", [])
        if not isinstance(actions, list) or not actions:
            await log_event({
                "type": "self_dev_reflection_complete",
                "actions_queued": 0
            })
            return

        queued = 0
        async with SELF_DEV_LOCK:
            async with aiofiles.open(SELF_DEV_ACTIONS_FILE, "a", encoding="utf-8") as f:
                for action in actions:
                    if not isinstance(action, dict):
                        continue
                    action_payload = dict(action)
                    action_payload.setdefault("ts", _utc_now())
                    action_payload.setdefault("status", "queued")
                    action_payload.setdefault("source", "self_dev_reflection")
                    await f.write(json.dumps(action_payload) + "\n")
                    queued += 1

        await log_event({
            "type": "self_dev_reflection_complete",
            "actions_queued": queued
        })

    async def apply_actions(self, architect) -> None:
        """
        Applies queued actions using the ArchitectNode, then logs results.
        """
        actions = _read_recent_jsonl(SELF_DEV_ACTIONS_FILE, 1000)
        if not actions:
            return

        history_records: List[Dict[str, Any]] = []

        for action in actions:
            confidence = action.get("confidence", 1.0)
            action_type = action.get("type", "unknown")

            if isinstance(confidence, (int, float)) and confidence < self.min_confidence:
                record = {
                    "ts": _utc_now(),
                    "type": action_type,
                    "status": "skipped_low_confidence",
                    "confidence": confidence
                }
                history_records.append(record)
                await log_event({
                    "type": "self_dev_action_skipped",
                    "action_type": action_type,
                    "confidence": confidence
                })
                continue

            try:
                applied = await architect.apply_self_dev_action(action)
            except Exception as e:
                applied = False
                history_records.append({
                    "ts": _utc_now(),
                    "type": action_type,
                    "status": "exception",
                    "error": str(e)
                })
                await log_event({
                    "type": "self_dev_action_exception",
                    "action_type": action_type,
                    "error": str(e)
                })
                continue

            status = "applied" if applied else "failed"
            history_records.append({
                "ts": _utc_now(),
                "type": action_type,
                "status": status
            })
            await log_event({
                "type": "self_dev_action_" + status,
                "action_type": action_type
            })

        if history_records:
            async with SELF_DEV_LOCK:
                async with aiofiles.open(SELF_DEV_HISTORY_FILE, "a", encoding="utf-8") as f:
                    for record in history_records:
                        await f.write(json.dumps(record) + "\n")

        # Clear the action queue after processing
        try:
            with open(SELF_DEV_ACTIONS_FILE, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass
