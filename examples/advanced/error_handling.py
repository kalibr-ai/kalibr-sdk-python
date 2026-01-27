"""
Error handling with Kalibr Router.

Demonstrates:
1. Handling provider API errors (rate limits, auth failures)
2. Handling intelligence service failures (graceful fallback)
3. Using try/except patterns correctly
4. Auto-reporting of failures
"""

import os
import time
from kalibr import Router

def example_with_error_handling():
    """Example showing proper error handling patterns."""

    router = Router(
        goal="extract_company",
        paths=["gpt-4o", "claude-sonnet-4-20250514"]
    )

    messages = [{"role": "user", "content": "Hi, I'm Sarah from Stripe."}]

    # Provider errors propagate to caller - you must handle them
    try:
        response = router.completion(messages=messages)

        # Your validation logic
        company = response.choices[0].message.content

        if not company or len(company) == 0:
            # Empty response - report failure
            router.report(success=False, reason="empty_response")
            print("Failed: Empty response")
        else:
            # Success
            router.report(success=True)
            print(f"Success: Extracted '{company}'")

    except Exception as e:
        error_type = type(e).__name__

        # Kalibr auto-reports provider errors as failures before raising
        # So this is already recorded, but you still need to handle it

        if "RateLimitError" in error_type:
            print(f"Rate limited by provider: {e}")
            # Wait and retry logic here
            time.sleep(60)

        elif "AuthenticationError" in error_type:
            print(f"Authentication failed: {e}")
            print("Check your API keys!")

        elif "InvalidRequestError" in error_type:
            print(f"Invalid request: {e}")
            print("Check your messages format")

        else:
            print(f"Unexpected error: {error_type}: {e}")
            # Log to your error tracking system


def example_intelligence_service_fallback():
    """Example showing intelligence service fallback behavior."""

    # Even if intelligence service is down, Router falls back gracefully
    router = Router(
        goal="test_fallback",
        paths=["gpt-4o", "claude-sonnet-4-20250514"]  # First path is fallback
    )

    try:
        # If intelligence service can't be reached, Router uses first path (gpt-4o)
        response = router.completion(
            messages=[{"role": "user", "content": "Test"}]
        )

        # This will work even if https://kalibr-intelligence.fly.dev is down
        print(f"Response from fallback model: {response.choices[0].message.content}")

        # Report still works (queued for when service recovers)
        router.report(success=True)

    except Exception as e:
        # Provider errors still raise, but intelligence service failures don't
        print(f"Provider error (not intelligence service): {e}")


if __name__ == "__main__":
    if not os.getenv("KALIBR_API_KEY"):
        print("Set KALIBR_API_KEY environment variable")
        exit(1)

    print("=== Example 1: Provider Error Handling ===")
    example_with_error_handling()

    print("\n=== Example 2: Intelligence Service Fallback ===")
    example_intelligence_service_fallback()
