import asyncio
import aiohttp
import json
import os
import re
import requests
from typing import List, Dict, Any, Tuple, Optional
from manifold.genesis import GenesisNode
from manifold.hyperparameters import Hyperparameters
from manifold.local_tools import execute_builtin_tool, get_builtin_tools, is_builtin_tool
from manifold.memory import Hippocampus
from manifold.paths import get_path
from manifold.self_development import log_event
from manifold.tool_masker import ToolMasker

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

class Synthesizer:
    """
    Performs the final dialectic synthesis call to intelligently merge multiple responses.
    Detects contradictions and initiates validation loops via the Genesis Node.

    Attributes:
        gateway_url (str): The Manifold HTTP Gateway URL.
        timeout (int): The timeout for the HTTP request in seconds.
        genesis_node (GenesisNode): Reference to the orchestrator's GenesisNode.
    """
    def __init__(self, genesis_node: GenesisNode, gateway_url: str = None, timeout: int = 60, model_name: str = None):
        self.gateway_url = gateway_url or DEFAULT_GATEWAY
        self.timeout = timeout
        self.genesis_node = genesis_node
        self.model = model_name or DEFAULT_MODEL
        self.api_key = DEFAULT_API_KEY

    def _sanitize_pivot_variable(self, pivot_variable: str) -> str:
        import re
        sanitized = pivot_variable[:100]
        sanitized = re.sub(r'[^a-zA-Z0-9\s\+\-\*\/\=\.\(\)]', '', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        sanitized = sanitized.lstrip('-')
        return sanitized

    async def _detect_contradiction(self, original_prompt: str, combined_text: str) -> str:
        """
        Uses the LLM to analyze divergent perspectives and identify any 'Pivot Variables'
        (specific facts or calculations they disagree on).
        """
        prompt = (
            f"Original Request: {original_prompt}\n\n"
            f"Perspectives:\n{combined_text}\n\n"
            "Analyze these perspectives. Do they contradict each other on any specific factual data, calculation, or core premise? "
            "If yes, reply STRICTLY with the word 'CONTRADICTION:' followed by the single specific variable, fact, or metric they disagree on. "
            "If no, reply STRICTLY with 'CONSENSUS'."
        )

        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": "You are a precise contradiction detector."}, {"role": "user", "content": prompt}],
            "temperature": 0.0,
            "stream": False
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.gateway_url}/v1/chat/completions", json=payload, headers=headers, timeout=self.timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as e:
             print(f"[Synthesizer] Contradiction Detection Error: {e}")

        return "CONSENSUS"

    def _log_metacognitive_ledger(self, domain: str, winning_rigidity: float, losing_rigidities: List[float]):
        """Logs the success rate of rigidities into META.json."""
        import json
        import os
        from datetime import datetime
        try:
            meta_path = get_path("META.json")
            if not os.path.exists(meta_path):
                return
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if domain not in data["domains"]:
                data["domains"][domain] = {"winning_rigidities": [], "losing_rigidities": []}

            data["domains"][domain]["winning_rigidities"].append(winning_rigidity)
            data["domains"][domain]["losing_rigidities"].extend(losing_rigidities)
            data["last_mutation_timestamp"] = datetime.now().isoformat()

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"[Synthesizer] Logged empirical resolution to META.json for domain '{domain}'.")
        except Exception as e:
            print(f"[Synthesizer] Failed to log META.json: {e}")

    async def _increment_api_error(self):
        """Increments the global API error count in META.json to trigger Architect rollbacks."""
        import json
        import os
        try:
            meta_path = get_path("META.json")
            if not os.path.exists(meta_path):
                return
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["api_error_count"] = data.get("api_error_count", 0) + 1
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            await log_event({"type": "api_error", "source": "synthesizer"})
        except Exception:
            pass

    async def merge(self, original_prompt: str, domain: str, thread_responses: List[Tuple[float, str]]) -> str:
        """
        Sends the diverse thread outputs back to the engine for intelligent resolution and synthesis.
        Detects epistemic friction and triggers validation if necessary.

        Args:
            original_prompt (str): The user's original query.
            domain (str): The identified domain of the prompt.
            thread_responses (List[Tuple[float, str]]): The outputs generated by the background threads, paired with their rigidities.

        Returns:
            str: The final, synthesized output.
        """
        import os, subprocess, sys

        # Unpack the list of tuples
        rigidities = [t[0] for t in thread_responses]
        responses = [t[1] for t in thread_responses]

        combined_text = "\n\n".join([f"--- Perspective {i+1} (Rigidity {rigidities[i]:.2f}) ---\n{responses[i]}" for i in range(len(responses))])

        post_log("status", "synthesizer", "active")
        print("[Synthesizer] Phase 3: Epistemic Friction Detection...")
        post_log("info", "synthesizer", "Phase 3: Epistemic Friction Detection started")
        friction_check = await self._detect_contradiction(original_prompt, combined_text)

        empirical_data = None
        pivot_variable = None

        if "CONTRADICTION:" in friction_check.upper():
            raw_pivot = friction_check.split(":", 1)[1].strip()
            pivot_variable = self._sanitize_pivot_variable(raw_pivot)
            print(f"[Synthesizer] Epistemic Friction Detected! Pivot Variable: '{pivot_variable}'")
            post_log("error", "synthesizer", "Epistemic Friction Detected!", {"pivot": pivot_variable})
            post_log("info", "genesis_node", "Spawning autonomous validation experiment...")
            await log_event({
                "type": "contradiction_detected",
                "domain": domain,
                "pivot": pivot_variable
            })

            validation_intent = f"Write a validation script to definitively find the true value of: {pivot_variable}"
            tool_path = await self.genesis_node.forge_tool(validation_intent, "validation")

            if tool_path:
                script_path = os.path.join(tool_path, "scripts", "script.py")
                if os.path.exists(script_path):
                    post_log("tool_call", "genesis_node", f"Executing validation script", {"path": script_path})
                    try:
                        result = subprocess.run([sys.executable, script_path, pivot_variable], capture_output=True, text=True, timeout=10)
                        if result.returncode == 0 and result.stdout.strip():
                            empirical_data = result.stdout.strip()
                            post_log("tool_result", "genesis_node", "Ground Truth acquired", {"data": empirical_data[:100]})
                        else:
                            post_log("error", "genesis_node", "Validation experiment failed", {"stderr": result.stderr[:100]})
                    except Exception as e:
                        post_log("error", "genesis_node", f"Error running validation script: {e}")
        else:
             post_log("info", "synthesizer", "Consensus achieved. No friction detected.")

        if empirical_data:
            synthesis_prompt = (
                f"Original Request:\n{original_prompt}\n\n"
                f"Diverse Perspectives Generated:\n{combined_text}\n\n"
                f"Internal contradiction detected regarding '{pivot_variable}'. I ran an autonomous validation experiment.\n"
                f"Ground Truth Result: {empirical_data}\n\n"
                "Task: Synthesize a final response. Weight the perspectives against the Ground Truth. "
                "You MUST begin your response explicitly with: 'Internal contradiction detected regarding [Variable]. Ran autonomous validation experiment. Result: [Data]. Conclusion: [Unified Answer].' "
                "Fill in the brackets with the correct context.\n\n"
                "AT THE VERY END of your response, on a new line, write 'WINNING_PERSPECTIVE: [N]' where N is the number (1, 2, 3...) of the perspective that was most correct."
            )
        else:
            synthesis_prompt = (
                f"Original Request:\n{original_prompt}\n\n"
                f"Diverse Perspectives Generated:\n{combined_text}\n\n"
                "Task: Synthesize the above perspectives into a single, unified, highly refined response. "
                "Resolve any friction intelligently. Do not just concatenate them; integrate their insights."
            )

        payload = {
            "model": self.model,
            "messages": [
                 {"role": "system", "content": "You are the master Synthesizer. Ensure output is highly rigorous and follows any formatting constraints."},
                 {"role": "user", "content": synthesis_prompt}
            ],
            "stream": False,
            "temperature": 0.2,
            "top_p": 0.9,
            "presence_penalty": 0.1
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.gateway_url}/v1/chat/completions", json=payload, headers=headers, timeout=self.timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        final_content = data.get("choices", [{}])[0].get("message", {}).get("content", "Error: Synthesizer response empty.")

                        # Extract the WINNING_PERSPECTIVE marker
                        if "WINNING_PERSPECTIVE:" in final_content:
                            try:
                                marker_line = [line for line in final_content.split('\n') if "WINNING_PERSPECTIVE:" in line][-1]
                                winner_index = int(''.join(filter(str.isdigit, marker_line))) - 1

                                if 0 <= winner_index < len(rigidities):
                                    winning_rig = rigidities[winner_index]
                                    losing_rigs = [r for i, r in enumerate(rigidities) if i != winner_index]
                                    self._log_metacognitive_ledger(domain, winning_rig, losing_rigs)

                                # Strip the marker from the final output shown to the user
                                final_content = "\n".join([line for line in final_content.split('\n') if "WINNING_PERSPECTIVE:" not in line]).strip()
                            except Exception as e:
                                print(f"[Synthesizer] Error parsing winning perspective: {e}")

                        post_log("status", "synthesizer", "idle")
                        return final_content
                    else:
                        print(f"[Synthesizer] Gateway API Error {response.status}: {await response.text()}")
                        await self._increment_api_error()
                        post_log("status", "synthesizer", "idle")
                        return f"Error synthesizing {len(thread_responses)} responses (Gateway Status {response.status})."
        except Exception as e:
            print(f"[Synthesizer] Connection Error: {e}")
            await self._increment_api_error()
            post_log("status", "synthesizer", "idle")
            return f"Failed to reach Manifold Gateway at {self.gateway_url}. Is it running?"

