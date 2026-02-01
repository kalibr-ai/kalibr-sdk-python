"""Tests for Router class."""

import pytest
from unittest.mock import patch, MagicMock

from kalibr.router import Router


class TestRouterInit:
    def test_basic_init(self):
        router = Router(goal="test", paths=["gpt-4o"], auto_register=False)
        assert router.goal == "test"
        assert len(router._paths) == 1
        assert router._paths[0]["model"] == "gpt-4o"

    def test_normalize_string_paths(self):
        router = Router(goal="test", paths=["gpt-4o", "claude-3"], auto_register=False)
        assert router._paths[0] == {"model": "gpt-4o", "tools": None, "params": None}
        assert router._paths[1] == {"model": "claude-3", "tools": None, "params": None}

    def test_normalize_dict_paths(self):
        router = Router(
            goal="test",
            paths=[{"model": "gpt-4o", "tools": ["search"]}],
            auto_register=False
        )
        assert router._paths[0]["model"] == "gpt-4o"
        assert router._paths[0]["tools"] == ["search"]


class TestRouterDispatch:
    def test_openai_model_detection(self):
        router = Router(goal="test", auto_register=False)
        assert router._dispatch.__name__  # Just check method exists

    @patch("kalibr.router.Router._call_openai")
    def test_routes_to_openai(self, mock_openai):
        mock_openai.return_value = MagicMock()
        router = Router(goal="test", auto_register=False)
        router._dispatch("gpt-4o", [{"role": "user", "content": "test"}], None)
        mock_openai.assert_called_once()

    @patch("kalibr.router.Router._call_anthropic")
    def test_routes_to_anthropic(self, mock_anthropic):
        mock_anthropic.return_value = MagicMock()
        router = Router(goal="test", auto_register=False)
        router._dispatch("claude-3-sonnet", [{"role": "user", "content": "test"}], None)
        mock_anthropic.assert_called_once()


class TestRouterReport:
    def test_double_report_warning(self):
        router = Router(goal="test", auto_register=False)
        router._outcome_reported = True
        # Should not raise, just warn
        router.report(success=True)


class TestRouterFallback:
    """Tests for provider fallback behavior."""

    @patch("kalibr.router.Router._call_anthropic")
    @patch("kalibr.router.Router._call_openai")
    @patch("kalibr.intelligence.decide")
    @patch("kalibr.intelligence.report_outcome")
    def test_fallback_on_provider_failure(
        self, mock_report, mock_decide, mock_openai, mock_anthropic
    ):
        """When first provider fails, router should try the next path."""
        # Setup: decide returns gpt-4o, but OpenAI fails
        mock_decide.return_value = {"model_id": "gpt-4o", "trace_id": "test-trace"}
        mock_openai.side_effect = Exception("OpenAI API key invalid")

        # Anthropic succeeds
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "success"
        mock_anthropic.return_value = mock_response

        router = Router(
            goal="test",
            paths=["gpt-4o", "claude-3-sonnet"],
            auto_register=False
        )
        response = router.completion(messages=[{"role": "user", "content": "test"}])

        # Verify OpenAI was tried first, then Anthropic
        mock_openai.assert_called_once()
        mock_anthropic.assert_called_once()

        # Verify the successful model is tracked
        assert router._last_model_id == "claude-3-sonnet"
        assert response.kalibr_trace_id == "test-trace"

    @patch("kalibr.router.Router._call_anthropic")
    @patch("kalibr.router.Router._call_openai")
    @patch("kalibr.intelligence.decide")
    @patch("kalibr.intelligence.report_outcome")
    def test_raises_when_all_providers_fail(
        self, mock_report, mock_decide, mock_openai, mock_anthropic
    ):
        """When all providers fail, router should raise the last exception."""
        mock_decide.return_value = {"model_id": "gpt-4o", "trace_id": "test-trace"}
        mock_openai.side_effect = Exception("OpenAI failed")
        mock_anthropic.side_effect = Exception("Anthropic failed")

        router = Router(
            goal="test",
            paths=["gpt-4o", "claude-3-sonnet"],
            auto_register=False
        )

        with pytest.raises(Exception) as exc_info:
            router.completion(messages=[{"role": "user", "content": "test"}])

        # Should raise the last exception (Anthropic's)
        assert "Anthropic failed" in str(exc_info.value)

    @patch("kalibr.router.Router._call_openai")
    @patch("kalibr.intelligence.decide")
    @patch("kalibr.intelligence.report_outcome")
    def test_no_fallback_when_first_succeeds(
        self, mock_report, mock_decide, mock_openai
    ):
        """When first provider succeeds, no fallback should be attempted."""
        mock_decide.return_value = {"model_id": "gpt-4o", "trace_id": "test-trace"}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "success"
        mock_openai.return_value = mock_response

        router = Router(
            goal="test",
            paths=["gpt-4o", "claude-3-sonnet"],
            auto_register=False
        )
        response = router.completion(messages=[{"role": "user", "content": "test"}])

        # Only OpenAI should be called
        mock_openai.assert_called_once()
        assert router._last_model_id == "gpt-4o"

    @patch("kalibr.router.Router._call_anthropic")
    @patch("kalibr.router.Router._call_openai")
    @patch("kalibr.intelligence.decide")
    @patch("kalibr.intelligence.report_outcome")
    def test_fallback_skips_duplicate_models(
        self, mock_report, mock_decide, mock_openai, mock_anthropic
    ):
        """Fallback should skip duplicate models in the path list."""
        # Decision returns gpt-4o, paths also has gpt-4o first
        mock_decide.return_value = {"model_id": "gpt-4o", "trace_id": "test-trace"}
        mock_openai.side_effect = Exception("OpenAI failed")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "success"
        mock_anthropic.return_value = mock_response

        router = Router(
            goal="test",
            paths=["gpt-4o", "claude-3-sonnet"],
            auto_register=False
        )
        response = router.completion(messages=[{"role": "user", "content": "test"}])

        # OpenAI should only be called once (not twice for duplicate gpt-4o)
        assert mock_openai.call_count == 1
        mock_anthropic.assert_called_once()
