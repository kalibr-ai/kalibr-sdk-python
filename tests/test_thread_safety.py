"""Tests for thread-safety in singleton patterns and shared state.

Tests concurrent access to:
- Intelligence client singleton
- Instrumentation singletons (OpenAI, Anthropic, Google)
- Collector singleton
- TraceCapsule append operations
- Instrumentation registry

These tests verify that no race conditions occur under heavy concurrent load.
"""

import threading
import time
from typing import List

import pytest


class TestSingletonThreadSafety:
    """Test thread-safe singleton patterns"""

    def test_intelligence_client_concurrent_creation(self):
        """Test that concurrent requests to intelligence client create only one instance"""
        from kalibr import intelligence

        # Reset singleton for clean test
        intelligence._intelligence_client = None

        instances = []
        lock = threading.Lock()

        def get_client():
            client = intelligence._get_intelligence_client()
            with lock:
                instances.append(client)

        # Create 50 threads trying to get the client simultaneously
        threads = [threading.Thread(target=get_client) for _ in range(50)]

        # Start all threads at once
        for t in threads:
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join()

        # Verify only one instance was created
        unique_instances = set(id(inst) for inst in instances)
        assert len(unique_instances) == 1, f"Expected 1 unique instance, got {len(unique_instances)}"

    def test_openai_instrumentation_concurrent_creation(self):
        """Test that concurrent OpenAI instrumentation requests create only one instance"""
        from kalibr.instrumentation import openai_instr

        # Reset singleton for clean test
        openai_instr._openai_instrumentation = None

        instances = []
        lock = threading.Lock()

        def get_instrumentation():
            instr = openai_instr.get_instrumentation()
            with lock:
                instances.append(instr)

        # Create 50 threads
        threads = [threading.Thread(target=get_instrumentation) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify only one instance
        unique_instances = set(id(inst) for inst in instances)
        assert len(unique_instances) == 1, f"Expected 1 unique instance, got {len(unique_instances)}"

    def test_anthropic_instrumentation_concurrent_creation(self):
        """Test that concurrent Anthropic instrumentation requests create only one instance"""
        from kalibr.instrumentation import anthropic_instr

        # Reset singleton
        anthropic_instr._anthropic_instrumentation = None

        instances = []
        lock = threading.Lock()

        def get_instrumentation():
            instr = anthropic_instr.get_instrumentation()
            with lock:
                instances.append(instr)

        threads = [threading.Thread(target=get_instrumentation) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        unique_instances = set(id(inst) for inst in instances)
        assert len(unique_instances) == 1

    def test_google_instrumentation_concurrent_creation(self):
        """Test that concurrent Google instrumentation requests create only one instance"""
        from kalibr.instrumentation import google_instr

        # Reset singleton
        google_instr._google_instrumentation = None

        instances = []
        lock = threading.Lock()

        def get_instrumentation():
            instr = google_instr.get_instrumentation()
            with lock:
                instances.append(instr)

        threads = [threading.Thread(target=get_instrumentation) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        unique_instances = set(id(inst) for inst in instances)
        assert len(unique_instances) == 1

    def test_collector_concurrent_setup(self):
        """Test that concurrent collector setup creates only one provider"""
        from kalibr import collector

        # Reset collector state
        collector._tracer_provider = None
        collector._is_configured = False

        providers = []
        lock = threading.Lock()

        def setup():
            provider = collector.setup_collector(service_name="test-service", file_export=False)
            with lock:
                providers.append(provider)

        # Create 30 threads
        threads = [threading.Thread(target=setup) for _ in range(30)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify only one provider was created
        unique_providers = set(id(p) for p in providers)
        assert len(unique_providers) == 1, f"Expected 1 unique provider, got {len(unique_providers)}"

        # Cleanup
        collector.shutdown_collector()


class TestSharedStateThreadSafety:
    """Test thread-safe shared state operations"""

    def test_registry_concurrent_instrumentation(self):
        """Test that concurrent instrumentation registration is thread-safe"""
        from kalibr.instrumentation import registry

        # Reset registry
        with registry._registry_lock:
            registry._instrumented_providers.clear()

        results = []
        lock = threading.Lock()

        def auto_instrument():
            # Try to instrument (will fail if SDK not installed, but that's ok)
            result = registry.auto_instrument(["openai"])
            with lock:
                results.append(result)

        # Create 20 threads trying to instrument simultaneously
        threads = [threading.Thread(target=auto_instrument) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Check final state
        providers = registry.get_instrumented_providers()

        # Should have consistent state (either instrumented or not, but not corrupted)
        assert isinstance(providers, list)
        # If instrumentation succeeded, should only have openai once
        assert providers.count("openai") <= 1

    def test_capsule_concurrent_append(self):
        """Test that concurrent append_hop operations are thread-safe"""
        from kalibr.trace_capsule import TraceCapsule

        capsule = TraceCapsule()
        errors = []

        def append_hops(thread_id: int, count: int):
            try:
                for i in range(count):
                    capsule.append_hop({
                        "provider": "openai",
                        "operation": f"thread_{thread_id}_op_{i}",
                        "model": "gpt-4o",
                        "duration_ms": 100,
                        "status": "success",
                        "cost_usd": 0.01,
                    })
            except Exception as e:
                errors.append(e)

        # Create 10 threads, each appending 20 hops
        num_threads = 10
        hops_per_thread = 20
        threads = [
            threading.Thread(target=append_hops, args=(i, hops_per_thread))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent append: {errors}"

        # Verify final state is consistent
        # Should have at most MAX_HOPS in the list
        assert len(capsule.last_n_hops) <= capsule.MAX_HOPS

        # All hops should have valid hop_index
        for hop in capsule.last_n_hops:
            assert "hop_index" in hop
            assert isinstance(hop["hop_index"], int)
            assert hop["hop_index"] >= 0

    def test_capsule_correct_hop_indices(self):
        """Test that hop indices are correctly assigned under concurrency"""
        from kalibr.trace_capsule import TraceCapsule

        capsule = TraceCapsule()

        def append_single_hop(thread_id: int):
            capsule.append_hop({
                "provider": "openai",
                "operation": f"thread_{thread_id}",
                "status": "success",
            })
            time.sleep(0.001)  # Small delay to increase chance of contention

        # Append 5 hops (less than MAX_HOPS to see all indices)
        threads = [threading.Thread(target=append_single_hop, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify we have 5 hops
        assert len(capsule.last_n_hops) == 5

        # Verify hop indices are sequential from 0 to 4
        indices = sorted([hop["hop_index"] for hop in capsule.last_n_hops])
        assert indices == [0, 1, 2, 3, 4], f"Expected [0,1,2,3,4], got {indices}"

    def test_capsule_correct_aggregates(self):
        """Test that aggregate calculations are correct under concurrency"""
        from kalibr.trace_capsule import TraceCapsule

        capsule = TraceCapsule()

        cost_per_hop = 0.01
        latency_per_hop = 100

        def append_hops(count: int):
            for _ in range(count):
                capsule.append_hop({
                    "provider": "openai",
                    "operation": "test",
                    "status": "success",
                    "cost_usd": cost_per_hop,
                    "duration_ms": latency_per_hop,
                })

        # 10 threads, 10 hops each = 100 total hops
        num_threads = 10
        hops_per_thread = 10
        threads = [
            threading.Thread(target=append_hops, args=(hops_per_thread,))
            for _ in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify aggregate cost (100 hops * $0.01)
        expected_cost = num_threads * hops_per_thread * cost_per_hop
        assert abs(capsule.aggregate_cost_usd - expected_cost) < 0.0001, \
            f"Expected cost ${expected_cost}, got ${capsule.aggregate_cost_usd}"

        # Verify aggregate latency (100 hops * 100ms)
        expected_latency = num_threads * hops_per_thread * latency_per_hop
        assert abs(capsule.aggregate_latency_ms - expected_latency) < 0.1, \
            f"Expected latency {expected_latency}ms, got {capsule.aggregate_latency_ms}ms"


class TestStressTests:
    """Stress tests with high concurrency"""

    def test_high_concurrency_stress_test(self):
        """Stress test with 100 threads accessing multiple singletons"""
        from kalibr import intelligence
        from kalibr.instrumentation import openai_instr, anthropic_instr

        # Reset singletons
        intelligence._intelligence_client = None
        openai_instr._openai_instrumentation = None
        anthropic_instr._anthropic_instrumentation = None

        errors = []

        def stress_worker(worker_id: int):
            try:
                # Access multiple singletons
                _ = intelligence._get_intelligence_client()
                _ = openai_instr.get_instrumentation()
                _ = anthropic_instr.get_instrumentation()
                time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append((worker_id, e))

        # Create 100 threads
        threads = [threading.Thread(target=stress_worker, args=(i,)) for i in range(100)]

        start_time = time.time()

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        duration = time.time() - start_time

        # Verify no errors
        assert len(errors) == 0, f"Errors during stress test: {errors}"

        # Should complete reasonably fast (under 5 seconds)
        assert duration < 5.0, f"Stress test took too long: {duration}s"

    def test_reproduce_issue_30(self):
        """Reproduce the exact scenario from issue #30"""
        from kalibr import intelligence

        # Reset singleton
        intelligence._intelligence_client = None

        instances_created = []
        lock = threading.Lock()

        def call_get_policy():
            """Simulate calling get_policy multiple times"""
            try:
                for _ in range(100):
                    # This internally calls _get_intelligence_client()
                    client = intelligence._get_intelligence_client()
                    with lock:
                        if id(client) not in [id(i) for i in instances_created]:
                            instances_created.append(client)
            except Exception:
                pass  # Some calls may fail (e.g., missing API key), that's ok

        # Create 10 threads as in the issue
        threads = [threading.Thread(target=call_get_policy) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # The bug would have created multiple instances
        # With the fix, should only have 1 instance
        assert len(instances_created) == 1, \
            f"Expected 1 KalibrIntelligence instance, got {len(instances_created)}"

    def test_concurrent_capsule_operations_stress(self):
        """Stress test TraceCapsule with many concurrent operations"""
        from kalibr.trace_capsule import TraceCapsule

        capsule = TraceCapsule()
        errors = []

        def stress_append(thread_id: int):
            try:
                for i in range(50):  # 50 operations per thread
                    capsule.append_hop({
                        "provider": "openai",
                        "operation": f"t{thread_id}_op{i}",
                        "status": "success",
                        "cost_usd": 0.001,
                        "duration_ms": 10,
                    })
            except Exception as e:
                errors.append((thread_id, e))

        # 50 threads * 50 operations = 2500 total operations
        threads = [threading.Thread(target=stress_append, args=(i,)) for i in range(50)]

        start_time = time.time()

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        duration = time.time() - start_time

        # Verify no errors
        assert len(errors) == 0, f"Errors during stress test: {errors}"

        # Verify capsule is in valid state
        assert len(capsule.last_n_hops) <= capsule.MAX_HOPS

        # Verify aggregates are consistent (2500 ops * $0.001 * 10ms)
        expected_cost = 2500 * 0.001
        expected_latency = 2500 * 10

        assert abs(capsule.aggregate_cost_usd - expected_cost) < 0.01
        assert abs(capsule.aggregate_latency_ms - expected_latency) < 1.0

        # Should complete in reasonable time (under 10 seconds)
        assert duration < 10.0, f"Stress test took too long: {duration}s"


class TestRegistryThreadSafety:
    """Additional tests for instrumentation registry"""

    def test_concurrent_is_instrumented_calls(self):
        """Test that concurrent is_instrumented() calls are safe"""
        from kalibr.instrumentation import registry

        results = []
        lock = threading.Lock()

        def check_instrumented(provider: str):
            for _ in range(100):
                result = registry.is_instrumented(provider)
                with lock:
                    results.append(result)

        threads = [
            threading.Thread(target=check_instrumented, args=("openai",))
            for _ in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 1000 results, all bool
        assert len(results) == 1000
        assert all(isinstance(r, bool) for r in results)

    def test_concurrent_get_instrumented_providers(self):
        """Test that concurrent get_instrumented_providers() calls are safe"""
        from kalibr.instrumentation import registry

        results = []
        lock = threading.Lock()

        def get_providers():
            for _ in range(50):
                providers = registry.get_instrumented_providers()
                with lock:
                    results.append(providers)

        threads = [threading.Thread(target=get_providers) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 500 results, all lists
        assert len(results) == 500
        assert all(isinstance(r, list) for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

