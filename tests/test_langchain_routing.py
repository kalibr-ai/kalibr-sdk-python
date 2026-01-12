"""Tests for LangChain routing integration."""

import pytest
from unittest.mock import MagicMock, patch

from kalibr.router import Router


class TestKalibrChatModel:
    @patch("kalibr.router.Router._call_openai")
    def test_basic_generation(self, mock_openai):
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4o"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_openai.return_value = mock_response

        router = Router(goal="test", paths=["gpt-4o"], auto_register=False)
        llm = router.as_langchain()

        from langchain_core.messages import HumanMessage
        result = llm.invoke([HumanMessage(content="Hi")])

        assert result.content == "Hello!"

    def test_llm_type(self):
        router = Router(goal="test", paths=["gpt-4o"], auto_register=False)
        llm = router.as_langchain()
        assert llm._llm_type == "kalibr"

    def test_identifying_params(self):
        router = Router(goal="summarize", paths=["gpt-4o"], auto_register=False)
        llm = router.as_langchain()
        assert llm._identifying_params == {"goal": "summarize"}

    @patch("kalibr.router.Router._call_openai")
    def test_message_conversion(self, mock_openai):
        """Test that LangChain messages are converted to OpenAI format."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4o"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_openai.return_value = mock_response

        router = Router(goal="test", paths=["gpt-4o"], auto_register=False)
        llm = router.as_langchain()

        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        messages = [
            SystemMessage(content="You are a helper"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there"),
            HumanMessage(content="How are you?"),
        ]

        llm.invoke(messages)

        # Verify the call was made with converted messages
        # Messages are passed as second positional arg to _call_openai(model, messages, tools, **kwargs)
        call_args = mock_openai.call_args
        converted_messages = call_args[0][1]

        assert converted_messages[0] == {"role": "system", "content": "You are a helper"}
        assert converted_messages[1] == {"role": "user", "content": "Hello"}
        assert converted_messages[2] == {"role": "assistant", "content": "Hi there"}
        assert converted_messages[3] == {"role": "user", "content": "How are you?"}

    @patch("kalibr.router.Router._call_openai")
    def test_stop_sequences(self, mock_openai):
        """Test that stop sequences are passed through."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4o"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_openai.return_value = mock_response

        router = Router(goal="test", paths=["gpt-4o"], auto_register=False)
        llm = router.as_langchain()

        from langchain_core.messages import HumanMessage

        llm.invoke([HumanMessage(content="Hi")], stop=["END"])

        call_args = mock_openai.call_args
        assert call_args[1].get("stop") == ["END"]

    @patch("kalibr.router.Router._call_openai")
    def test_chat_result_format(self, mock_openai):
        """Test that the ChatResult is properly formatted."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated text"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4o"
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 10
        mock_response.usage.total_tokens = 30
        mock_openai.return_value = mock_response

        router = Router(goal="test", paths=["gpt-4o"], auto_register=False)
        llm = router.as_langchain()

        from langchain_core.messages import HumanMessage, AIMessage

        result = llm.invoke([HumanMessage(content="Hi")])

        assert result.content == "Generated text"
        assert isinstance(result, AIMessage)
