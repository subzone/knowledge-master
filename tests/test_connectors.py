"""Tests for connector framework."""
from knowledge_master.connectors import MCPSource, SOURCES, add_custom_source, _parse_mcp_result


def test_preconfigured_sources_exist():
    assert "outlook" in SOURCES
    assert "slack" in SOURCES


def test_source_has_required_fields():
    for name, source in SOURCES.items():
        assert source.name, f"{name} missing name"
        assert source.command, f"{name} missing command"
        assert source.tool_name, f"{name} missing tool_name"
        assert source.source_type, f"{name} missing source_type"


def test_add_custom_source():
    add_custom_source("test-source", ["echo", "hi"], "get_data", {"limit": 10}, "custom")
    assert "test-source" in SOURCES
    assert SOURCES["test-source"].tool_name == "get_data"
    # Cleanup
    del SOURCES["test-source"]


def test_parse_mcp_result_json_list():
    class FakeContent:
        text = '[{"title": "hello", "body": "world"}]'

    class FakeResult:
        content = [FakeContent()]

    items = _parse_mcp_result(FakeResult())
    assert len(items) == 1
    assert items[0]["title"] == "hello"


def test_parse_mcp_result_json_dict_with_results():
    class FakeContent:
        text = '{"results": [{"text": "a"}, {"text": "b"}]}'

    class FakeResult:
        content = [FakeContent()]

    items = _parse_mcp_result(FakeResult())
    assert len(items) == 2


def test_parse_mcp_result_plain_text():
    class FakeContent:
        text = "just plain text"

    class FakeResult:
        content = [FakeContent()]

    items = _parse_mcp_result(FakeResult())
    assert len(items) == 1
    assert items[0]["text"] == "just plain text"
