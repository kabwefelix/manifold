import os
from manifold.tool_masker import ToolMasker
from manifold.genesis import GenesisNode
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

if __name__ == "__main__":
    test_tool_masker()
    test_genesis_sandbox()
