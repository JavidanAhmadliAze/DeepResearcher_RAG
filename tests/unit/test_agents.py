from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# model_wrapper helpers — no network calls needed
# ---------------------------------------------------------------------------

def test_content_to_text_string():
    from src.llm.model_wrapper import _content_to_text
    assert _content_to_text("hello") == "hello"


def test_content_to_text_list():
    from src.llm.model_wrapper import _content_to_text
    assert _content_to_text(["hello", {"text": " world"}]) == "hello world"


def test_content_to_text_unknown_type():
    from src.llm.model_wrapper import _content_to_text
    assert _content_to_text(42) == "42"


def test_extract_json_object_from_markdown():
    from src.llm.model_wrapper import _extract_json_object
    text = 'Here is the result: ```json\n{"key": "value"}\n```'
    assert _extract_json_object(text) == '{"key": "value"}'


def test_extract_json_object_bare():
    from src.llm.model_wrapper import _extract_json_object
    assert _extract_json_object('  {"a": 1}  ') == '{"a": 1}'


def test_extract_json_object_invalid_raises():
    from src.llm.model_wrapper import _extract_json_object
    with pytest.raises(ValueError):
        _extract_json_object("no json here")


# ---------------------------------------------------------------------------
# create_model — mock ChatOpenAI so no real API key or network is needed
# ---------------------------------------------------------------------------

@patch("src.llm.model_wrapper.ChatOpenAI")
def test_create_model_default_routing(mock_chat_openai):
    mock_instance = MagicMock()
    mock_instance.model_name = "deepseek-chat"
    mock_instance.streaming = True
    mock_chat_openai.return_value = mock_instance

    from src.llm.model_wrapper import create_model
    model = create_model("researcher")

    mock_chat_openai.assert_called_once()
    call_kwargs = mock_chat_openai.call_args.kwargs
    assert call_kwargs["model"] == "deepseek-chat"
    assert call_kwargs["streaming"] is True
    assert call_kwargs["base_url"] == "https://api.deepseek.com"


@patch("src.llm.model_wrapper.ChatOpenAI")
def test_create_model_reasoner_routing(mock_chat_openai):
    mock_chat_openai.return_value = MagicMock()

    from src.llm.model_wrapper import create_model
    create_model("final_reporter")

    call_kwargs = mock_chat_openai.call_args.kwargs
    assert call_kwargs["model"] == "deepseek-reasoner"


# ---------------------------------------------------------------------------
# RAG retriever — disabled path (no Chroma connection needed)
# ---------------------------------------------------------------------------

def test_retrieve_data_rag_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_RAG", "false")
    # Re-evaluate the module-level RAG_ENABLED flag
    import src.data_retriever.output_retriever as retriever
    monkeypatch.setattr(retriever, "RAG_ENABLED", False)
    monkeypatch.setattr(retriever, "_vector_store", None)

    result = retriever.retrieve_data_with_score.func("some research brief")
    assert result["needs_research"] is True
    assert result.get("rag_disabled") is True
