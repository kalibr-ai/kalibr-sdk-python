#!/usr/bin/env python3
"""End-to-End Test: SDK to Intelligence API Flow

This script tests the full flow from Kalibr SDK tracing to Intelligence API:
1. Simulates 100 LLM calls per model using the SDK's tracing
2. Reports outcomes to the Intelligence API
3. Queries the Intelligence API for recommendations
4. Verifies the best-performing model is recommended

Usage:
    python examples/test_e2e_intelligence.py
"""

import json
import os
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

# =============================================================================
# CONFIGURATION
# =============================================================================

API_KEY = "sk_0f065a78071045d3a6d36a9456920a30fb1ad2395be44d36b96eadb18fdcf8f7"
TENANT_ID = "test-dk"
BACKEND_URL = "https://kalibr-backend.fly.dev"
INTELLIGENCE_URL = "https://kalibr-intelligence.fly.dev"

# Goal for this test (should be unique/new)
GOAL = "schedule_interview"

# Model scenarios with expected performance characteristics
# Format: (model_id, provider, success_rate, avg_cost, avg_duration_ms)
SCENARIOS = [
    {
        "model_id": "gpt-4o-mini",
        "provider": "openai",
        "success_rate": 0.90,  # 90% success - EXPECTED WINNER
        "avg_cost": 0.01,
        "avg_duration_ms": 800,
        "input_tokens": 500,
        "output_tokens": 200,
    },
    {
        "model_id": "claude-3-haiku",
        "provider": "anthropic",
        "success_rate": 0.60,  # 60% success
        "avg_cost": 0.008,
        "avg_duration_ms": 500,
        "input_tokens": 400,
        "output_tokens": 150,
    },
    {
        "model_id": "gpt-4o",
        "provider": "openai",
        "success_rate": 0.70,  # 70% success
        "avg_cost": 0.03,
        "avg_duration_ms": 2000,
        "input_tokens": 600,
        "output_tokens": 300,
    },
]

CALLS_PER_MODEL = 100
EXPECTED_WINNER = "gpt-4o-mini"

# =============================================================================
# SDK TRACE SIMULATION
# =============================================================================


def generate_trace_id() -> str:
    """Generate a UUID v4 trace ID."""
    return str(uuid.uuid4())


def generate_span_id() -> str:
    """Generate a UUID v4 span ID."""
    return str(uuid.uuid4())


def create_trace_event(
    trace_id: str,
    model_id: str,
    provider: str,
    duration_ms: int,
    cost_usd: float,
    input_tokens: int,
    output_tokens: int,
    status: str = "success",
) -> dict[str, Any]:
    """Create a trace event payload matching the SDK schema."""
    now = datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": "1.0",
        "trace_id": trace_id,
        "span_id": generate_span_id(),
        "parent_span_id": None,
        "tenant_id": TENANT_ID,
        "workflow_id": "e2e-intelligence-test",
        "sandbox_id": "test-sandbox",
        "runtime_env": "test",
        "provider": provider,
        "model_name": model_id,
        "model_id": model_id,
        "operation": "chat_completion",
        "endpoint": "test_e2e_intelligence",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
        "latency_ms": duration_ms,
        "unit_price_usd": cost_usd / (input_tokens + output_tokens) if (input_tokens + output_tokens) > 0 else 0,
        "total_cost_usd": round(cost_usd, 6),
        "cost_usd": round(cost_usd, 6),
        "status": status,
        "error_type": None,
        "error_message": None,
        "timestamp": now,
        "ts_start": now,
        "ts_end": now,
        "environment": "test",
        "service": "e2e-intelligence-test",
        "vendor": provider,
        "data_class": "economic",
    }


