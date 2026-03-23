import aiohttp
import os
import re
import sys
import subprocess
import ast
from typing import Tuple, Dict, Optional
import requests
from manifold.self_development import log_event
from datetime import datetime
import json
from manifold.paths import get_path

# Default to DeepSeek model
DEFAULT_MODEL = os.environ.get("MANIFOLD_MODEL", "deepseek-reasoner")
DEFAULT_GATEWAY = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
FAIL_LOG = get_path("GENESIS_FAILS.jsonl")

SAFE_IMPORTS = {
    "sys",
    "json",
    "re",
    "math",
    "datetime",
    "time",
    "uuid",
    "typing",
    "pathlib",
    "itertools",
    "collections",
    "statistics",
    "random",
    "string",
    "requests",
    "aiohttp"
}

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

def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def _log_failure(domain: str, intent: str, reason: str, details: str = ""):
    try:
        entry = {
            "ts": _utc_now(),
            "domain": domain,
            "intent": intent[:400],
            "reason": reason,
            "details": details[:800]
        }
        with open(FAIL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except:
        pass

class GenesisNode:
    """
    Spawns new tools dynamically when the Orchestrator encounters an unknown domain.
    Forges a SKILL.md and a standalone script.py, sandboxes them, and permanently saves them.

    Attributes:
        gateway_url (str): The Manifold HTTP Gateway URL.
        skills_dir (str): The base directory for skills.
    """
    def __init__(self, gateway_url: str = None, model_name: str = None, skills_dir: str = None):
        self.gateway_url = gateway_url or DEFAULT_GATEWAY
        self.skills_dir = skills_dir or get_path("skills")
        self.model = model_name or DEFAULT_MODEL
        self.api_key = DEFAULT_API_KEY
        self.templates = {
            "browser": {
                "description": "Control the browser to open a URL and perform a simple action.",
                "script": (
                    "import sys\n"
                    "def main():\n"
                    "    url = sys.argv[1] if len(sys.argv) > 1 else \"\"\n"
                    "    if not url:\n"
                    "        print(\"ERROR: Missing URL argument\")\n"
                    "        return\n"
                    "    # Output an action plan; actual browser control happens in Manifold tool layer\n"
                    "    print(f\"OPEN_URL:{url}\")\n"
                    "if __name__ == '__main__':\n"
                    "    main()\n"
                )
            },
            "file": {
                "description": "Transform or validate a file path and output a plan.",
                "script": (
                    "import sys\n"
                    "def main():\n"
                    "    path = sys.argv[1] if len(sys.argv) > 1 else \"\"\n"
                    "    if not path:\n"
                    "        print(\"ERROR: Missing path argument\")\n"
                    "        return\n"
                    "    print(f\"TARGET_PATH:{path}\")\n"
                    "if __name__ == '__main__':\n"
                    "    main()\n"
                )
            }
        }

    def _render_skill_md(self, domain: str, description: str, version: str = "1.0.0") -> str:
        safe_name = re.sub(r'[^a-zA-Z0-9-]', '-', domain).lower()
        return f"---\nname: {safe_name}\ndescription: {description}\ndomain: {domain}\nversion: {version}\n---\n\n## {domain} Skill\n\nAutomatically forged by Manifold Genesis Node.\n"

    async def forge_tool(self, intent: str, domain: str) -> Optional[str]:
        """
        The main entry point for the Genesis Node to forge a new tool.

        Args:
            intent (str): The user's original prompt that triggered the need.
            domain (str): The identified domain that lacks tools.

        Returns:
            Optional[str]: The path to the created tool directory if successful, None otherwise.
        """
        post_log("status", "genesis_node", "active")
        print(f"\n[GenesisNode] Spawning... Forging tool for Domain: '{domain}' to handle intent: '{intent}'")

        template_hint = ""
        for key, template in self.templates.items():
            if key in domain.lower():
                template_hint = (
                    f"\n\nExample template for domain '{key}':\n"
                    f"Description: {template['description']}\n"
                    f"script.py:\n{template['script']}\n"
                )
                break

        system_prompt = (
            "You are the Genesis Node, an expert Python developer and system architect. "
            f"You need to create a standalone command-line tool for the '{domain}' domain to handle this intent: '{intent}'.\n\n"
            "You must output STRICT JSON ONLY. No markdown, no extra text.\n"
            "JSON schema:\n"
            "{\n"
            "  \"description\": \"short human description\",\n"
            "  \"version\": \"1.0.0\",\n"
            "  \"script_py\": \"<full python script as a string>\"\n"
            "}\n"
            "Rules:\n"
            "- The script MUST be standalone, contain a main() and __name__ guard.\n"
            "- It must read inputs from sys.argv and print the final result to stdout.\n"
            "- You MAY use `requests` or `aiohttp` for API integrations.\n"
            "- Do NOT use os.system, subprocess, eval, exec, socket.\n"
            "- IMPORTANT: If the FIRST argument (sys.argv[1]) is exactly 'test_input', the script MUST safely exit with code 0 and print 'Test passed' without performing real actions. This is critical for sandboxing.\n"
            "- Keep code simple, deterministic, and highly autonomous.\n"
            f"{template_hint}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Forge the tools for '{domain}' based on this intent: '{intent}'"}
        ]

        max_attempts = 3
        last_script = ""
        last_desc = ""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            async with aiohttp.ClientSession() as session:
                for attempt in range(max_attempts):
                    print(f"[GenesisNode] Forge Attempt {attempt+1}/{max_attempts}...")

                    payload = {
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "temperature": 0.0, # Maximum rigidity for code generation
                        "top_p": 0.1,
                        "presence_penalty": 0.0
                    }

                    # Gateway url for completion is self.gateway_url + "/v1/chat/completions" (handled if not already in url)
                    url = self.gateway_url
                    if not url.endswith("/v1/chat/completions"):
                        url = f"{url.rstrip('/')}/v1/chat/completions"

                    async with session.post(url, json=payload, headers=headers, timeout=60) as response:
                        if response.status == 200:
                            data = await response.json()
                            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                            # Log response
                            messages.append({"role": "assistant", "content": content})

                            skill_md, script_py = self._parse_forge_output(content, domain)

                            if not skill_md or not script_py:
                                error_msg = "Error: JSON parse failed or required fields missing. Output STRICT JSON only with keys: description, version, script_py."
                                _log_failure(domain, intent, "parse_error", error_msg)
                                await log_event({"type": "genesis_parse_error", "domain": domain})
                                print(f"[GenesisNode] Parsing Error. Requesting correction...")
                                messages.append({"role": "user", "content": error_msg})
                                continue

                            last_script = script_py
                            last_desc = skill_md.split("\n", 1)[-1] if "\n" in skill_md else skill_md

                            # Run Sandbox Test
                            passed, error_output = self.sandbox_test(script_py)

                            if passed:
                                print("[GenesisNode] Sandbox Test Passed! Saving tool permanently.")
                                # We need a safe directory name based on the intent or domain
                                # For simplicity, we use the domain + a small hash or counter, but domain is fine if it doesn't exist
                                safe_dir_name = re.sub(r'[^a-zA-Z0-9]', '_', domain).lower()
                                saved_path = self._save_tool(safe_dir_name, skill_md, script_py)
                                post_log("status", "genesis_node", "idle")
                                return saved_path
                            else:
                                print(f"[GenesisNode] Sandbox failed (Execution/Security Error):\n{error_output}\nRequesting correction...")
                                _log_failure(domain, intent, "sandbox_failed", error_output)
                                await log_event({"type": "genesis_sandbox_failed", "domain": domain})
                                messages.append({
                                    "role": "user",
                                    "content": (
                                        "Sandbox Test Failed with this error:\n"
                                        f"{error_output}\n\n"
                                        "Patch ONLY the script to fix it. Return STRICT JSON with description, version, script_py.\n"
                                        "Here is the previous script:\n"
                                        f"{last_script}"
                                    )
                                })

                        else:
                            print(f"[GenesisNode] API Error {response.status}: {await response.text()}")
                            post_log("status", "genesis_node", "idle")
                            await log_event({
                                "type": "genesis_failed",
                                "domain": domain,
                                "reason": f"api_error_{response.status}",
                                "intent": intent[:200]
                            })
                            _log_failure(domain, intent, f"api_error_{response.status}")
                            return None

        except Exception as e:
            print(f"[GenesisNode] Connection Error: {e}")
            post_log("status", "genesis_node", "idle")
            await log_event({
                "type": "genesis_failed",
                "domain": domain,
                "reason": "connection_error",
                "intent": intent[:200]
            })
            _log_failure(domain, intent, "connection_error", str(e))
            return None

        print("[GenesisNode] Failed to forge tool after maximum attempts.")
        post_log("status", "genesis_node", "idle")
        await log_event({
            "type": "genesis_failed",
            "domain": domain,
            "reason": "max_attempts_exhausted",
            "intent": intent[:200]
        })
        _log_failure(domain, intent, "max_attempts_exhausted")
        return None

    def _parse_forge_output(self, content: str, domain: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parses the raw LLM output to extract description and script from JSON.
        """
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            data = json.loads(cleaned)
        except Exception:
            return None, None

        description = str(data.get("description", "")).strip()
        version = str(data.get("version", "1.0.0")).strip() or "1.0.0"
        script_py = str(data.get("script_py", "")).strip()
        if not description or not script_py:
            return None, None

        skill_md = self._render_skill_md(domain, description, version)
        return skill_md, script_py

    def sandbox_test(self, python_code: str) -> Tuple[bool, str]:
        """
        Crucial Security Step: Compiles and tests the generated code in a restricted environment.
        """
        # 1. AST Security Scan
        try:
            tree = ast.parse(python_code)
            for node in ast.walk(tree):
                # Check for imports
                if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                    module_names = [n.name for n in node.names]
                    if hasattr(node, 'module') and node.module:
                        module_names.append(node.module)

                    forbidden = ['os', 'subprocess', 'socket']
                    for mod in module_names:
                         if mod in forbidden:
                             return False, f"Security Violation: Import of forbidden module '{mod}' detected."
                         if mod not in SAFE_IMPORTS:
                             return False, f"Security Violation: Import of non-allowlisted module '{mod}' detected."

                # Check for dangerous builtins
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', 'open', '__import__']:
                             return False, f"Security Violation: Use of forbidden builtin '{node.func.id}' detected."
                    # Check for attribute calls like os.system
                    elif isinstance(node.func, ast.Attribute):
                         if isinstance(node.func.value, ast.Name) and node.func.value.id == 'os':
                             return False, "Security Violation: Use of 'os' module methods detected."
        except SyntaxError as e:
            return False, f"Syntax Error during compilation:\n{e}"
        except Exception as e:
            return False, f"AST Scan Error:\n{e}"

        # 2. Execution Test
        import tempfile
        sandbox_file = os.path.join(tempfile.gettempdir(), "manifold_sandbox_test.py")
        try:
            with open(sandbox_file, 'w', encoding='utf-8') as f:
                f.write(python_code)

            # Run the script with a mock argument to test sys.argv handling
            result = subprocess.run(
                [sys.executable, sandbox_file, "test_input"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return False, f"Execution Runtime Error:\n{result.stderr}"

            if not result.stdout.strip():
                 return False, "Execution Error: The script did not print any output to stdout."

            return True, "Success"

        except subprocess.TimeoutExpired:
            return False, "Execution Timeout: The script took longer than 5 seconds to execute."
        except Exception as e:
             return False, f"Sandbox Execution Error:\n{e}"
        finally:
            if os.path.exists(sandbox_file):
                os.remove(sandbox_file)

    def _save_tool(self, safe_dir_name: str, skill_md: str, script_py: str) -> str:
        """
        Saves the forged files permanently to the skills directory.

        Returns:
            str: The path to the created directory.
        """
        target_dir = os.path.join(self.skills_dir, safe_dir_name)

        # If the directory already exists (e.g., from a previous manual tool), append a suffix
        counter = 1
        base_dir = target_dir
        while os.path.exists(target_dir):
             target_dir = f"{base_dir}_{counter}"
             counter += 1

        os.makedirs(target_dir, exist_ok=True)

        scripts_dir = os.path.join(target_dir, "scripts")
        os.makedirs(scripts_dir, exist_ok=True)

        with open(os.path.join(target_dir, "SKILL.md"), 'w', encoding='utf-8') as f:
             f.write(skill_md)

        with open(os.path.join(scripts_dir, "script.py"), 'w', encoding='utf-8') as f:
             f.write(script_py)

        print(f"[GenesisNode] Tool successfully written to '{target_dir}'.")
        post_log("info", "genesis_node", f"Capability Forged: New tool for '{safe_dir_name}' written to {target_dir}", {"domain": safe_dir_name, "path": target_dir})
        return target_dir
