import sys
from unittest.mock import MagicMock

# Mock dependencies to allow importing agent_server
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.middleware.cors"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["bs4"] = MagicMock()

# Mock pydantic to avoid typing issues with BaseModel
pydantic_mock = MagicMock()
class MockBaseModel:
    pass
pydantic_mock.BaseModel = MockBaseModel
sys.modules["pydantic"] = pydantic_mock

sys.modules["manifold.vector_observer"] = MagicMock()
sys.modules["manifold.orchestrator"] = MagicMock()
sys.modules["manifold.subconscious"] = MagicMock()
sys.modules["manifold.memory"] = MagicMock()

import json
from manifold.agent_server import extract_dsml_tool_calls

def test_extract_empty_content():
    assert extract_dsml_tool_calls("") == []
    assert extract_dsml_tool_calls(None) == []

def test_extract_no_tags():
    assert extract_dsml_tool_calls("Hello, this is just some text.") == []

def test_extract_single_tool_no_params():
    content = "Summary: I will read the file.\n<｜DSML｜function_calls><｜DSML｜invoke name=\"read_file\"></｜DSML｜invoke></｜DSML｜function_calls>\nEnd of message."
    result = extract_dsml_tool_calls(content)
    assert len(result) == 1
    assert result[0]["id"] == "call_dsml_0"
    assert result[0]["type"] == "function"
    assert result[0]["function"]["name"] == "read_file"
    assert json.loads(result[0]["function"]["arguments"]) == {}

def test_extract_single_tool_with_params():
    content = '<｜DSML｜function_calls><｜DSML｜invoke name="write_file"><｜DSML｜parameter name="path">test.txt</｜DSML｜parameter><｜DSML｜parameter name="content">hello world</｜DSML｜parameter></｜DSML｜invoke></｜DSML｜function_calls>'
    result = extract_dsml_tool_calls(content)
    assert len(result) == 1
    assert result[0]["id"] == "call_dsml_0"
    assert result[0]["function"]["name"] == "write_file"
    args = json.loads(result[0]["function"]["arguments"])
    assert args == {"path": "test.txt", "content": "hello world"}

def test_extract_multiple_tool_calls():
    content = '''
<｜DSML｜function_calls>
<｜DSML｜invoke name="list_directory">
<｜DSML｜parameter name="path">.</｜DSML｜parameter>
</｜DSML｜invoke>
<｜DSML｜invoke name="run_command">
<｜DSML｜parameter name="command">ls -la</｜DSML｜parameter>
</｜DSML｜invoke>
</｜DSML｜function_calls>
'''
    result = extract_dsml_tool_calls(content)
    assert len(result) == 2
    assert result[0]["id"] == "call_dsml_0"
    assert result[0]["function"]["name"] == "list_directory"
    assert result[1]["id"] == "call_dsml_1"
    assert result[1]["function"]["name"] == "run_command"

def test_extract_ignores_outside_content():
    content = "Pre-content<｜DSML｜function_calls><｜DSML｜invoke name=\"test\"></｜DSML｜invoke></｜DSML｜function_calls>Post-content"
    result = extract_dsml_tool_calls(content)
    assert len(result) == 1
    assert result[0]["function"]["name"] == "test"

def test_extract_malformed_tags():
    # Missing closing tag for function_calls
    content = "<｜DSML｜function_calls><｜DSML｜invoke name=\"test\"></｜DSML｜invoke>"
    assert extract_dsml_tool_calls(content) == []

    # Mismatched tag (using standard pipe | instead of fullwidth ｜)
    content = "<|DSML|function_calls><|DSML|invoke name=\"test\"></|DSML|invoke></|DSML|function_calls>"
    assert extract_dsml_tool_calls(content) == []
