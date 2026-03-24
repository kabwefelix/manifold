import copy
import os
import subprocess
from typing import Any, Dict

import requests


BUILTIN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path or path relative to the current working directory.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a local file with the provided content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path or path relative to the current working directory.",
                    },
                    "content": {"type": "string", "description": "File contents to write."}
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path or path relative to the current working directory.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the current working directory and capture its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command line to execute."},
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds.",
                        "default": 30,
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch a web page and return extracted text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "HTTP or HTTPS URL to fetch."}
                },
                "required": ["url"],
            },
        },
    },
]

BUILTIN_TOOL_NAMES = {
    tool_definition["function"]["name"] for tool_definition in BUILTIN_TOOLS
}


def get_builtin_tools() -> list[dict]:
    return copy.deepcopy(BUILTIN_TOOLS)


def is_builtin_tool(tool_name: str) -> bool:
    return tool_name in BUILTIN_TOOL_NAMES


def _resolve_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(os.getcwd(), path)


def execute_builtin_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if tool_name == "read_file":
            path = _resolve_path(str(args.get("path", "")))
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                return {"result": handle.read()[:5000], "path": path}

        if tool_name == "write_file":
            path = _resolve_path(str(args.get("path", "")))
            content = str(args.get("content", ""))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
            return {"result": "File written successfully", "path": path}

        if tool_name == "list_directory":
            path = _resolve_path(str(args.get("path", ".")))
            entries = sorted(os.listdir(path))
            return {"result": "\n".join(entries[:500]), "path": path}

        if tool_name == "run_command":
            command = str(args.get("command", ""))
            timeout = max(1, min(int(args.get("timeout", 30)), 120))
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )
            output = (result.stdout + result.stderr).strip()
            return {
                "result": output[:3000],
                "returncode": result.returncode,
                "command": command,
            }

        if tool_name == "web_fetch":
            url = str(args.get("url", ""))
            response = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Manifold/1.0"},
            )
            response.raise_for_status()
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")
                text = soup.get_text(separator="\n", strip=True)
            except Exception:
                text = response.text
            return {"result": text[:3000], "url": url, "status_code": response.status_code}

        return {"error": f"Unknown builtin tool: {tool_name}"}

    except Exception as exc:
        return {"error": str(exc)}
