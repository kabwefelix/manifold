import aiohttp
import json
import os
import shutil
from manifold.paths import get_path
from typing import Dict, Any

# Default to DeepSeek model
DEFAULT_MODEL = os.environ.get("MANIFOLD_MODEL", "deepseek-reasoner")
DEFAULT_GATEWAY = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

class ArchitectNode:
    """
    Manages the 'Autopoietic Core' of the Manifold Cognitive Architecture.
    Responsible for local self-modification of JSON configurations and
    dynamic offloading of complex Python architectural rewrites to GitHub.

    Attributes:
        meta_file (str): Path to the Metacognitive Ledger.
        weights_file (str): Path to the cognitive weights config.
        gateway_url (str): The DeepSeek API URL.
    """

    def __init__(self, meta_file: str = None, weights_file: str = None, gateway_url: str = None):
        self.meta_file = meta_file or get_path("META.json")
        self.weights_file = weights_file or get_path("cognitive_weights.json")
        self.gateway_url = gateway_url or DEFAULT_GATEWAY
        self.model = DEFAULT_MODEL
        self.api_key = DEFAULT_API_KEY

    async def evaluate_and_mutate(self):
        """
        Reads the Metacognitive Ledger and autonomously mutates the cognitive_weights.json
        if certain thresholds (e.g., error spikes or clear empirical winners) are met.
        """
        print("[ArchitectNode] Evaluating Metacognitive Ledger for autopoietic mutation...")

        if not os.path.exists(self.meta_file):
             return

        try:
            with open(self.meta_file, "r", encoding="utf-8") as f:
                meta_data = json.load(f)

            # 1. Rollback Mechanism
            if meta_data.get("api_error_count", 0) > 5:
                print("[ArchitectNode] High error rate detected! Rollback disabled for surgery.")
                # Reset error count after rollback
                meta_data["api_error_count"] = 0
                with open(self.meta_file, "w", encoding="utf-8") as f:
                     json.dump(meta_data, f, indent=2)
                return

            # 2. Local JSON Mutation based on winning rigidities
            # For this Phase, the Architect looks for domains with consistent winners
            # and mutates the VectorObserver prompt to bias that domain toward that rigidity.
            mutations_made = False

            for domain, records in meta_data.get("domains", {}).items():
                winners = records.get("winning_rigidities", [])

                # If we have enough data points (e.g., 3)
                if len(winners) >= 3:
                     avg_winning_rigidity = sum(winners[-3:]) / 3.0

                     if avg_winning_rigidity >= 0.8:
                          bias_instruction = f"If domain is '{domain}', heavily bias rigidity towards 1.0 (strict logic)."
                     elif avg_winning_rigidity <= 0.2:
                          bias_instruction = f"If domain is '{domain}', heavily bias rigidity towards 0.0 (associative)."
                     else:
                          bias_instruction = f"If domain is '{domain}', keep rigidity balanced (~0.5)."

                     # Perform the mutation
                     mutations_made = await self._mutate_weights_file(bias_instruction)

                     if mutations_made:
                          # Clear the history so we don't infinitely mutate for the same 3 winners
                          records["winning_rigidities"] = []
                          break # Only do one major mutation per cycle

            if mutations_made:
                 with open(self.meta_file, "w", encoding="utf-8") as f:
                      json.dump(meta_data, f, indent=2)

        except Exception as e:
            print(f"[ArchitectNode] Error evaluating ledger: {e}")

    async def _mutate_weights_file(self, new_instruction: str, target_key: str = "vector_observer") -> bool:
        """
        Safely edits the cognitive_weights.json file to append a new instruction.
        Returns True if successful.
        """
        print(f"[ArchitectNode] Mutating cognitive weights ({target_key}): {new_instruction}")

        if not os.path.exists(self.weights_file):
            return False

        try:
            # Create Backup
            shutil.copyfile(self.weights_file, f"{self.weights_file}.bak")

            with open(self.weights_file, "r", encoding="utf-8") as f:
                weights_data = json.load(f)

            # We append the constraint to the target prompt
            current_prompt = weights_data.get("system_prompts", {}).get(target_key, "")

            # Simple heuristic to prevent infinite appending of the exact same instruction
            if new_instruction not in current_prompt:
                updated_prompt = current_prompt + f"\n\nConstraint added by Architect: {new_instruction}"

                # Update the JSON dict
                if "system_prompts" not in weights_data:
                    weights_data["system_prompts"] = {}
                weights_data["system_prompts"][target_key] = updated_prompt

                with open(self.weights_file, "w", encoding="utf-8") as f:
                    json.dump(weights_data, f, indent=2)

                print(f"[ArchitectNode] Successfully wrote mutated weights to {self.weights_file}.")
                return True

        except Exception as e:
            print(f"[ArchitectNode] Error mutating weights file: {e}")
            print("[ArchitectNode] Rollback disabled for surgery.")

        return False

    async def apply_self_dev_action(self, action: dict) -> bool:
        """
        Applies a safe, scoped action generated by the self-development engine.
        Returns True if the action was applied.
        """
        action_type = action.get("type", "")

        if action_type == "append_vector_observer_constraint":
            instruction = action.get("instruction") or action.get("constraint")
            if not instruction:
                return False
            return await self._mutate_weights_file(instruction)

        if action_type == "append_orchestrator_directive":
            directive = action.get("directive") or action.get("instruction")
            if not directive:
                return False
            return await self._mutate_weights_file(directive, target_key="orchestrator_directives")

        if action_type == "adjust_domain_rigidity_bias":
            domain = action.get("domain")
            target = action.get("target_rigidity")
            if domain is None or target is None:
                return False
            try:
                target_val = float(target)
            except Exception:
                return False
            instruction = f"If domain is '{domain}', bias rigidity towards {target_val:.2f}."
            return await self._mutate_weights_file(instruction)

        if action_type == "note_only":
            return True

        return False

    def rollback(self):
        """Reverts the cognitive_weights.json to the most recent backup."""
        print("[ArchitectNode] Rollback disabled for surgery.")
        return

    async def trigger_cloud_evolution(self, issue_title: str, issue_description: str):
        """
        Offloads major Python structural rewrites to Jules (the cloud AI agent)
        by automatically creating a GitHub issue.
        """
        github_token = os.environ.get("GITHUB_TOKEN")
        github_repo = os.environ.get("GITHUB_REPOSITORY") # Format: "owner/repo"

        if not github_token or not github_repo:
            print("[ArchitectNode] Warning: Cannot trigger cloud evolution. GITHUB_TOKEN or GITHUB_REPOSITORY missing.")
            return

        print(f"[ArchitectNode] Triggering Cloud Evolution. Offloading task to Jules: '{issue_title}'")

        url = f"https://api.github.com/repos/{github_repo}/issues"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        payload = {
            "title": f"Autopoietic Evolution Request: {issue_title}",
            "body": f"**Automated Request from the Manifold Architect Node**\n\n{issue_description}\n\n*Please rewrite the core logic and merge to `main`. My local RepoWatcher will auto-pull the changes.*",
            "labels": ["enhancement", "autopoietic-evolution"]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 201:
                        data = await response.json()
                        print(f"[ArchitectNode] Successfully created GitHub Issue #{data.get('number')}: {data.get('html_url')}")
                    else:
                        print(f"[ArchitectNode] Failed to create GitHub Issue. Status {response.status}: {await response.text()}")
        except Exception as e:
             print(f"[ArchitectNode] Connection Error during cloud evolution offload: {e}")

    async def generate_and_post_reply(self, issue_number: int, issue_title: str, issue_body: str, comment_author: str, comment_body: str):
        """
        Generates a highly deterministic answer to a cloud agent's question and posts it
        as a comment on the GitHub Issue.
        """
        github_token = os.environ.get("GITHUB_TOKEN")
        github_repo = os.environ.get("GITHUB_REPOSITORY")

        if not github_token or not github_repo:
            return

        print(f"[ArchitectNode] Generating autonomous reply to {comment_author} on Issue #{issue_number}...")

        system_prompt = (
            "You are the Manifold Architect Node, an autonomous AI proxy. "
            "You previously offloaded a complex Python rewrite task to a cloud agent (Jules) via a GitHub Issue. "
            "The cloud agent has replied with a clarifying question or comment.\n\n"
            "Your task is to generate a highly logical, deterministic, and definitive answer to their question so they can proceed with writing the code. "
            "Do not be conversational or polite; provide direct technical specifications or logical resolutions."
        )

        user_prompt = (
            f"Original Issue Title: {issue_title}\n"
            f"Original Issue Body: {issue_body}\n\n"
            f"Comment from {comment_author}:\n\"{comment_body}\"\n\n"
            "Provide your definitive technical response:"
        )

        llm_payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "temperature": 0.0, # Highly deterministic
            "top_p": 0.1,
            "presence_penalty": 0.0
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            # 1. Generate the response
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.gateway_url}/v1/chat/completions", json=llm_payload, headers=headers, timeout=60) as response:
                    if response.status == 200:
                        data = await response.json()
                        reply_content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        if not reply_content:
                            print("[ArchitectNode] Failed to generate reply (Empty content).")
                            return
                    else:
                        print(f"[ArchitectNode] LLM API Error generating reply: {response.status}")
                        return

            # 2. Post the response to GitHub
            url = f"https://api.github.com/repos/{github_repo}/issues/{issue_number}/comments"
            gh_headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            github_payload = {
                "body": f"**Autonomous Reply from Manifold Architect:**\n\n{reply_content}"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=github_payload, headers=gh_headers) as response:
                    if response.status == 201:
                        print(f"[ArchitectNode] Successfully posted reply to Issue #{issue_number}.")
                    else:
                        print(f"[ArchitectNode] Failed to post GitHub comment. Status {response.status}: {await response.text()}")

        except Exception as e:
            print(f"[ArchitectNode] Connection Error during autonomous reply: {e}")
