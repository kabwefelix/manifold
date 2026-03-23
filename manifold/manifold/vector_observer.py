import json
import ast
import aiohttp
import os
from manifold.paths import get_path
from typing import Dict, Any, Tuple

# Default to DeepSeek Reasoner
DEFAULT_MODEL = os.environ.get("MANIFOLD_MODEL", "deepseek-reasoner")
DEFAULT_API_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

class VectorObserver:
    """
    Analyzes the user's input and returns a JSON object dictating the Domain, Rigidity, and Complexity.

    Attributes:
        api_url (str): The DeepSeek API endpoint.
        model_name (str): The name of the model to use for the analysis (defaults to deepseek-reasoner).
    """

    def __init__(self, api_url: str = None, model_name: str = None):
        """
        Initializes the VectorObserver.

        Args:
            api_url (str): The base URL for the DeepSeek API.
            model_name (str): The name of the model to use.
        """
        self.api_url = api_url or DEFAULT_API_URL
        self.model_name = model_name or DEFAULT_MODEL
        self.api_key = DEFAULT_API_KEY

    def _get_system_prompt(self) -> str:
        """Loads the vector observer prompt dynamically from cognitive_weights.json."""
        default_prompt = (
            "You are the Manifold Vector Observer. Your job is to classify the user's prompt into three variables:\n"
            "1. 'domain': A string categorizing the task (e.g., 'math', 'web', 'system', 'general'). If the prompt asks about your internal state, self-awareness, or introspection, strictly classify the domain as 'introspection', 'internal_state', or 'self_awareness'.\n"
            "2. 'rigidity': A float between 0.0 and 1.0 indicating how strictly logical (1.0) or creatively associative (0.0) the response should be.\n"
            "3. 'complexity': An integer between 1 and 5 indicating the depth/parallelism required (1 = simple, 5 = highly complex synthesis).\n\n"
            "Respond ONLY with a valid, raw JSON object: {'domain': '...', 'rigidity': 0.5, 'complexity': 1}. "
            "Do not include markdown blocks, backticks, or any other text. Only the JSON object."
        )
        try:
            with open(get_path("cognitive_weights.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("system_prompts", {}).get("vector_observer", default_prompt)
        except Exception as e:
            print(f"[VectorObserver] Error reading cognitive_weights.json: {e}")
            return default_prompt

    async def analyze(self, prompt: str) -> Dict[str, Any]:
        """
        Analyzes the user's prompt using DeepSeek API.

        Args:
            prompt (str): The user's input text.

        Returns:
            Dict[str, Any]: A dictionary containing 'domain' (str), 'rigidity' (float), and 'complexity' (int).
        """
        system_prompt = self._get_system_prompt()

        # Use DeepSeek chat completions API (OpenAI-compatible)
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "stream": False
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.api_url}/v1/chat/completions", json=payload, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                        try:
                            # Clean the text just in case the model ignored the format directive
                            cleaned_text = response_text.strip()
                            if cleaned_text.startswith("```json"):
                                cleaned_text = cleaned_text[7:]
                            if cleaned_text.startswith("```"):
                                cleaned_text = cleaned_text[3:]
                            if cleaned_text.endswith("```"):
                                cleaned_text = cleaned_text[:-3]

                            # Try JSON first, then fallback to Python dict eval
                            try:
                                parsed = json.loads(cleaned_text.strip())
                            except json.JSONDecodeError:
                                # DeepSeek might return Python dict format: {'key': 'value'}
                                try:
                                    parsed = ast.literal_eval(cleaned_text.strip())
                                except:
                                    raise json.JSONDecodeError("Failed to parse", cleaned_text, 0)

                            # Validate types
                            domain = str(parsed.get("domain", "general"))
                            rigidity = float(parsed.get("rigidity", 0.5))
                            complexity = int(parsed.get("complexity", 1))

                            # Bound constraints
                            rigidity = max(0.0, min(1.0, rigidity))
                            complexity = max(1, min(5, complexity))

                            return {"domain": domain, "rigidity": rigidity, "complexity": complexity}

                        except json.JSONDecodeError as e:
                            print(f"[VectorObserver] JSON decode error: {e}. Raw response: {response_text}")
                            return {"domain": "general", "rigidity": 0.5, "complexity": 1}
                    else:
                        print(f"[VectorObserver] Error {response.status}: {await response.text()}")
                        return {"domain": "general", "rigidity": 0.5, "complexity": 1}

        except Exception as e:
            print(f"[VectorObserver] Connection error: {e}")
            return {"domain": "general", "rigidity": 0.5, "complexity": 1}
