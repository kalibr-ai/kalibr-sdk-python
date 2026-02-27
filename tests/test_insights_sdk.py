"""Tests for failure categories, outcome enrichment, and insights API."""

import pytest
from unittest.mock import Mock, patch
import httpx

from kalibr.intelligence import (
    KalibrIntelligence,
    FAILURE_CATEGORIES,
    report_outcome,
    update_outcome,
    get_insights,
)


class TestFailureCategories:
    """Tests for the FAILURE_CATEGORIES constant."""

    def test_has_all_expected_categories(self):
        """FAILURE_CATEGORIES contains all 12 expected values."""
        expected = [
            "timeout", "context_exceeded", "tool_error", "rate_limited",
            "validation_failed", "hallucination_detected", "user_unsatisfied",
            "empty_response", "malformed_output", "auth_error", "provider_error", "unknown",
        ]
        assert FAILURE_CATEGORIES == expected
        assert len(FAILURE_CATEGORIES) == 12

    def test_importable_from_kalibr(self):
        """FAILURE_CATEGORIES is importable from the top-level kalibr package."""
        from kalibr import FAILURE_CATEGORIES as fc
        assert fc is FAILURE_CATEGORIES


class TestReportOutcomeFailureCategory:
    """Tests for failure_category on report_outcome."""

    @patch.object(httpx.Client, "request")
    def test_includes_failure_category_in_body(self, mock_request):
        """report_outcome includes failure_category in request body when provided."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "accepted", "trace_id": "t1", "goal": "g1"}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="k", tenant_id="t")
        client.report_outcome(
            trace_id="t1", goal="g1", success=False,
            failure_category="timeout",
        )

        body = mock_request.call_args[1]["json"]
        assert body["failure_category"] == "timeout"

    def test_invalid_failure_category_raises(self):
        """report_outcome with invalid failure_category raises ValueError client-side."""
        client = KalibrIntelligence(api_key="k", tenant_id="t")
        with pytest.raises(ValueError, match="Invalid failure_category 'not_real'"):
            client.report_outcome(
                trace_id="t1", goal="g1", success=False,
                failure_category="not_real",
            )

    @patch.object(httpx.Client, "request")
    def test_without_failure_category_backwards_compatible(self, mock_request):
        """report_outcome without failure_category still works (backwards compatible)."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "accepted", "trace_id": "t1", "goal": "g1"}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="k", tenant_id="t")
        result = client.report_outcome(trace_id="t1", goal="g1", success=True)

        assert result["status"] == "accepted"
        body = mock_request.call_args[1]["json"]
        assert body["failure_category"] is None


class TestUpdateOutcome:
    """Tests for the update_outcome method."""

    @patch.object(httpx.Client, "request")
    def test_makes_post_to_correct_endpoint(self, mock_request):
        """update_outcome makes POST to /api/v1/intelligence/update-outcome."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "updated", "trace_id": "t1", "goal": "g1",
            "fields_updated": ["success", "failure_reason"],
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="k", tenant_id="t")
        result = client.update_outcome(
            trace_id="t1", goal="g1", success=False,
            failure_reason="customer_reopened",
        )

        assert result["status"] == "updated"
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/api/v1/intelligence/update-outcome" in call_args[0][1]

        body = call_args[1]["json"]
        assert body["trace_id"] == "t1"
        assert body["goal"] == "g1"
        assert body["success"] is False
        assert body["failure_reason"] == "customer_reopened"

    @patch.object(httpx.Client, "request")
    def test_correct_body_all_fields(self, mock_request):
        """update_outcome sends all fields in request body."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "updated"}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="k", tenant_id="t")
        client.update_outcome(
            trace_id="t1", goal="g1", success=True, score=0.9,
            failure_reason=None, failure_category="timeout",
            metadata={"key": "val"},
        )

        body = mock_request.call_args[1]["json"]
        assert body == {
            "trace_id": "t1",
            "goal": "g1",
            "success": True,
            "score": 0.9,
            "failure_reason": None,
            "failure_category": "timeout",
            "metadata": {"key": "val"},
        }

    def test_invalid_failure_category_raises(self):
        """update_outcome with invalid failure_category raises ValueError."""
        client = KalibrIntelligence(api_key="k", tenant_id="t")
        with pytest.raises(ValueError, match="Invalid failure_category 'bad_cat'"):
            client.update_outcome(
                trace_id="t1", goal="g1", failure_category="bad_cat",
            )


