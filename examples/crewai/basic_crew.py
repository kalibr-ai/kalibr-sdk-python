"""Basic CrewAI usage with Kalibr integration.

This example shows how to use the KalibrCrewAIInstrumentor for
automatic tracing of CrewAI operations.

Prerequisites:
    pip install kalibr[crewai]
    export OPENAI_API_KEY="your-openai-key"
    export KALIBR_API_KEY="your-kalibr-key"
"""

import os
from kalibr_crewai import KalibrCrewAIInstrumentor

# Instrument BEFORE importing CrewAI classes
instrumentor = KalibrCrewAIInstrumentor(
    tenant_id="demo-tenant",
    environment="dev",
    service="crewai-demo",
)
instrumentor.instrument()

# Now import and use CrewAI normally
from crewai import Agent, Task, Crew


def main():
    # Create agents
    researcher = Agent(
        role="Senior Researcher",
        goal="Find and summarize the latest AI developments",
        backstory="You are an expert AI researcher with deep knowledge of machine learning.",
        verbose=True,
    )

    writer = Agent(
        role="Technical Writer",
        goal="Write clear and engaging content about AI",
        backstory="You are a skilled technical writer who makes complex topics accessible.",
        verbose=True,
    )

    # Create tasks
    research_task = Task(
        description="Research the latest developments in AI agents and multi-agent systems.",
        expected_output="A summary of 3-5 key developments with their implications.",
        agent=researcher,
    )

    writing_task = Task(
        description="Write a short blog post based on the research findings.",
        expected_output="A 200-word blog post suitable for a tech audience.",
        agent=writer,
    )

    # Create and run crew
    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        verbose=True,
    )

    print("Starting crew execution...")
    print("=" * 50)

    result = crew.kickoff()

    print("=" * 50)
    print("Crew execution complete!")
    print(f"Result: {result}")

    # Flush events before exit
    instrumentor.flush()

    print("\nCheck your Kalibr dashboard for traces!")


if __name__ == "__main__":
    main()
