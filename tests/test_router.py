"""Tests for Router class."""

import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from kalibr.router import Router


def _make_response(content="Hello world", finish_reason="stop"):
    """Helper to create a mock OpenAI-format response."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ]
    )


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


class TestDefaultScore:
    def test_empty_response_returns_zero(self):
        router = Router(goal="test", auto_register=False)
        response = _make_response(content="")
        assert router._default_score(response) == 0.0

    def test_none_content_returns_zero(self):
        router = Router(goal="test", auto_register=False)
        response = _make_response(content=None)
        assert router._default_score(response) == 0.0

    def test_whitespace_only_returns_zero(self):
        router = Router(goal="test", auto_register=False)
        response = _make_response(content="   \n  ")
        assert router._default_score(response) == 0.0

    def test_normal_text_above_half(self):
        router = Router(goal="test", auto_register=False)
        response = _make_response(content="This is a normal response with enough text to be useful." * 5)
        score = router._default_score(response)
        assert score > 0.5

    def test_valid_json_scores_high(self):
        router = Router(goal="test", auto_register=False)
        response = _make_response(content='{"name": "Alice", "email": "alice@example.com", "age": 30}')
        score = router._default_score(response)
        # Valid JSON should get structure_score=1.0
        assert score > 0.5

    def test_invalid_json_scores_lower(self):
        router = Router(goal="test", auto_register=False)
        valid_response = _make_response(content='{"name": "Alice", "email": "alice@example.com"}')
        invalid_response = _make_response(content='{name: Alice, email: broken}')
        valid_score = router._default_score(valid_response)
        invalid_score = router._default_score(invalid_response)
        assert valid_score > invalid_score

    def test_markdown_gets_structure_bonus(self):
        router = Router(goal="test", auto_register=False)
        plain = _make_response(content="Just some plain text response here.")
        markdown = _make_response(content="## Header\n- Item 1\n- Item 2\n- Item 3")
        plain_score = router._default_score(plain)
        md_score = router._default_score(markdown)
        assert md_score > plain_score

    def test_truncated_response_scores_lower(self):
        router = Router(goal="test", auto_register=False)
        text = "A decent response." * 20
        stopped = _make_response(content=text, finish_reason="stop")
        truncated = _make_response(content=text, finish_reason="length")
        assert router._default_score(stopped) > router._default_score(truncated)

    def test_score_between_zero_and_one(self):
        router = Router(goal="test", auto_register=False)
        for content in ["x", "hello world", "a" * 5000, '{"key": "value"}']:
            score = router._default_score(_make_response(content=content))
            assert 0.0 <= score <= 1.0

    def test_malformed_response_returns_zero(self):
        router = Router(goal="test", auto_register=False)
        # Response with no choices attribute
        assert router._default_score(SimpleNamespace()) == 0.0
        # Response with empty choices
        assert router._default_score(SimpleNamespace(choices=[])) == 0.0


class TestScoreWhen:
    def test_score_when_stored(self):
        scorer = lambda out: 0.8
        router = Router(goal="test", score_when=scorer, auto_register=False)
        assert router.score_when is scorer

    @patch("kalibr.router.Router._dispatch")
    @patch("kalibr.router.Router.report")
    @patch("kalibr.intelligence.decide")
    def test_score_when_called_with_output(self, mock_decide, mock_report, mock_dispatch):
        mock_decide.return_value = {"model_id": "gpt-4o", "trace_id": "abc123"}
        mock_dispatch.return_value = _make_response(content="test output")

        router = Router(goal="test", score_when=lambda out: 0.75, auto_register=False)
        router.completion(messages=[{"role": "user", "content": "hi"}])

        mock_report.assert_called_once_with(success=True, score=0.75)

    @patch("kalibr.router.Router._dispatch")
    @patch("kalibr.router.Router.report")
    @patch("kalibr.intelligence.decide")
    def test_score_when_clamps_values(self, mock_decide, mock_report, mock_dispatch):
        mock_decide.return_value = {"model_id": "gpt-4o", "trace_id": "abc123"}
        mock_dispatch.return_value = _make_response(content="test")

        # score_when returns value > 1.0, should be clamped
        router = Router(goal="test", score_when=lambda out: 1.5, auto_register=False)
        router.completion(messages=[{"role": "user", "content": "hi"}])

        mock_report.assert_called_once_with(success=True, score=1.0)

    @patch("kalibr.router.Router._dispatch")
    @patch("kalibr.router.Router.report")
    @patch("kalibr.intelligence.decide")
    def test_score_when_low_score_reports_failure(self, mock_decide, mock_report, mock_dispatch):
        mock_decide.return_value = {"model_id": "gpt-4o", "trace_id": "abc123"}
        mock_dispatch.return_value = _make_response(content="test")

        router = Router(goal="test", score_when=lambda out: 0.2, auto_register=False)
        router.completion(messages=[{"role": "user", "content": "hi"}])

        mock_report.assert_called_once_with(success=False, score=0.2)

    @patch("kalibr.router.Router._dispatch")
    @patch("kalibr.router.Router.report")
    @patch("kalibr.intelligence.decide")
    def test_score_when_takes_priority_over_success_when(self, mock_decide, mock_report, mock_dispatch):
        mock_decide.return_value = {"model_id": "gpt-4o", "trace_id": "abc123"}
        mock_dispatch.return_value = _make_response(content="test output")

        # Both provided - score_when should win
        router = Router(
            goal="test",
            score_when=lambda out: 0.9,
            success_when=lambda out: False,  # Would report failure if used
            auto_register=False,
        )
        router.completion(messages=[{"role": "user", "content": "hi"}])

        # score_when used (score=0.9 -> success=True), not success_when (which would give False)
        mock_report.assert_called_once_with(success=True, score=0.9)


class TestDefaultScoringIntegration:
    @patch("kalibr.router.Router._dispatch")
    @patch("kalibr.router.Router.report")
    @patch("kalibr.intelligence.decide")
    def test_default_scoring_fires_when_no_scorers(self, mock_decide, mock_report, mock_dispatch):
        mock_decide.return_value = {"model_id": "gpt-4o", "trace_id": "abc123"}
        mock_dispatch.return_value = _make_response(content="A good response with enough content." * 5)

        # No score_when, no success_when
        router = Router(goal="test", auto_register=False)
        router.completion(messages=[{"role": "user", "content": "hi"}])

        # report() should have been called with a heuristic score
        mock_report.assert_called_once()
        call_kwargs = mock_report.call_args
        assert "score" in call_kwargs.kwargs or (len(call_kwargs.args) > 1 if call_kwargs.args else False)

    @patch("kalibr.router.Router._dispatch")
    @patch("kalibr.router.Router.report")
    @patch("kalibr.intelligence.decide")
    def test_success_when_takes_priority_over_default(self, mock_decide, mock_report, mock_dispatch):
        mock_decide.return_value = {"model_id": "gpt-4o", "trace_id": "abc123"}
        mock_dispatch.return_value = _make_response(content="no-email-here")

        # success_when provided - should use it, not default scoring
        router = Router(
            goal="test",
            success_when=lambda out: "@" in out,
            auto_register=False,
        )
        router.completion(messages=[{"role": "user", "content": "hi"}])

        # success_when should report success=False (no @ in output), no score kwarg
        mock_report.assert_called_once_with(success=False)
