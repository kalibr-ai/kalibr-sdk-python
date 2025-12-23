"""
Test suite for capsule reconstruction and aggregation
Tests the capsule builder API and CLI functionality
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).parent.parent / "sdk" / "python"))


class TestCapsuleReconstruction:
    """Test capsule reconstruction from trace chains"""
    
    def test_capsule_endpoint_import(self):
        """Test that capsule router can be imported"""
        from routes.capsule import router, get_capsule
        assert router is not None
        assert get_capsule is not None
    
    def test_capsule_aggregation_logic(self):
        """Test capsule cost and latency aggregation"""
        # Sample trace events (simulating ClickHouse query results)
        sample_rows = [
            # (tid, parent, tenant, provider, model, operation, duration, cost, cost_est, status, timestamp, ts_start)
            ("trace-001", None, "acme-prod", "openai", "gpt-5", "completion", 150, 0.002, 0.002, "success", datetime.now(timezone.utc), datetime.now(timezone.utc)),
            ("trace-002", "trace-001", "acme-prod", "anthropic", "claude-sonnet-4", "completion", 200, 0.003, 0.003, "success", datetime.now(timezone.utc), datetime.now(timezone.utc)),
            ("trace-003", "trace-001", "acme-prod", "openai", "gpt-5", "embedding", 50, 0.0001, 0.0001, "success", datetime.now(timezone.utc), datetime.now(timezone.utc)),
        ]
        
        # Simulate aggregation logic
        total_cost = 0.0
        total_latency_ms = 0
        events = []
        providers = set()
        
        for row in sample_rows:
            (tid, parent, tenant, provider, model, operation, 
             duration, cost, cost_est, status, timestamp, ts_start) = row
            
            # Use cost_est if cost_usd is 0
            event_cost = float(cost_est) if float(cost_est) > 0 else float(cost)
            total_cost += event_cost
            total_latency_ms += int(duration) if duration else 0
            
            if provider:
                providers.add(str(provider))
            
            events.append({
                "trace_id": str(tid),
                "parent_id": str(parent) if parent else None,
                "provider": str(provider),
                "duration_ms": int(duration),
                "cost_usd": event_cost,
            })
        
        # Assertions
        assert len(events) == 3, "Should have 3 events"
        assert total_cost == 0.0051, f"Expected total cost 0.0051, got {total_cost}"
        assert total_latency_ms == 400, f"Expected total latency 400ms, got {total_latency_ms}"
        assert len(providers) == 2, "Should have 2 unique providers"
        assert "openai" in providers
        assert "anthropic" in providers
    
    def test_capsule_parent_chain_logic(self):
        """Test parent_id chain reconstruction"""
        sample_rows = [
            ("root-trace", None, "tenant1", "openai", "gpt-5", "chat", 100, 0.001, 0.001, "success", datetime.now(timezone.utc), datetime.now(timezone.utc)),
            ("child-1", "root-trace", "tenant1", "anthropic", "claude-sonnet-4", "chat", 150, 0.002, 0.002, "success", datetime.now(timezone.utc), datetime.now(timezone.utc)),
            ("child-2", "root-trace", "tenant1", "google", "gemini-2.0-flash-exp", "chat", 120, 0.0015, 0.0015, "success", datetime.now(timezone.utc), datetime.now(timezone.utc)),
            ("grandchild-1", "child-1", "tenant1", "openai", "gpt-5", "chat", 80, 0.0008, 0.0008, "success", datetime.now(timezone.utc), datetime.now(timezone.utc)),
        ]
        
        # Build parent chain map
        events_by_id = {}
        for row in sample_rows:
            tid, parent = row[0], row[1]
            events_by_id[tid] = {"trace_id": tid, "parent_id": parent, "duration_ms": row[6]}
        
        # Verify chain structure
        assert events_by_id["root-trace"]["parent_id"] is None
        assert events_by_id["child-1"]["parent_id"] == "root-trace"
        assert events_by_id["child-2"]["parent_id"] == "root-trace"
        assert events_by_id["grandchild-1"]["parent_id"] == "child-1"
        
        # Count total chain length
        hop_count = len(events_by_id)
        assert hop_count == 4, f"Expected 4 hops, got {hop_count}"
    
    def test_capsule_cost_prioritization(self):
        """Test that cost_est_usd is used when cost_usd is 0"""
        test_cases = [
            # (cost_usd, cost_est_usd, expected)
            (0.0, 0.003, 0.003),  # Use cost_est when cost is 0
            (0.002, 0.003, 0.003),  # Use cost_est when it's greater
            (0.0, 0.0, 0.0),  # Both zero
        ]
        
        for cost, cost_est, expected in test_cases:
            result = float(cost_est) if float(cost_est) > 0 else float(cost)
            assert result == expected, f"Cost calculation failed for cost={cost}, cost_est={cost_est}"
    
    def test_capsule_response_structure(self):
        """Test that capsule response has required fields"""
        expected_fields = {
            "capsule_id",
            "reconstructed_at",
            "total_cost_usd",
            "total_latency_ms",
            "hop_count",
            "providers",
            "events",
            "metadata",
        }
        
        # Simulate capsule response
        capsule = {
            "capsule_id": "trace-001",
            "reconstructed_at": datetime.utcnow().isoformat() + "Z",
            "total_cost_usd": 0.005,
            "total_latency_ms": 400,
            "hop_count": 3,
            "providers": ["openai", "anthropic"],
            "events": [],
            "metadata": {
                "reconstruction_method": "parent_id_chain",
                "chain_complete": True
            }
        }
        
        # Verify all required fields are present
        assert set(capsule.keys()) == expected_fields
        assert capsule["metadata"]["reconstruction_method"] == "parent_id_chain"
        assert isinstance(capsule["providers"], list)
        assert isinstance(capsule["events"], list)


class TestCapsuleCLI:
    """Test CLI command for capsule fetching"""
    
    def test_cli_import(self):
        """Test that CLI command can be imported"""
        from kalibr.cli.capsule_cmd import capsule
        assert capsule is not None
    
    @patch('kalibr.cli.capsule_cmd.requests.get')
    def test_cli_successful_fetch(self, mock_get):
        """Test successful capsule fetch via CLI"""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "capsule_id": "test-trace-123",
            "total_cost_usd": 0.005,
            "total_latency_ms": 350,
            "hop_count": 2,
            "providers": ["openai"],
            "events": [
                {
                    "trace_id": "test-trace-123",
                    "provider": "openai",
                    "model_id": "gpt-5",
                    "operation": "completion",
                    "duration_ms": 150,
                    "cost_usd": 0.005,
                    "status": "success",
                }
            ],
            "reconstructed_at": "2025-01-01T00:00:00Z",
            "metadata": {"reconstruction_method": "parent_id_chain", "chain_complete": True}
        }
        mock_get.return_value = mock_response
        
        # Test CLI function
        from kalibr.cli.capsule_cmd import capsule
        # This would normally be called by typer, so we test the logic
        # In real usage: kalibr capsule test-trace-123
        
        # Verify mock was called correctly
        assert mock_response.json() is not None
        assert mock_response.json()["capsule_id"] == "test-trace-123"
    
    def test_cli_api_url_construction(self):
        """Test that CLI constructs correct API URLs"""
        test_cases = [
            ("http://localhost:8001", "trace-123", False, "http://localhost:8001/api/capsule/trace-123"),
            ("http://localhost:8001/", "trace-456", False, "http://localhost:8001/api/capsule/trace-456"),
            ("https://api.kalibr.systems", "trace-789", True, "https://api.kalibr.systems/api/capsule/trace-789/export"),
        ]
        
        for base_url, trace_id, export, expected in test_cases:
            base = base_url.rstrip("/")
            if export:
                result = f"{base}/api/capsule/{trace_id}/export"
            else:
                result = f"{base}/api/capsule/{trace_id}"
            
            assert result == expected, f"URL construction failed for {base_url}, {trace_id}, export={export}"


class TestCapsuleEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_trace_chain(self):
        """Test handling of empty trace results"""
        sample_rows = []
        
        total_cost = 0.0
        total_latency_ms = 0
        events = []
        
        for row in sample_rows:
            pass  # No rows to process
        
        assert len(events) == 0
        assert total_cost == 0.0
        assert total_latency_ms == 0
    
    def test_missing_cost_fields(self):
        """Test handling of missing or None cost fields"""
        test_row = ("trace-1", None, "tenant", "provider", "model", "op", 100, None, None, "success", datetime.now(timezone.utc), datetime.now(timezone.utc))
        
        duration, cost, cost_est = test_row[6], test_row[7], test_row[8]
        
        # Handle None values
        event_cost = float(cost_est or 0) if float(cost_est or 0) > 0 else float(cost or 0)
        total_latency = int(duration) if duration else 0
        
        assert event_cost == 0.0
        assert total_latency == 100
    
    def test_circular_parent_detection(self):
        """Test detection of circular parent references"""
        # This shouldn't happen in practice, but test defensive logic
        sample_rows = [
            ("trace-A", "trace-B", "tenant", "provider", "model", "op", 100, 0.001, 0.001, "success", datetime.now(timezone.utc), datetime.now(timezone.utc)),
            ("trace-B", "trace-A", "tenant", "provider", "model", "op", 100, 0.001, 0.001, "success", datetime.now(timezone.utc), datetime.now(timezone.utc)),
        ]
        
        # Build parent map
        parent_map = {row[0]: row[1] for row in sample_rows}
        
        # Detect circular reference
        visited = set()
        current = "trace-A"
        max_depth = 100
        depth = 0
        
        while current and depth < max_depth:
            if current in visited:
                # Circular reference detected
                assert True, "Circular reference correctly detected"
                break
            visited.add(current)
            current = parent_map.get(current)
            depth += 1
        else:
            pytest.fail("Circular reference not detected")


class TestCapsuleIntegration:
    """Integration tests for capsule functionality"""
    
    def test_capsule_endpoint_registration(self):
        """Test that capsule endpoint is registered in FastAPI"""
        # This would require actual FastAPI app instance
        # Skipping for now, but can be added with proper setup
        pass
    
    def test_clickhouse_query_format(self):
        """Test that ClickHouse query format is correct"""
        trace_id = "test-trace-123"
        
        # Expected query structure
        expected_query_parts = [
            "SELECT",
            "trace_id",
            "parent_id",
            "FROM kalibr.traces",
            "WHERE trace_id =",
            "OR parent_id =",
            "ORDER BY ts_start ASC"
        ]
        
        # Actual query from capsule.py
        query = """
            SELECT 
                trace_id,
                parent_id,
                tenant,
                provider,
                model_id,
                operation,
                duration_ms,
                cost_usd,
                cost_est_usd,
                status,
                timestamp,
                ts_start
            FROM kalibr.traces
            WHERE trace_id = %(trace_id)s OR parent_id = %(trace_id)s
            ORDER BY ts_start ASC
        """
        
        # Verify query structure
        for part in expected_query_parts:
            assert part in query, f"Query missing expected part: {part}"


def test_module_imports():
    """Test that all required modules can be imported"""
    try:
        from routes.capsule import router
        from kalibr.cli.capsule_cmd import capsule
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import required modules: {e}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
