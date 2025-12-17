"""Example: Outcome-Conditioned Routing with Kalibr

This example shows how to use Kalibr's outcome routing to:
1. Query for the best model based on historical success rates
2. Report outcomes to teach Kalibr what works

The system learns over time which execution paths lead to success
for each goal, and recommends those paths to future executions.
"""

import os
from kalibr import get_policy, report_outcome, get_trace_id

# Ensure environment is configured
# export KALIBR_API_KEY=your-api-key
# export KALIBR_TENANT_ID=your-tenant-id


def book_meeting_agent():
    """Example agent that books meetings."""

    # Step 1: Query Kalibr for the best execution path
    try:
        policy = get_policy(goal="book_meeting")

        print(f"Kalibr recommends: {policy['recommended_model']}")
        print(f"  Provider: {policy['recommended_provider']}")
        print(f"  Success rate: {policy['outcome_success_rate']:.0%}")
        print(f"  Confidence: {policy['confidence']:.0%}")
        print(f"  Reasoning: {policy['reasoning']}")

        # Use the recommended model
        model = policy["recommended_model"]
        provider = policy["recommended_provider"]

    except Exception as e:
        # Fall back to default if intelligence unavailable
        print(f"Intelligence unavailable, using default: {e}")
        model = "gpt-4o"
        provider = "openai"

    # Step 2: Execute your agent logic
    trace_id = get_trace_id()  # Get current trace ID from Kalibr context

    try:
        # ... your actual agent logic here ...
        # This would call the LLM, use tools, etc.

        success = True  # Assume success for this example
        meeting_booked = True

    except Exception as e:
        success = False
        meeting_booked = False
        failure_reason = str(e)

    # Step 3: Report the outcome to Kalibr
    if success and meeting_booked:
        report_outcome(
            trace_id=trace_id,
            goal="book_meeting",
            success=True,
            score=1.0,  # Optional: quality score
        )
        print("Meeting booked! Outcome reported to Kalibr.")
    else:
        report_outcome(
            trace_id=trace_id,
            goal="book_meeting",
            success=False,
            failure_reason=failure_reason if not success else "meeting_not_booked",
        )
        print("Failed to book meeting. Outcome reported to Kalibr.")

    # Over time, Kalibr learns which models/paths work best for booking meetings
    # and will recommend those to future executions.


def main():
    """Run the example."""
    print("=" * 60)
    print("Kalibr Outcome-Conditioned Routing Example")
    print("=" * 60)
    print()

    # Check for required env vars
    if not os.getenv("KALIBR_API_KEY"):
        print("Warning: Set KALIBR_API_KEY environment variable")
        print("   export KALIBR_API_KEY=your-api-key")
        return

    if not os.getenv("KALIBR_TENANT_ID"):
        print("Warning: Set KALIBR_TENANT_ID environment variable")
        print("   export KALIBR_TENANT_ID=your-tenant-id")
        return

    book_meeting_agent()


if __name__ == "__main__":
    main()
