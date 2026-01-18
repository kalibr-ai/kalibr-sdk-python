"""
Multi-turn conversation example with Kalibr.

Demonstrates:
1. Using force_model to keep consistent model across conversation turns
2. Reporting outcome only after conversation completes
3. Building conversation history correctly
"""

import os
from kalibr import Router

def customer_support_conversation():
    """Multi-turn customer support conversation."""

    # Create router for support conversations
    router = Router(
        goal="customer_support_conversation",
        paths=["gpt-4o", "claude-sonnet-4-20250514"]
    )

    # First turn - router decides which model to use
    conversation = [{"role": "user", "content": "I can't log into my account"}]

    response1 = router.completion(messages=conversation)
    selected_model = response1.model  # Track which model was selected

    # Add assistant response to conversation
    conversation.append({
        "role": "assistant",
        "content": response1.choices[0].message.content
    })

    print(f"Assistant (Turn 1, {selected_model}): {response1.choices[0].message.content}")

    # Turn 2 - force same model for consistency
    conversation.append({
        "role": "user",
        "content": "I tried that but still getting an error"
    })

    response2 = router.completion(
        messages=conversation,
        force_model=selected_model  # Keep same model
    )

    conversation.append({
        "role": "assistant",
        "content": response2.choices[0].message.content
    })

    print(f"Assistant (Turn 2, {selected_model}): {response2.choices[0].message.content}")

    # Turn 3 - still same model
    conversation.append({
        "role": "user",
        "content": "That worked! Thanks!"
    })

    response3 = router.completion(
        messages=conversation,
        force_model=selected_model
    )

    print(f"Assistant (Turn 3, {selected_model}): {response3.choices[0].message.content}")

    # Report outcome ONCE at the end when we know overall success
    # In this case, user said "that worked" so we succeeded
    issue_resolved = "worked" in conversation[-1]["content"].lower()

    router.report(
        success=issue_resolved,
        score=1.0 if issue_resolved else 0.0
    )

    print(f"\nConversation outcome: {'Success' if issue_resolved else 'Failed'}")
    print(f"Kalibr will learn that {selected_model} {'works well' if issue_resolved else 'needs improvement'} for support conversations")

if __name__ == "__main__":
    if not os.getenv("KALIBR_API_KEY"):
        print("Set KALIBR_API_KEY environment variable")
        exit(1)

    customer_support_conversation()