class Orchestrator:
    """
    Manages the execution flow, spawning background threads based on complexity and managing tool masking.

    Attributes:
        gateway_url (str): The Manifold HTTP Gateway URL.
        tool_masker (ToolMasker): Instance to handle dynamic skill masking.
        model_name (str): The model to use for LLM calls.
    """
    def __init__(self, api_url: str = None, gateway_url: str = None, model_name: str = None, hippocampus: Optional[Hippocampus] = None):
        self.gateway_url = gateway_url or DEFAULT_GATEWAY
        self.api_url = api_url or self.gateway_url
        self.api_key = DEFAULT_API_KEY
        self.model = model_name or DEFAULT_MODEL
        self.tool_masker = ToolMasker()
        self.genesis_node = GenesisNode(gateway_url=self.gateway_url, model_name=self.model)
        self.synthesizer = Synthesizer(
            genesis_node=self.genesis_node,
            gateway_url=self.gateway_url,
            model_name=self.model,
        )
        self.hippocampus = hippocampus or Hippocampus(gateway_url=self.gateway_url, model_name=self.model)
        self.last_genesis_failure = None

    async def _increment_api_error(self):
        """Increments the global API error count in META.json to trigger Architect rollbacks."""
        import json
        import os
        try:
            meta_path = get_path("META.json")
            if not os.path.exists(meta_path):
                return
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["api_error_count"] = data.get("api_error_count", 0) + 1
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            await log_event({"type": "api_error", "source": "orchestrator"})
        except Exception:
            pass

    def _extract_dsml_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        if not content:
            return []

        tool_calls: List[Dict[str, Any]] = []
        function_calls_match = re.search(
            r'<[|\uff5c]DSML[|\uff5c]function_calls>(.*?)</[|\uff5c]DSML[|\uff5c]function_calls>',
            content,
            re.DOTALL,
        )
        if not function_calls_match:
            return tool_calls

        invokes = re.finditer(
            r'<[|\uff5c]DSML[|\uff5c]invoke name="([^"]+)">(.*?)</[|\uff5c]DSML[|\uff5c]invoke>',
            function_calls_match.group(1),
            re.DOTALL,
        )
        for index, invoke in enumerate(invokes):
            args: Dict[str, Any] = {}
            params = re.finditer(
                r'<[|\uff5c]DSML[|\uff5c]parameter name="([^"]+)"[^>]*>(.*?)</[|\uff5c]DSML[|\uff5c]parameter>',
                invoke.group(2),
                re.DOTALL,
            )
            for param in params:
                args[param.group(1)] = param.group(2).strip()

            tool_calls.append(
                {
                    "id": f"call_dsml_{index}",
                    "type": "function",
                    "function": {
                        "name": invoke.group(1),
                        "arguments": json.dumps(args),
                    },
                }
            )

        return tool_calls

    def _parse_tool_arguments(self, raw_arguments: Any) -> Dict[str, Any]:
        if isinstance(raw_arguments, dict):
            return raw_arguments
        if isinstance(raw_arguments, str):
            try:
                parsed = json.loads(raw_arguments)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {"input": raw_arguments}
        return {}

    def _tool_signature(self, tool_call: Dict[str, Any]) -> str:
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")
        args = self._parse_tool_arguments(function.get("arguments", {}))
        try:
            serialized_args = json.dumps(args, sort_keys=True)
        except TypeError:
            serialized_args = str(args)
        return f"{tool_name}:{serialized_args}"

    def _select_builtin_tools(self, prompt: str, domain: str) -> List[Dict[str, Any]]:
        return get_builtin_tools()

    async def _finalize_after_tool_use(
        self,
        session: aiohttp.ClientSession,
        messages: List[Dict[str, Any]],
        params: Dict[str, float],
        reason: str,
        last_content: str,
    ) -> str:
        post_log("info", "orchestrator", "Finalizing after tool use", {"reason": reason})
        final_messages = messages + [
            {
                "role": "user",
                "content": (
                    "Tool execution is complete. Using only the tool results and prior context above, "
                    "write the final answer for the user now. Do not call any more tools. "
                    "If a tool failed or data is incomplete, say that briefly and give the best answer you can."
                ),
            }
        ]
        final_message = await self._request_completion(session, final_messages, params, [])
        final_content = (final_message.get("content") or "").strip()
        if final_content:
            return final_content
        return last_content or "Tool use completed, but the model did not return a final answer."

    async def _request_completion(
        self,
        session: aiohttp.ClientSession,
        messages: List[Dict[str, Any]],
        params: Dict[str, float],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": params["temperature"],
            "top_p": params["top_p"],
            "presence_penalty": params["presence_penalty"],
            "stream": False,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with session.post(
            f"{self.gateway_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        ) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(f"Gateway status {response.status}: {body[:300]}")

            data = await response.json()
            with open("debug_dump.log", "a") as f:
                f.write(f"\\n--- RAW DEEPSEEK RESPONSE ---\\n{json.dumps(data, indent=2)}\\n-----------------------------\\n")
            return data.get("choices", [{}])[0].get("message", {})

    async def execute_pass(self, prompt: str, rigidity: float, tools: List[Dict], base_system: str = "You are Manifold, an advanced cognitive architecture proxy.") -> str:
        """
        Executes a single threaded LLM pass with specific hyperparameters, tools, and injected context.
        """
        params = Hyperparameters.scale_parameters(rigidity)
        
        if "reasoner" in self.model.lower():
            tool_signatures = []
            for t in tools:
                name = t["function"]["name"]
                desc = t["function"]["description"]
                params_list = list(t["function"].get("parameters", {}).get("properties", {}).keys())
                tool_signatures.append(f"- {name}({', '.join(params_list)}): {desc}")
            
            dsml_instruction = (
                "You have tools available to interact with the OS. You MUST use them to fulfill the user's request. "
                "Since you are the Reasoner model, you MUST invoke tools using this exact XML format:\n"
                "<|DSML|function_calls>\n"
                "<|DSML|invoke name=\"tool_name\">\n"
                "<|DSML|parameter name=\"arg_name\">arg_value</|DSML|parameter>\n"
                "</|DSML|invoke>\n"
                "</|DSML|function_calls>\n\n"
                "Available tools:\n" + "\n".join(tool_signatures) + "\n\n"
                f"OVERRIDE DIRECTIVES:\n{base_system}\n\n"
            )
            messages = [
                {"role": "user", "content": dsml_instruction + prompt}
            ]
        else:
            messages = [
                {"role": "system", "content": base_system},
                {"role": "user", "content": prompt},
            ]
            
        last_content = ""
        tool_invocations: Dict[str, int] = {}

        try:
            async with aiohttp.ClientSession() as session:
                for _ in range(20):
                    message = await self._request_completion(session, messages, params, tools)
                    content = message.get("content", "") or ""
                    tool_calls = message.get("tool_calls") or self._extract_dsml_tool_calls(content)
                    last_content = content or last_content

                    is_native_tools = bool(message.get("tool_calls"))

                    assistant_message: Dict[str, Any] = {"role": "assistant"}
                    if content:
                        assistant_message["content"] = content
                    if is_native_tools and tool_calls:
                        assistant_message["tool_calls"] = tool_calls
                    messages.append(assistant_message)

                    if not tool_calls:
                        with open("debug_dump.log", "a") as f:
                            f.write(f"\\n--- EMPTY RESPONSE BLOCK DETECTED ---\\nContent: {content}\\nRaw Message: {message}\\n------------------------------------\\n")
                        return content or "Manifold returned an empty response."

                    dsml_results = []
                    forced_finalize = False
                    for tool_call in tool_calls:
                        function = tool_call.get("function", {})
                        tool_name = function.get("name", "")
                        args = self._parse_tool_arguments(function.get("arguments", {}))
                        signature = self._tool_signature(tool_call)
                        tool_invocations[signature] = tool_invocations.get(signature, 0) + 1

                        post_log("tool_call", "orchestrator", f"Executing tool '{tool_name}'", {"arguments": args})

                        if tool_invocations[signature] > 2:
                            result = {
                                "error": "Repeated identical tool call blocked to prevent a runaway loop.",
                                "tool": tool_name,
                                "arguments": args,
                            }
                            forced_finalize = True
                        elif is_builtin_tool(tool_name):
                            result = execute_builtin_tool(tool_name, args)
                        else:
                            result = self.tool_masker.execute_skill(tool_name, args)

                        event_type = "tool_result" if "error" not in result else "error"
                        log_msg = f"Tool '{tool_name}' completed" if event_type == "tool_result" else f"Tool '{tool_name}' failed"
                        post_log(event_type, "orchestrator", log_msg, result)

                        if is_native_tools:
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.get("id", tool_name),
                                    "name": tool_name,
                                    "content": json.dumps(result),
                                }
                            )
                        else:
                            dsml_results.append(f"<\uff5cDSML\uff5ctool_result name=\"{tool_name}\">\n{json.dumps(result)}\n</\uff5cDSML\uff5ctool_result>")

                    if not is_native_tools and dsml_results:
                        messages.append({
                            "role": "user",
                            "content": "\n".join(dsml_results)
                        })

                    if forced_finalize:
                        return await self._finalize_after_tool_use(
                            session,
                            messages,
                            params,
                            "duplicate_tool_call",
                            last_content,
                        )

                return await self._finalize_after_tool_use(
                    session,
                    messages,
                    params,
                    "tool_loop_limit",
                    last_content,
                )
        except Exception as e:
            print(f"[Orchestrator] Connection Error: {e}")
            post_log("error", "orchestrator", f"Execution pass failed: {e}")
            await log_event({
                "type": "api_error",
                "source": "orchestrator",
                "error": str(e)
            })
            await self._increment_api_error()
            return f"Gateway request failed: {e}"

    async def run(self, prompt: str, domain: str, rigidity: float, complexity: int) -> str:
        """
        The core execution loop of the Architect.
        Scales the number of threads and applies differential hyperparameters based on complexity.
        Injects Semantic Memory Context seamlessly before evaluation.
        """
        post_log("status", "orchestrator", "active")
        print(f"\n[Orchestrator] Running -> Domain: {domain} | Rigidity: {rigidity:.2f} | Complexity: {complexity}")

        # Ensure tools exist for this domain. If not, Genesis Node spawns them.
        domain_tools = self.tool_masker.get_tool_definitions(domain)
        if not domain_tools and domain not in ["general", "system", "introspection", "internal_state", "self_awareness"]:
            print(f"[Orchestrator] Capability gap detected for domain '{domain}'. Triggering Genesis Node...")
            post_log("info", "orchestrator", f"Capability gap detected for domain '{domain}'. Triggering Genesis Node...")
            await self.genesis_node.forge_tool(prompt, domain)
            
            # Re-fetch tools after forging
            domain_tools = self.tool_masker.get_tool_definitions(domain)
            if not domain_tools:
                 print(f"[Orchestrator] Genesis Node failed to forge tools for '{domain}'. Proceeding without tools.")
                 post_log("error", "genesis_node", f"Genesis Node failed to forge tools for '{domain}'. Proceeding without tools.")
                 self.last_genesis_failure = {
                     "domain": domain,
                     "prompt": prompt[:200]
                 }
                 await log_event({
                     "type": "genesis_failed",
                     "domain": domain,
                     "reason": "forge_failed",
                     "intent": prompt[:200]
                 })

        tools = self._select_builtin_tools(prompt, domain) + domain_tools

        # --- HIPPOCAMPUS MEMORY RETRIEVAL ---
        memory_context = await self.hippocampus.retrieve_context(prompt)
        base_system_prompt = (
            "You are Manifold, an advanced cognitive architecture proxy. "
            "You may call available tools whenever file access, shell execution, web retrieval, or skill execution "
            "would improve accuracy. Prefer tool use over guessing when the answer depends on local or external state. "
            "Prefer specialized domain tools over generic tools when they are available. "
            "For live external questions, avoid local filesystem or shell tools unless the user explicitly asks for local inspection. "
            "After you have enough tool output to answer, stop calling tools and answer directly."
        )
        if memory_context:
            base_system_prompt += f"\n\n{memory_context}\n\n"

        # Determine number of concurrent passes based on complexity
        num_passes = complexity if complexity <= 3 else 3
        tasks = []

        if num_passes == 1:
            print(f"[Orchestrator] Complexity 1: Executing single synchronous pass.")
            post_log("info", "orchestrator", f"Complexity 1: Executing single synchronous pass.")
            pass_system_prompt = base_system_prompt + "\n\n" + Hyperparameters.construct_system_prompt(rigidity, domain)
            final_output = await self.execute_pass(prompt, rigidity, tools, pass_system_prompt)
            print("\n[Orchestrator] Single pass complete.")
            self.hippocampus.add_short_term(prompt, final_output)
            post_log("status", "orchestrator", "idle")
            return final_output

        post_log("info", "orchestrator", f"Complexity {complexity}: Spawning background threads for dialectic synthesis.")

        # Calculate cognitive diversity offsets for rigidity
        # We spread the rigidity across the spectrum. For example, if complexity is 3:
        # T1: highly associative (base - 0.3), T2: base, T3: highly strict (base + 0.3)
        generated_rigidities = []
        step = 1.0 / (num_passes + 1)

        for i in range(num_passes):
            # Diverge the rigidity slightly to ensure cognitive diversity, but keep bounded 0.0-1.0
            varied_rigidity = max(0.0, min(1.0, rigidity + (step * (i - (num_passes // 2)))))
            generated_rigidities.append(varied_rigidity)
            pass_system_prompt = base_system_prompt + "\n\n" + Hyperparameters.construct_system_prompt(varied_rigidity, domain)
            tasks.append(self.execute_pass(prompt, varied_rigidity, tools, pass_system_prompt))

        # Gather responses from all active threads
        responses = await asyncio.gather(*tasks)

        # Pair rigidities with their responses
        thread_outputs = [(generated_rigidities[i], responses[i]) for i in range(len(responses)) if "Error" not in responses[i]]

        if not thread_outputs:
            post_log("status", "orchestrator", "idle")
            return "Fatal Error: All dialectic threads failed to return a valid response."

        print(f"\n[Orchestrator] All {len(thread_outputs)} threads completed. Initiating Synthesis...")

        # Initiate Synthesis
        final_output = await self.synthesizer.merge(prompt, domain, thread_outputs)

        # Add to Short Term Memory Buffer
        self.hippocampus.add_short_term(prompt, final_output)

        post_log("status", "orchestrator", "idle")
        return final_output
