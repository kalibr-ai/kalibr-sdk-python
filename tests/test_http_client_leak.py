"""Tests for HTTP client resource management and memory leak prevention.

Verifies that convenience functions properly close HTTP clients to prevent
connection leaks in long-running applications.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestHTTPClientResourceManagement:
    """Test that HTTP clients are properly closed"""

    @patch('kalibr.intelligence.KalibrIntelligence')
    def test_get_policy_with_tenant_id_closes_client(self, mock_client_class):
        """Test that get_policy() closes client when using custom tenant_id"""
        from kalibr import intelligence

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.get_policy = Mock(return_value={"recommended_model": "gpt-4o"})
        mock_client_class.return_value = mock_instance

        # Call function with tenant_id
        result = intelligence.get_policy(goal="test", tenant_id="tenant-123")

        # Verify client was created with tenant_id
        mock_client_class.assert_called_once_with(tenant_id="tenant-123")

        # Verify context manager was used (client was entered and exited)
        mock_instance.__enter__.assert_called_once()
        mock_instance.__exit__.assert_called_once()

        # Verify get_policy was called
        mock_instance.get_policy.assert_called_once_with("test")

        # Verify result
        assert result == {"recommended_model": "gpt-4o"}

    @patch('kalibr.intelligence.KalibrIntelligence')
    def test_report_outcome_with_tenant_id_closes_client(self, mock_client_class):
        """Test that report_outcome() closes client when using custom tenant_id"""
        from kalibr import intelligence

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.report_outcome = Mock(return_value={"status": "recorded"})
        mock_client_class.return_value = mock_instance

        # Call function with tenant_id
        result = intelligence.report_outcome(
            trace_id="trace-123",
            goal="test",
            success=True,
            tenant_id="tenant-456"
        )

        # Verify client was created with tenant_id
        mock_client_class.assert_called_once_with(tenant_id="tenant-456")

        # Verify context manager was used
        mock_instance.__enter__.assert_called_once()
        mock_instance.__exit__.assert_called_once()

        # Verify report_outcome was called
        mock_instance.report_outcome.assert_called_once_with("trace-123", "test", True)

        # Verify result
        assert result == {"status": "recorded"}

    @patch('kalibr.intelligence.KalibrIntelligence')
    def test_register_path_with_tenant_id_closes_client(self, mock_client_class):
        """Test that register_path() closes client when using custom tenant_id"""
        from kalibr import intelligence

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.register_path = Mock(return_value={"path_id": "path-789"})
        mock_client_class.return_value = mock_instance

        # Call function with tenant_id
        result = intelligence.register_path(
            goal="test",
            model_id="gpt-4",
            tenant_id="tenant-789"
        )

        # Verify client was created with tenant_id
        mock_client_class.assert_called_once_with(tenant_id="tenant-789")

        # Verify context manager was used
        mock_instance.__enter__.assert_called_once()
        mock_instance.__exit__.assert_called_once()

        # Verify register_path was called
        mock_instance.register_path.assert_called_once_with("test", "gpt-4", None, None, "low")

        # Verify result
        assert result == {"path_id": "path-789"}

    @patch('kalibr.intelligence.KalibrIntelligence')
    def test_decide_with_tenant_id_closes_client(self, mock_client_class):
        """Test that decide() closes client when using custom tenant_id"""
        from kalibr import intelligence

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.decide = Mock(return_value={"model_id": "gpt-4o"})
        mock_client_class.return_value = mock_instance

        # Call function with tenant_id
        result = intelligence.decide(
            goal="test",
            tenant_id="tenant-999"
        )

        # Verify client was created with tenant_id
        mock_client_class.assert_called_once_with(tenant_id="tenant-999")

        # Verify context manager was used
        mock_instance.__enter__.assert_called_once()
        mock_instance.__exit__.assert_called_once()

        # Verify decide was called
        mock_instance.decide.assert_called_once_with("test", "low")

        # Verify result
        assert result == {"model_id": "gpt-4o"}

    @patch('kalibr.intelligence._get_intelligence_client')
    def test_get_policy_without_tenant_id_uses_singleton(self, mock_get_client):
        """Test that get_policy() uses singleton client when no tenant_id"""
        from kalibr import intelligence

        # Setup mock
        mock_client = Mock()
        mock_client.get_policy = Mock(return_value={"recommended_model": "gpt-4o"})
        mock_get_client.return_value = mock_client

        # Call function without tenant_id
        result = intelligence.get_policy(goal="test")

        # Verify singleton was used
        mock_get_client.assert_called_once()
        mock_client.get_policy.assert_called_once_with("test")

        # Verify result
        assert result == {"recommended_model": "gpt-4o"}

    @patch('kalibr.intelligence._get_intelligence_client')
    def test_report_outcome_without_tenant_id_uses_singleton(self, mock_get_client):
        """Test that report_outcome() uses singleton client when no tenant_id"""
        from kalibr import intelligence

        # Setup mock
        mock_client = Mock()
        mock_client.report_outcome = Mock(return_value={"status": "recorded"})
        mock_get_client.return_value = mock_client

        # Call function without tenant_id
        result = intelligence.report_outcome(trace_id="trace-123", goal="test", success=True)

        # Verify singleton was used
        mock_get_client.assert_called_once()
        mock_client.report_outcome.assert_called_once_with("trace-123", "test", True)

        # Verify result
        assert result == {"status": "recorded"}

    @patch('kalibr.intelligence.KalibrIntelligence')
    def test_multiple_calls_with_different_tenants_each_closed(self, mock_client_class):
        """Test that multiple calls with different tenant_ids each create and close clients"""
        from kalibr import intelligence

        # Setup mock to return different instances
        instances = []
        for i in range(5):
            mock_instance = MagicMock()
            mock_instance.__enter__ = Mock(return_value=mock_instance)
            mock_instance.__exit__ = Mock(return_value=False)
            mock_instance.get_policy = Mock(return_value={"model": f"model-{i}"})
            instances.append(mock_instance)

        mock_client_class.side_effect = instances

        # Make 5 calls with different tenant_ids
        for i in range(5):
            result = intelligence.get_policy(goal="test", tenant_id=f"tenant-{i}")
            assert result == {"model": f"model-{i}"}

        # Verify 5 clients were created
        assert mock_client_class.call_count == 5

        # Verify each client was entered and exited (closed)
        for instance in instances:
            instance.__enter__.assert_called_once()
            instance.__exit__.assert_called_once()

    @patch('kalibr.intelligence.KalibrIntelligence')
    def test_context_manager_closes_on_exception(self, mock_client_class):
        """Test that client is closed even when exception occurs"""
        from kalibr import intelligence

        # Setup mock to raise exception
        mock_instance = MagicMock()
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.get_policy = Mock(side_effect=Exception("API Error"))
        mock_client_class.return_value = mock_instance

        # Call function and expect exception
        with pytest.raises(Exception, match="API Error"):
            intelligence.get_policy(goal="test", tenant_id="tenant-error")

        # Verify context manager was still properly used (client closed)
        mock_instance.__enter__.assert_called_once()
        mock_instance.__exit__.assert_called_once()


class TestMemoryLeakPrevention:
    """Test scenarios from issue #38"""

    @patch('kalibr.intelligence.KalibrIntelligence')
    def test_no_leak_with_many_tenant_calls(self, mock_client_class):
        """Test that making many calls with different tenant_ids doesn't leak connections"""
        from kalibr import intelligence

        # Setup mock
        instances_created = []

        def create_instance(tenant_id=None):
            mock_instance = MagicMock()
            mock_instance.__enter__ = Mock(return_value=mock_instance)
            mock_instance.__exit__ = Mock(return_value=False)
            mock_instance.get_policy = Mock(return_value={"model": "gpt-4o"})
            instances_created.append(mock_instance)
            return mock_instance

        mock_client_class.side_effect = create_instance

        # Simulate multi-tenant application (from issue #38)
        num_calls = 100
        for i in range(num_calls):
            intelligence.get_policy(goal="test", tenant_id=f"tenant-{i}")

        # Verify all instances were properly closed
        assert len(instances_created) == num_calls
        for instance in instances_created:
            instance.__enter__.assert_called_once()
            instance.__exit__.assert_called_once()

    @patch('kalibr.intelligence.KalibrIntelligence')
    def test_all_convenience_functions_properly_close_clients(self, mock_client_class):
        """Test that all 4 convenience functions properly close clients"""
        from kalibr import intelligence

        # Track all created instances
        instances_created = []

        def create_instance(tenant_id=None):
            mock_instance = MagicMock()
            mock_instance.__enter__ = Mock(return_value=mock_instance)
            mock_instance.__exit__ = Mock(return_value=False)
            mock_instance.get_policy = Mock(return_value={"model": "gpt-4o"})
            mock_instance.report_outcome = Mock(return_value={"status": "ok"})
            mock_instance.register_path = Mock(return_value={"path_id": "123"})
            mock_instance.decide = Mock(return_value={"model_id": "gpt-4o"})
            instances_created.append(mock_instance)
            return mock_instance

        mock_client_class.side_effect = create_instance

        # Call all 4 functions with tenant_id
        intelligence.get_policy(goal="test", tenant_id="tenant-1")
        intelligence.report_outcome(trace_id="t1", goal="test", success=True, tenant_id="tenant-2")
        intelligence.register_path(goal="test", model_id="gpt-4", tenant_id="tenant-3")
        intelligence.decide(goal="test", tenant_id="tenant-4")

        # Verify 4 instances were created
        assert len(instances_created) == 4

        # Verify all were properly closed
        for instance in instances_created:
            instance.__enter__.assert_called_once()
            instance.__exit__.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

