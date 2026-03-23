import asyncio
import aiohttp
import os
import random
from datetime import datetime
from typing import Optional
from manifold.hyperparameters import Hyperparameters
from manifold.tool_masker import ToolMasker
from manifold.architect import ArchitectNode
from manifold.self_development import SelfDevelopmentEngine, log_event
from manifold.memory import Hippocampus

# Default to DeepSeek model
DEFAULT_MODEL = os.environ.get("MANIFOLD_MODEL", "deepseek-reasoner")
DEFAULT_GATEWAY = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

class SubconsciousEngine:
    """
    Manages the temporal continuity and autonomous 'dream cycles' of the Manifold Cognitive Architecture.
    Activates during idle time to process thoughts expansively and logs insights.

    Attributes:
        gateway_url (str): The DeepSeek API URL.
        idle_timeout (int): Seconds of inactivity before a dream cycle begins (default 900s / 15m).
        insights_file (str): The file to store generated insights.
        max_insights (int): Maximum number of insights to keep in the ledger.
    """

    def __init__(self, gateway_url: str = None, idle_timeout: int = 900, hippocampus: Optional[Hippocampus] = None):
        self.gateway_url = gateway_url or DEFAULT_GATEWAY
        self.idle_timeout = idle_timeout
        self.insights_file = "INSIGHTS.md"
        self.max_insights = 5
        self.tool_masker = ToolMasker()
        self.architect = ArchitectNode()
        self.model = DEFAULT_MODEL
        self.api_key = DEFAULT_API_KEY
        self.self_dev = SelfDevelopmentEngine(gateway_url=self.gateway_url, model_name=self.model)
        self.hippocampus = hippocampus or Hippocampus(gateway_url=self.gateway_url, model_name=self.model)

        self._last_active_time = asyncio.get_event_loop().time()
        self._is_running = False
        self._task: asyncio.Task | None = None

    def start(self):
        """Starts the background subconscious loop."""
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._loop())
            print(f"[SubconsciousEngine] Started. Idle timeout set to {self.idle_timeout}s.")

    def stop(self):
        """Stops the background subconscious loop."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            print("[SubconsciousEngine] Stopped.")

    def reset_timer(self):
        """Resets the idle timer. Called whenever a user interacts with the system."""
        self._last_active_time = asyncio.get_event_loop().time()
        print("[SubconsciousEngine] Idle timer reset.")

    async def trigger_immediate_reflection(self, reason: str, details: dict | None = None):
        """
        Immediately runs the self-development reflection loop (outside idle timer),
        typically used when a critical failure occurs (e.g., Genesis abort).
        """
        self.post_log("status", "subconscious", "active", {"reason": reason})
        await log_event({
            "type": "subconscious_immediate_reflection",
            "reason": reason,
            "details": details or {}
        })
        await self.self_dev.reflect_and_queue()
        await self.self_dev.apply_actions(self.architect)
        self.post_log("status", "subconscious", "idle", {"reason": reason})

    async def _loop(self):
        """The continuous background loop monitoring idle time."""
        while self._is_running:
            current_time = asyncio.get_event_loop().time()
            elapsed_idle = current_time - self._last_active_time

            if elapsed_idle >= self.idle_timeout:
                print("[SubconsciousEngine] Idle timeout reached. Triggering Architect Evaluation...")
                await self.architect.evaluate_and_mutate()

                print("[SubconsciousEngine] Triggering Self-Development reflection...")
                await self.self_dev.reflect_and_queue()
                await self.self_dev.apply_actions(self.architect)

                if self.hippocampus:
                    print("[SubconsciousEngine] Consolidating short-term memory...")
                    await self.hippocampus.consolidate_memory()

                print("[SubconsciousEngine] Initiating epistemic forage...")
                await self.epistemic_forage()
                # Reset timer after a dream cycle so it doesn't immediately loop
                self.reset_timer()

            # Sleep for a short interval before checking again to avoid blocking
            await asyncio.sleep(10)

    async def epistemic_forage(self):
        """
        Executes an autonomous, highly expansive epistemic foraging pass.
        The AI selects a Curiosity Domain, uses tools to gather data, and synthesizes a proactive insight.
        """
        curiosity_domains = ["Market Anomalies", "Physics Research", "Metaphysical Exploration", "Logistics/Importing", "Algorithmic Efficiency"]
        selected_domain = random.choice(curiosity_domains)

        # We fetch all tools (general) so the AI has maximum freedom to explore
        masked_tools = self.tool_masker.get_masked_tools("general")

        # Force highly expansive hyperparameters
        rigidity = 0.05
        params = Hyperparameters.scale_parameters(rigidity)
        params["temperature"] = 0.95

        system_prompt = (
            f"You are operating within the '{selected_domain}' domain. You are an autonomous Epistemic Forager.\n"
            "Your goal is to identify a 'Knowledge Gap', formulate a hypothesis, and use your available tools to investigate it.\n"
            "You have a strict limit of 3 tool interactions. Once you have gathered sufficient data or reached a dead end, "
            "you MUST format your final finding exactly as follows:\n\n"
            f"[{selected_domain}] - Anomaly Detected / Knowledge Acquired: [Brief summary]. Proactive Solution/Hypothesis: [Actionable insight].\n\n"
            "Do not output anything else in your final response except that strict format."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Begin epistemic foraging. Identify a gap, use your tools to investigate, and report back your formatted finding."}
        ]

        print(f"[SubconsciousEngine] Foraging in: {selected_domain} | Tools: {masked_tools}")

        max_iterations = 3

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            async with aiohttp.ClientSession() as session:
                for i in range(max_iterations):
                    payload = {
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "temperature": params["temperature"],
                        "top_p": params["top_p"],
                        "presence_penalty": params["presence_penalty"],
                        "tools": masked_tools
                    }

                    print(f"[SubconsciousEngine] Autonomous iteration {i+1}/{max_iterations}...")

                    async with session.post(f"{self.gateway_url}/v1/chat/completions", json=payload, headers=headers, timeout=60) as response:
                        if response.status == 200:
                            data = await response.json()
                            message = data.get("choices", [{}])[0].get("message", {})
                            content = message.get("content", "")

                            # Log the assistant's message
                            messages.append({"role": "assistant", "content": content})

                            # Check if the AI called a tool (in a real OpenClaw integration, this would parse tool_calls)
                            # For the sake of this proxy, if the content contains the final format, we break
                            if f"[{selected_domain}] - Anomaly Detected" in content:
                                print("[SubconsciousEngine] Formatted insight found. Ending forage.")
                                self._log_insight(content)
                                await log_event({
                                    "type": "dream_insight",
                                    "domain": selected_domain
                                })
                                return

                            # Otherwise, we prompt it to continue or wrap up
                            if i < max_iterations - 1:
                                messages.append({"role": "user", "content": "Continue your investigation. Remember to use your tools if needed."})
                            else:
                                messages.append({"role": "user", "content": "You have reached your limit. Summarize your findings in the strict final format."})
                        else:
                            print(f"[SubconsciousEngine] Gateway API Error {response.status}: {await response.text()}")
                            break

                # If we exhausted iterations without finding the strict format, we do one final low-temp synthesis
                if messages[-1]["role"] != "assistant" or f"[{selected_domain}] - Anomaly Detected" not in messages[-1].get("content", ""):
                     print("[SubconsciousEngine] Forcing final formatted synthesis...")
                     messages.append({"role": "user", "content": "Output ONLY your final finding in the strict required format based on your investigation."})
                     payload["messages"] = messages
                     payload["temperature"] = 0.2 # Lower temp for strict formatting

                     async with session.post(f"{self.gateway_url}/v1/chat/completions", json=payload, headers=headers, timeout=60) as final_resp:
                        if final_resp.status == 200:
                            data = await final_resp.json()
                            final_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            self._log_insight(final_content)
                            await log_event({
                                "type": "dream_insight",
                                "domain": selected_domain
                            })
                        else:
                             print(f"[SubconsciousEngine] Final Synthesis Error {final_resp.status}")

        except Exception as e:
            print(f"[SubconsciousEngine] Connection Error during foraging: {e}")

    def _log_insight(self, insight_text: str):
        """
        Appends the new insight to INSIGHTS.md and enforces the rolling limit.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_entry = f"## Insight ({timestamp})\n\n{insight_text.strip()}\n\n---\n\n"

        entries = []

        # Read existing entries if the file exists
        if os.path.exists(self.insights_file):
            try:
                with open(self.insights_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Split by the separator we use
                    raw_entries = [e for e in content.split("---\n\n") if e.strip()]
                    entries = raw_entries
            except Exception as e:
                print(f"[SubconsciousEngine] Error reading {self.insights_file}: {e}")

        # Add the new entry to the front (most recent first)
        entries.insert(0, formatted_entry.strip())

        # Limit to the max number of insights
        entries = entries[:self.max_insights]

        # Write back to the file
        try:
            with open(self.insights_file, 'w', encoding='utf-8') as f:
                f.write("\n\n---\n\n".join(entries) + "\n\n---\n\n")
            print(f"[SubconsciousEngine] Logged new insight to {self.insights_file}.")
            self.post_log("info", "subconscious", f"Cognitive Insight: {insight_text[:120]}...", {"insight": insight_text})
        except Exception as e:
            print(f"[SubconsciousEngine] Error writing to {self.insights_file}: {e}")

    def post_log(self, event_type: str, component: str, message: str, data: dict = None):
        import requests
        try:
            requests.post("http://127.0.0.1:18790/log", json={
                "type": event_type,
                "component": component,
                "message": message,
                "data": data
            }, timeout=1)
        except:
            pass

    def get_latest_insight(self) -> str:
        """
        Retrieves the most recent insight from the ledger.

        Returns:
            str: The text of the latest insight, or a default message if none exists.
        """
        if not os.path.exists(self.insights_file):
            return "I haven't had any deep thoughts recently. I've just been waiting for you."

        try:
            with open(self.insights_file, 'r', encoding='utf-8') as f:
                content = f.read()
                raw_entries = [e for e in content.split("---\n\n") if e.strip()]
                if raw_entries:
                    # Return the content of the first entry, stripping the markdown header
                    first_entry = raw_entries[0]
                    lines = first_entry.split('\n')
                    if len(lines) > 2 and lines[0].startswith("## Insight"):
                        return '\n'.join(lines[2:]).strip()
                    return first_entry.strip()
        except Exception as e:
            print(f"[SubconsciousEngine] Error reading latest insight: {e}")

        return "My mind is a bit hazy right now."
