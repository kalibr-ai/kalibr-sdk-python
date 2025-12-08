"""Basic OpenAI Agents SDK usage with Kalibr integration.

This example shows how to use setup_kalibr_tracing for
automatic tracing of OpenAI Agents operations.

Prerequisites:
    pip install kalibr[openai-agents]
    export OPENAI_API_KEY="your-openai-key"
    export KALIBR_API_KEY="your-kalibr-key"
"""

from kalibr_openai_agents import setup_kalibr_tracing

# Set up tracing BEFORE importing agents
processor = setup_kalibr_tracing(
    tenant_id="demo-tenant",
    environment="dev",
    service="openai-agents-demo",
)

# Now import and use OpenAI Agents
from agents import Agent, Runner


def main():
    # Create an agent
    assistant = Agent(
        name="Assistant",
        instructions="""You are a helpful assistant.
        Answer questions concisely and accurately.""",
    )

    print("Starting agent conversation...")
    print("=" * 50)

    # Run the agent
    result = Runner.run_sync(
        assistant,
        "What are the three laws of robotics?",
    )

    print(f"\nAgent response: {result.final_output}")
    print("=" * 50)

    # Force flush events
    processor.force_flush()

    print("\nCheck your Kalibr dashboard for traces!")
    print("You should see:")
    print("  - Trace for the full conversation")
    print("  - Generation spans for LLM calls")
    print("  - Agent spans for agent execution")


if __name__ == "__main__":
    main()
