"""
Demonstrates when to use success_when vs manual report().

Key principle:
- success_when: Simple validation based on LLM output (length, format, presence of key)
- manual report(): Complex validation requiring external checks, multiple steps, or business logic
"""

import os
import re
from kalibr import Router

# Example 1: Good use of success_when (simple validation)
def auto_report_example():
    """Use success_when for simple output validation."""

    router = Router(
        goal="extract_email",
        paths=["gpt-4o", "claude-sonnet-4-20250514"],
        # Simple check: output contains '@' character
        success_when=lambda output: "@" in output
    )

    messages = [
        {"role": "user", "content": "What's the email? Contact us at support@stripe.com"}
    ]

    # completion() will auto-call report() based on success_when
    response = router.completion(messages=messages)

    print(f"Extracted: {response.choices[0].message.content}")
    print("✓ Outcome auto-reported based on '@' presence")


# Example 2: When NOT to use success_when (complex validation)
def manual_report_example():
    """Use manual report() for complex validation."""

    router = Router(
        goal="book_meeting",
        paths=["gpt-4o", "claude-sonnet-4-20250514"]
        # NO success_when - validation is complex
    )

    messages = [
        {"role": "user", "content": "Book a meeting with John tomorrow at 2pm"}
    ]

    response = router.completion(messages=messages)
    llm_output = response.choices[0].message.content

    # Complex validation requiring multiple checks
    success = False
    reason = None

    # Check 1: LLM parsed the request correctly
    if "meeting" not in llm_output.lower():
        reason = "llm_did_not_understand"
    # Check 2: Extracted time is valid
    elif "2pm" not in llm_output and "14:00" not in llm_output:
        reason = "time_not_extracted"
    else:
        # Check 3: Actually book the meeting (external API call)
        try:
            # calendar_api.book(meeting_details)  # Simulated
            success = True
        except Exception as e:
            reason = f"calendar_api_failed: {str(e)}"

    # Manual report with detailed reason
    router.report(success=success, reason=reason)

    print(f"LLM output: {llm_output}")
    print(f"Meeting booked: {success}")
    if reason:
        print(f"Failure reason: {reason}")


# Example 3: Combining both patterns
def hybrid_example():
    """Sometimes you want both auto-validation AND manual override."""

    router = Router(
        goal="extract_json",
        paths=["gpt-4o", "claude-sonnet-4-20250514"],
        # Auto-check: output starts with '{'
        success_when=lambda output: output.strip().startswith("{")
    )

    messages = [
        {"role": "user", "content": "Extract as JSON: Company is Stripe, founded 2010"}
    ]

    response = router.completion(messages=messages)
    output = response.choices[0].message.content

    # success_when already reported, but we can add more detail
    # by checking if outcome was already reported
    import json
    try:
        data = json.loads(output)
        if "company" not in data:
            # Override the auto-report with more specific failure
            router.report(success=False, reason="missing_company_field")
    except:
        pass  # Auto-report already captured JSON parse failure


if __name__ == "__main__":
    if not os.getenv("KALIBR_API_KEY"):
        print("Set KALIBR_API_KEY environment variable")
        exit(1)

    print("=== Example 1: Auto-report with success_when ===\n")
    auto_report_example()

    print("\n=== Example 2: Manual report for complex validation ===\n")
    manual_report_example()

    print("\n=== Example 3: Hybrid approach ===\n")
    hybrid_example()