class TestGetInsights:
    """Tests for the get_insights method."""

    @patch.object(httpx.Client, "request")
    def test_makes_get_to_correct_endpoint(self, mock_request):
        """get_insights makes GET to /api/v1/intelligence/insights."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "schema_version": "1.0",
            "goals": [],
            "cross_goal_summary": {},
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="k", tenant_id="t")
        result = client.get_insights()

        assert result["schema_version"] == "1.0"
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/v1/intelligence/insights" in call_args[0][1]

    @patch.object(httpx.Client, "request")
    def test_with_goal_filter(self, mock_request):
        """get_insights with goal filter passes goal as query param."""
        mock_response = Mock()
        mock_response.json.return_value = {"goals": []}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="k", tenant_id="t")
        client.get_insights(goal="book_meeting")

        params = mock_request.call_args[1]["params"]
        assert params["goal"] == "book_meeting"
        assert params["window_hours"] == 168

    @patch.object(httpx.Client, "request")
    def test_without_goal_omits_goal_param(self, mock_request):
        """get_insights without goal omits goal param."""
        mock_response = Mock()
        mock_response.json.return_value = {"goals": []}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="k", tenant_id="t")
        client.get_insights()

        params = mock_request.call_args[1]["params"]
        assert "goal" not in params
        assert params["window_hours"] == 168

    @patch.object(httpx.Client, "request")
    def test_custom_window_hours(self, mock_request):
        """get_insights passes custom window_hours."""
        mock_response = Mock()
        mock_response.json.return_value = {"goals": []}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="k", tenant_id="t")
        client.get_insights(window_hours=24)

        params = mock_request.call_args[1]["params"]
        assert params["window_hours"] == 24


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @patch("kalibr.intelligence._get_intelligence_client")
    def test_update_outcome_callable(self, mock_get_client):
        """Module-level update_outcome is callable."""
        mock_client = Mock()
        mock_client.update_outcome.return_value = {"status": "updated"}
        mock_get_client.return_value = mock_client

        result = update_outcome(trace_id="t1", goal="g1", success=False)

        mock_client.update_outcome.assert_called_once_with("t1", "g1", success=False)
        assert result["status"] == "updated"

    @patch("kalibr.intelligence._get_intelligence_client")
    def test_get_insights_callable(self, mock_get_client):
        """Module-level get_insights is callable."""
        mock_client = Mock()
        mock_client.get_insights.return_value = {"goals": []}
        mock_get_client.return_value = mock_client

        result = get_insights(goal="book_meeting")

        mock_client.get_insights.assert_called_once_with(goal="book_meeting")
        assert result["goals"] == []

    @patch("kalibr.intelligence._get_intelligence_client")
    def test_report_outcome_passes_failure_category(self, mock_get_client):
        """Module-level report_outcome passes failure_category through."""
        mock_client = Mock()
        mock_client.report_outcome.return_value = {"status": "accepted"}
        mock_get_client.return_value = mock_client

        report_outcome(
            trace_id="t1", goal="g1", success=False,
            failure_category="timeout",
        )

        mock_client.report_outcome.assert_called_once_with(
            "t1", "g1", False, failure_category="timeout",
        )

    def test_importable_from_kalibr_package(self):
        """update_outcome and get_insights importable from kalibr package."""
        from kalibr import update_outcome as uo, get_insights as gi
        assert callable(uo)
        assert callable(gi)


class TestRouterFailureCategory:
    """Tests for Router.report with failure_category."""

    def test_report_accepts_failure_category(self, monkeypatch):
        """Router.report accepts failure_category parameter."""
        monkeypatch.setenv("KALIBR_API_KEY", "test-key")
        monkeypatch.setenv("KALIBR_TENANT_ID", "test-tenant")
        from kalibr.router import Router

        router = Router(goal="test", paths=["gpt-4o"], auto_register=False)
        # Set up internal state as if completion() was called
        router._last_trace_id = "trace-123"
        router._last_model_id = "gpt-4o"
        router._outcome_reported = False

        with patch("kalibr.intelligence.report_outcome") as mock_report:
            mock_report.return_value = {"status": "accepted"}
            router.report(success=False, failure_category="timeout", reason="timed out")

        mock_report.assert_called_once_with(
            trace_id="trace-123",
            goal="test",
            success=False,
            score=None,
            failure_reason="timed out",
            failure_category="timeout",
            model_id="gpt-4o",
        )

    def test_report_invalid_failure_category_raises(self, monkeypatch):
        """Router.report with invalid failure_category raises ValueError."""
        monkeypatch.setenv("KALIBR_API_KEY", "test-key")
        monkeypatch.setenv("KALIBR_TENANT_ID", "test-tenant")
        from kalibr.router import Router

        router = Router(goal="test", paths=["gpt-4o"], auto_register=False)
        router._last_trace_id = "trace-123"
        router._outcome_reported = False

        with pytest.raises(ValueError, match="Invalid failure_category 'nope'"):
            router.report(success=False, failure_category="nope")