def send_trace_to_backend(session: requests.Session, event: dict) -> bool:
    """Send a trace event to the backend collector."""
    url = f"{BACKEND_URL}/api/ingest"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/x-ndjson",
    }

    # Send as NDJSON format
    body = json.dumps(event) + "\n"

    try:
        response = session.post(url, headers=headers, data=body, timeout=30)
        return response.status_code in (200, 201, 202)
    except Exception as e:
        print(f"  [ERROR] Failed to send trace: {e}")
        return False


# =============================================================================
# INTELLIGENCE API
# =============================================================================


def report_outcome_to_intelligence(
    session: requests.Session,
    trace_id: str,
    goal: str,
    success: bool,
) -> bool:
    """Report an outcome to the Intelligence API."""
    url = f"{INTELLIGENCE_URL}/api/v1/intelligence/report-outcome"
    headers = {
        "X-API-Key": API_KEY,
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json",
    }
    payload = {
        "trace_id": trace_id,
        "goal": goal,
        "success": success,
    }

    try:
        response = session.post(url, headers=headers, json=payload, timeout=30)
        return response.status_code in (200, 201, 202)
    except Exception as e:
        print(f"  [ERROR] Failed to report outcome: {e}")
        return False


def get_policy_from_intelligence(
    session: requests.Session,
    goal: str,
) -> dict | None:
    """Query the Intelligence API for a policy recommendation."""
    url = f"{INTELLIGENCE_URL}/api/v1/intelligence/policy"
    headers = {
        "X-API-Key": API_KEY,
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json",
    }
    payload = {
        "goal": goal,
    }

    try:
        response = session.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  [ERROR] Policy request failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"  [ERROR] Failed to get policy: {e}")
        return None


# =============================================================================
# SIMULATION
# =============================================================================


def simulate_model_calls(session: requests.Session, scenario: dict) -> tuple[int, int]:
    """Simulate CALLS_PER_MODEL calls for a given model scenario.

    Returns:
        Tuple of (successful_traces, successful_outcomes)
    """
    model_id = scenario["model_id"]
    provider = scenario["provider"]
    success_rate = scenario["success_rate"]
    avg_cost = scenario["avg_cost"]
    avg_duration_ms = scenario["avg_duration_ms"]
    input_tokens = scenario["input_tokens"]
    output_tokens = scenario["output_tokens"]

    print(f"\n  Simulating {CALLS_PER_MODEL} calls for {model_id}...")
    print(f"    Expected success rate: {success_rate:.0%}")

    traces_sent = 0
    outcomes_reported = 0
    successes = 0

    for i in range(CALLS_PER_MODEL):
        # Generate trace ID
        trace_id = generate_trace_id()

        # Determine if this call is successful based on success rate
        is_success = random.random() < success_rate
        if is_success:
            successes += 1

        # Add variance to duration and cost (+-20%)
        variance = random.uniform(0.8, 1.2)
        duration = int(avg_duration_ms * variance)
        cost = round(avg_cost * variance, 6)

        # Create and send trace event
        status = "success" if is_success else "error"
        event = create_trace_event(
            trace_id=trace_id,
            model_id=model_id,
            provider=provider,
            duration_ms=duration,
            cost_usd=cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status=status,
        )

        if send_trace_to_backend(session, event):
            traces_sent += 1

        # Report outcome to intelligence
        if report_outcome_to_intelligence(session, trace_id, GOAL, is_success):
            outcomes_reported += 1

        # Progress indicator every 25 calls
        if (i + 1) % 25 == 0:
            print(f"    Progress: {i + 1}/{CALLS_PER_MODEL} calls")

    actual_success_rate = successes / CALLS_PER_MODEL
    print(f"    Completed: {traces_sent} traces, {outcomes_reported} outcomes reported")
    print(f"    Actual success rate: {actual_success_rate:.0%} ({successes}/{CALLS_PER_MODEL})")

    return traces_sent, outcomes_reported


# =============================================================================
# MAIN TEST
# =============================================================================


