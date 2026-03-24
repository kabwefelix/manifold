import os
import asyncio
from manifold.tool_masker import ToolMasker
from manifold.genesis import GenesisNode
from manifold.local_tools import get_builtin_tools
from manifold.orchestrator import Orchestrator
import tempfile

def test_tool_masker():
    print("Testing ToolMasker YAML parsing...")
    masker = ToolMasker()
    
    # Create a dummy skill with YAML frontmatter
    dummy_dir = os.path.join(masker.skills_dir, "test-skill-xyz")
    os.makedirs(dummy_dir, exist_ok=True)
    with open(os.path.join(dummy_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: test-skill\ndescription: A test\ndomain: browser\n---\n# Test")
    
    tools = masker.get_masked_tools("browser")
    if "test-skill-xyz" in tools:
        print(" [PASS] ToolMasker successfully parsed YAML domain.")
    else:
        print(" [FAIL] ToolMasker failed to parse YAML domain.")
        
    # Cleanup
    os.remove(os.path.join(dummy_dir, "SKILL.md"))
    os.rmdir(dummy_dir)

def test_tool_masker_tool_definition_and_execution():
    print("\nTesting ToolMasker tool definitions and script execution...")
    masker = ToolMasker()

    dummy_dir = os.path.join(masker.skills_dir, "test_exec_skill")
    scripts_dir = os.path.join(dummy_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    with open(os.path.join(dummy_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: test-exec\ndescription: Echoes the input\ndomain: general\n---\n# Test")

    script_path = os.path.join(scripts_dir, "script.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(
            "import sys\n"
            "def main():\n"
            "    if len(sys.argv) > 1 and sys.argv[1] == 'test_input':\n"
            "        print('Test passed')\n"
            "        return\n"
            "    print(sys.argv[1] if len(sys.argv) > 1 else 'no input')\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )

    tool_definitions = masker.get_tool_definitions("general")
    tool_names = [tool["function"]["name"] for tool in tool_definitions]
    if "test_exec_skill" in tool_names:
        print(" [PASS] ToolMasker emitted a callable tool definition for the skill.")
    else:
        print(" [FAIL] ToolMasker did not emit a tool definition.")

    result = masker.execute_skill("test_exec_skill", {"input": "hello"})
    if result.get("result") == "hello":
        print(" [PASS] ToolMasker executed the generated script successfully.")
    else:
        print(f" [FAIL] ToolMasker execution failed: {result}")

    os.remove(script_path)
    os.rmdir(scripts_dir)
    os.remove(os.path.join(dummy_dir, "SKILL.md"))
    os.rmdir(dummy_dir)

def test_genesis_sandbox():
    print("\nTesting Genesis Sandbox with a script that uses requests...")
    genesis = GenesisNode()
    
    # This script simulates what the LLM should output based on the new prompt
    test_script = '''import sys
import requests

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "test_input":
        print("Test passed")
        sys.exit(0)
    
    # Real logic that uses requests
    try:
        r = requests.get("https://example.com")
        print(f"Got response {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
'''
    
    passed, error = genesis.sandbox_test(test_script)
    if passed:
        print(" [PASS] Genesis sandbox correctly allowed requests and passed the test_input mock execution.")
    else:
        print(f" [FAIL] Genesis sandbox failed: {error}")

def test_orchestrator_tool_loop():
    print("\nTesting Orchestrator tool execution loop with a mocked LLM response...")
    orch = Orchestrator(model_name="mock-model")
    calls = {"count": 0}

    async def fake_request_completion(session, messages, params, tools):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": "{\"path\":\"VERSION.txt\"}"
                        }
                    }
                ]
            }
        return {"content": "V1.0"}

    orch._request_completion = fake_request_completion
    result = asyncio.run(
        orch.execute_pass(
            "Read VERSION.txt and reply with only the contents.",
            0.5,
            get_builtin_tools(),
            "Use tools when needed."
        )
    )

    if result.strip() == "V1.0":
        print(" [PASS] Orchestrator executed the tool call and returned the final response.")
    else:
        print(f" [FAIL] Orchestrator tool loop failed: {result}")

def test_orchestrator_limits_builtin_tools_for_live_data():
    print("\nTesting Orchestrator builtin-tool filtering for live market data prompts...")
    orch = Orchestrator(model_name="mock-model")
    tools = orch._select_builtin_tools(
        "what are the current prices of silver and gold right now?",
        "web",
    )
    tool_names = [tool["function"]["name"] for tool in tools]

    if tool_names == ["web_fetch"]:
        print(" [PASS] Orchestrator narrowed builtin tools to web retrieval for a live external query.")
    else:
        print(f" [FAIL] Unexpected builtin tools selected: {tool_names}")

def test_orchestrator_finalizes_after_repeated_tool_calls():
    print("\nTesting Orchestrator recovery when the model repeats the same tool call...")
    orch = Orchestrator(model_name="mock-model")
    calls = {"tool_rounds": 0, "finalize_rounds": 0}

    async def fake_request_completion(session, messages, params, tools):
        if tools:
            calls["tool_rounds"] += 1
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call_{calls['tool_rounds']}",
                        "type": "function",
                        "function": {
                            "name": "list_directory",
                            "arguments": "{\"path\":\".\"}"
                        }
                    }
                ]
            }

        calls["finalize_rounds"] += 1
        return {
            "content": "Gold and silver pricing could not be resolved cleanly from tools, but the assistant recovered and produced a final answer."
        }

    orch._request_completion = fake_request_completion
    result = asyncio.run(
        orch.execute_pass(
            "what are the current prices of silver and gold right now?",
            0.5,
            get_builtin_tools(),
            "Use tools when needed."
        )
    )

    if (
        "assistant recovered" in result
        and calls["tool_rounds"] == 3
        and calls["finalize_rounds"] == 1
    ):
        print(" [PASS] Orchestrator blocked the runaway loop and forced a final answer.")
    else:
        print(f" [FAIL] Orchestrator did not recover correctly: result={result!r}, calls={calls}")

if __name__ == "__main__":
    test_tool_masker()
    test_tool_masker_tool_definition_and_execution()
    test_genesis_sandbox()
    test_orchestrator_tool_loop()
    test_orchestrator_limits_builtin_tools_for_live_data()
    test_orchestrator_finalizes_after_repeated_tool_calls()
