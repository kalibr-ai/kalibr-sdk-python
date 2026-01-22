"""
Parameter-based routing example.

Demonstrates:
1. Routing between different parameter configurations of the same model
2. Learning which temperature/parameters work best for your goal
3. Each (model, params) combination is a separate path
"""

import os
import json
from kalibr import Router

def test_temperature_routing():
    """Learn which temperature works best for creative writing."""

    # Define paths with different temperatures
    router = Router(
        goal="creative_story_writing",
        paths=[
            {"model": "gpt-4o", "params": {"temperature": 0.3}},  # Conservative
            {"model": "gpt-4o", "params": {"temperature": 0.7}},  # Balanced
            {"model": "gpt-4o", "params": {"temperature": 0.9}},  # Creative
        ]
    )

    print("Testing different temperature settings for creative writing...")
    print("Kalibr will learn which temperature produces the best stories.\n")

    # Simulate multiple requests
    prompts = [
        "Write a short story about a time-traveling chef",
        "Write a story about a robot learning to paint",
        "Write a story about a magical library"
    ]

    for i, prompt in enumerate(prompts, 1):
        messages = [{"role": "user", "content": prompt}]

        response = router.completion(messages=messages)
        story = response.choices[0].message.content

        # Simulate evaluation (in real use, this would be human feedback or validation)
        # For demo purposes, we'll check story length and creativity markers
        has_dialogue = '"' in story or "'" in story
        good_length = len(story) > 200

        success = has_dialogue and good_length

        print(f"Story {i}:")
        print(f"  Model used: gpt-4o")
        print(f"  Temperature: {response.choices[0].message.content[:50]}...")
        print(f"  Quality: {'✓ Good' if success else '✗ Needs improvement'}")

        router.report(
            success=success,
            score=1.0 if success else 0.5
        )
        print()

    print("After enough iterations, Kalibr will route to the temperature that works best!")


def test_json_mode_routing():
    """Test routing between models with and without JSON mode."""

    router = Router(
        goal="structured_data_extraction",
        paths=[
            {"model": "gpt-4o", "params": {"response_format": {"type": "json_object"}}},
            {"model": "gpt-4o", "params": {}},  # No JSON mode
        ]
    )

    messages = [
        {"role": "system", "content": "Extract company info as JSON with keys: name, industry, location"},
        {"role": "user", "content": "Stripe is a payment processing company based in San Francisco"}
    ]

    response = router.completion(messages=messages)
    output = response.choices[0].message.content

    # Validate JSON
    try:
        data = json.loads(output)
        required_keys = {"name", "industry", "location"}

        if required_keys.issubset(data.keys()):
            router.report(success=True)
            print("✓ Valid JSON with all required fields")
            print(json.dumps(data, indent=2))
        else:
            router.report(success=False, reason="missing_required_fields")
            print("✗ JSON missing required fields")

    except json.JSONDecodeError:
        router.report(success=False, reason="invalid_json")
        print("✗ Invalid JSON output")


if __name__ == "__main__":
    if not os.getenv("KALIBR_API_KEY"):
        print("Set KALIBR_API_KEY environment variable")
        exit(1)

    print("=== Example 1: Temperature Routing ===\n")
    test_temperature_routing()

    print("\n=== Example 2: JSON Mode Routing ===\n")
    test_json_mode_routing()
