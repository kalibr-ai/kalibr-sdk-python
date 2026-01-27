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
