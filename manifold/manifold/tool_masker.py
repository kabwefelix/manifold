import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

from manifold.paths import get_path


class ToolMasker:
    """
    Load Manifold skills from the skills directory and expose them as callable tools.
    """

    def __init__(self, skills_dir: str = None):
        self.skills_dir = skills_dir or get_path("skills")

    def reload(self):
        print(f"[ToolMasker] Reloading tools from '{self.skills_dir}'...")

    def get_masked_tools(self, target_domain: str) -> List[str]:
        """
        Backward-compatible helper that returns matching skill directory names.
        """
        return [skill["directory"] for skill in self._matching_skills(target_domain)]

    def get_tool_definitions(self, target_domain: str) -> List[Dict[str, Any]]:
        """
        Return OpenAI-compatible function tool definitions for matching skills.
        """
        tool_definitions: List[Dict[str, Any]] = []
        for skill in self._matching_skills(target_domain):
            if not skill.get("script_path"):
                continue

            description = skill["description"] or f"Run the {skill['display_name']} skill."
            tool_definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": skill["tool_name"],
                        "description": description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "input": {
                                    "type": "string",
                                    "description": "Primary input string for the skill.",
                                },
                                "extra_args": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Optional extra positional arguments.",
                                },
                                "timeout": {
                                    "type": "integer",
                                    "description": "Execution timeout in seconds.",
                                    "default": 30,
                                },
                            },
                        },
                    },
                }
            )
        return tool_definitions

    def execute_skill(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        skill = self._find_skill(tool_name)
        if not skill:
            return {"error": f"Unknown skill tool: {tool_name}"}

        script_path = skill.get("script_path")
        if not script_path or not os.path.exists(script_path):
            return {"error": f"Skill script not found for {tool_name}"}

        primary_input = args.get("input")
        extra_args = args.get("extra_args", [])
        timeout = args.get("timeout", 30)

        if not isinstance(extra_args, list):
            extra_args = [str(extra_args)]

        try:
            timeout_value = max(1, min(int(timeout), 120))
        except Exception:
            timeout_value = 30

        command = [sys.executable, script_path]
        if primary_input not in (None, ""):
            command.append(str(primary_input))
        command.extend(str(item) for item in extra_args if item is not None)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_value,
                cwd=os.path.dirname(script_path),
            )
        except Exception as exc:
            return {"error": str(exc)}

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            return {
                "error": stderr or stdout or f"Skill exited with code {result.returncode}",
                "returncode": result.returncode,
            }

        return {
            "result": (stdout or stderr)[:3000],
            "tool": skill["tool_name"],
            "directory": skill["directory"],
        }

    def _matching_skills(self, target_domain: str) -> List[Dict[str, Any]]:
        skills = []
        if not os.path.isdir(self.skills_dir):
            return skills

        for item in sorted(os.listdir(self.skills_dir)):
            item_path = os.path.join(self.skills_dir, item)
            manifest = self._load_skill_manifest(item, item_path)
            if not manifest:
                continue
            if manifest["domain"] in {target_domain, "general"}:
                skills.append(manifest)

        return skills

    def _find_skill(self, tool_name: str) -> Optional[Dict[str, Any]]:
        if not os.path.isdir(self.skills_dir):
            return None

        for item in os.listdir(self.skills_dir):
            manifest = self._load_skill_manifest(item, os.path.join(self.skills_dir, item))
            if not manifest:
                continue
            if tool_name in {manifest["tool_name"], manifest["directory"]}:
                return manifest

        return None

    def _load_skill_manifest(self, directory_name: str, item_path: str) -> Optional[Dict[str, Any]]:
        if not os.path.isdir(item_path):
            return None

        skill_md_path = os.path.join(item_path, "SKILL.md")
        if not os.path.exists(skill_md_path):
            return None

        metadata = {
            "name": directory_name,
            "description": "",
            "domain": "general",
        }

        try:
            with open(skill_md_path, "r", encoding="utf-8") as handle:
                lines = handle.readlines()
        except Exception as exc:
            print(f"[ToolMasker] Error reading {skill_md_path}: {exc}")
            return None

        in_yaml = False
        for raw_line in lines:
            line = raw_line.strip()
            if line == "---":
                if not in_yaml:
                    in_yaml = True
                    continue
                break

            if not in_yaml or ":" not in line:
                continue

            key, value = line.split(":", 1)
            metadata[key.strip().lower()] = value.strip()

        script_path = os.path.join(item_path, "scripts", "script.py")
        tool_name = re.sub(r"[^a-zA-Z0-9_-]", "_", directory_name)

        return {
            "directory": directory_name,
            "display_name": metadata.get("name") or directory_name,
            "description": metadata.get("description", ""),
            "domain": metadata.get("domain", "general").lower(),
            "tool_name": tool_name,
            "script_path": script_path if os.path.exists(script_path) else None,
        }