def main():
    print("=" * 70)
    print("KALIBR E2E INTELLIGENCE TEST")
    print("=" * 70)
    print(f"\nGoal: {GOAL}")
    print(f"Backend: {BACKEND_URL}")
    print(f"Intelligence: {INTELLIGENCE_URL}")
    print(f"Tenant: {TENANT_ID}")
    print(f"Calls per model: {CALLS_PER_MODEL}")
    print(f"Expected winner: {EXPECTED_WINNER}")

    # Create HTTP session
    session = requests.Session()

    try:
        # ---------------------------------------------------------------------
        # STEP 1: Simulate LLM calls for all scenarios
        # ---------------------------------------------------------------------
        print("\n" + "-" * 70)
        print("STEP 1: Simulating LLM calls and reporting outcomes")
        print("-" * 70)

        total_traces = 0
        total_outcomes = 0

        for scenario in SCENARIOS:
            traces, outcomes = simulate_model_calls(session, scenario)
            total_traces += traces
            total_outcomes += outcomes

        print(f"\n  TOTAL: {total_traces} traces sent, {total_outcomes} outcomes reported")

        # ---------------------------------------------------------------------
        # STEP 2: Wait for data propagation
        # ---------------------------------------------------------------------
        print("\n" + "-" * 70)
        print("STEP 2: Waiting for data propagation (5 seconds)")
        print("-" * 70)

        for i in range(5, 0, -1):
            print(f"  {i}...")
            time.sleep(1)

        # ---------------------------------------------------------------------
        # STEP 3: Query Intelligence API
        # ---------------------------------------------------------------------
        print("\n" + "-" * 70)
        print("STEP 3: Querying Intelligence API for recommendation")
        print("-" * 70)

        policy = get_policy_from_intelligence(session, GOAL)

        if policy is None:
            print("\n[FAIL] Could not get policy from Intelligence API")
            return False

        print(f"\n  Policy Response:")
        print(f"    Goal: {policy.get('goal', 'N/A')}")
        print(f"    Recommended Model: {policy.get('recommended_model', 'N/A')}")
        print(f"    Recommended Provider: {policy.get('recommended_provider', 'N/A')}")
        print(f"    Success Rate: {policy.get('outcome_success_rate', 0):.0%}")
        print(f"    Sample Count: {policy.get('outcome_sample_count', 'N/A')}")
        print(f"    Confidence: {policy.get('confidence', 0):.0%}")
        print(f"    Risk Score: {policy.get('risk_score', 'N/A')}")
        print(f"    Reasoning: {policy.get('reasoning', 'N/A')}")

        # Show alternatives if available
        alternatives = policy.get("alternatives", [])
        if alternatives:
            print(f"\n  Alternatives:")
            for alt in alternatives[:3]:  # Show top 3
                print(f"    - {alt.get('model', 'N/A')}: {alt.get('success_rate', 0):.0%} success rate")

        # ---------------------------------------------------------------------
        # STEP 4: Verify result
        # ---------------------------------------------------------------------
        print("\n" + "-" * 70)
        print("STEP 4: Verifying recommendation")
        print("-" * 70)

        recommended_model = policy.get("recommended_model", "")

        if recommended_model == EXPECTED_WINNER:
            print(f"\n  [PASS] Intelligence API correctly recommended {EXPECTED_WINNER}")
            print("         This model had the highest success rate (90%)")
            result = True
        else:
            print(f"\n  [FAIL] Expected {EXPECTED_WINNER}, got {recommended_model}")
            print("         The model with 90% success rate should have been recommended")
            # Don't fail hard - the intelligence might need more data or time
            result = False

        # ---------------------------------------------------------------------
        # Final Summary
        # ---------------------------------------------------------------------
        print("\n" + "=" * 70)
        if result:
            print("TEST RESULT: PASS")
        else:
            print("TEST RESULT: FAIL")
            print("\nNote: If this is a new goal, the Intelligence API may need more")
            print("data or time to converge on the optimal recommendation.")
        print("=" * 70)

        return result

    finally:
        session.close()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
