"""Tests for Kalibr Intelligence client."""

import pytest
from unittest.mock import Mock, patch
import httpx

from kalibr.intelligence import (
    KalibrIntelligence,
    get_policy,
    report_outcome,
    get_recommendation,
    _get_intelligence_client,
)


class TestKalibrIntelligence:
    """Tests for KalibrIntelligence client class."""

    def test_init_defaults(self):
        """Test client initializes with defaults."""
        client = KalibrIntelligence()
        assert client.base_url == "https://kalibr-intelligence.fly.dev"
        assert client.timeout == 10.0

    def test_init_custom_values(self):
        """Test client initializes with custom values."""
        client = KalibrIntelligence(
            api_key="test-key",
            tenant_id="test-tenant",
            base_url="https://custom.url",
            timeout=30.0,
        )
        assert client.api_key == "test-key"
        assert client.tenant_id == "test-tenant"
        assert client.base_url == "https://custom.url"
        assert client.timeout == 30.0

    def test_init_from_env(self, monkeypatch):
        """Test client reads from environment variables."""
        monkeypatch.setenv("KALIBR_API_KEY", "env-key")
        monkeypatch.setenv("KALIBR_TENANT_ID", "env-tenant")
        monkeypatch.setenv("KALIBR_INTELLIGENCE_URL", "https://env.url")

        client = KalibrIntelligence()
        assert client.api_key == "env-key"
        assert client.tenant_id == "env-tenant"
        assert client.base_url == "https://env.url"

    @patch.object(httpx.Client, "request")
    def test_get_policy(self, mock_request):
        """Test get_policy makes correct API call."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "goal": "book_meeting",
            "recommended_model": "claude-3-sonnet",
            "recommended_provider": "anthropic",
            "outcome_success_rate": 0.73,
            "outcome_sample_count": 150,
            "confidence": 0.82,
            "risk_score": 0.15,
            "reasoning": "outcome score | high confidence",
            "alternatives": [],
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="test", tenant_id="test")
        result = client.get_policy(goal="book_meeting")

        assert result["recommended_model"] == "claude-3-sonnet"
        assert result["outcome_success_rate"] == 0.73

        # Verify request was made correctly
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/api/v1/intelligence/policy" in call_args[0][1]

    @patch.object(httpx.Client, "request")
    def test_report_outcome_success(self, mock_request):
        """Test report_outcome for success case."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "accepted",
            "trace_id": "trace-123",
            "goal": "book_meeting",
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="test", tenant_id="test")
        result = client.report_outcome(
            trace_id="trace-123",
            goal="book_meeting",
            success=True,
        )

        assert result["status"] == "accepted"

        # Verify request body
        call_args = mock_request.call_args
        request_body = call_args[1]["json"]
        assert request_body["trace_id"] == "trace-123"
        assert request_body["goal"] == "book_meeting"
        assert request_body["success"] is True

    @patch.object(httpx.Client, "request")
    def test_report_outcome_failure_with_reason(self, mock_request):
        """Test report_outcome for failure case with reason."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "accepted",
            "trace_id": "trace-456",
            "goal": "book_meeting",
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = KalibrIntelligence(api_key="test", tenant_id="test")
        result = client.report_outcome(
            trace_id="trace-456",
            goal="book_meeting",
            success=False,
            failure_reason="calendar_conflict",
            score=0.3,
        )

        assert result["status"] == "accepted"

        # Verify request body includes failure details
        call_args = mock_request.call_args
        request_body = call_args[1]["json"]
        assert request_body["success"] is False
        assert request_body["failure_reason"] == "calendar_conflict"
        assert request_body["score"] == 0.3

    def test_context_manager(self):
        """Test client works as context manager."""
        with KalibrIntelligence() as client:
            assert client is not None
        # Client should be closed after context


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @patch("kalibr.intelligence._get_intelligence_client")
    def test_get_policy_convenience(self, mock_get_client):
        """Test get_policy convenience function."""
        mock_client = Mock()
        mock_client.get_policy.return_value = {"recommended_model": "gpt-4"}
        mock_get_client.return_value = mock_client

        result = get_policy(goal="test_goal", task_type="code")

        mock_client.get_policy.assert_called_once_with("test_goal", task_type="code")
        assert result["recommended_model"] == "gpt-4"

    @patch("kalibr.intelligence._get_intelligence_client")
    def test_report_outcome_convenience(self, mock_get_client):
        """Test report_outcome convenience function."""
        mock_client = Mock()
        mock_client.report_outcome.return_value = {"status": "accepted"}
        mock_get_client.return_value = mock_client

        result = report_outcome(
            trace_id="trace-123",
            goal="test_goal",
            success=True,
        )

        mock_client.report_outcome.assert_called_once_with(
            "trace-123", "test_goal", True
        )
        assert result["status"] == "accepted"
