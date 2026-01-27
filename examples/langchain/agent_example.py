"""Agent usage with Kalibr LangChain integration.

This example shows how to trace LangChain agents with tools.
You'll see spans for the agent execution, tool calls, and LLM calls.

Prerequisites:
    pip install kalibr langchain langchain-openai
    export OPENAI_API_KEY="your-openai-key"
    export KALIBR_API_KEY="your-kalibr-key"
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from kalibr_langchain import KalibrCallbackHandler


# Define some example tools
@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    # Simulated weather data
    weather_data = {
        "paris": "Sunny, 22°C",
        "london": "Cloudy, 15°C",
        "tokyo": "Rainy, 18°C",
        "new york": "Partly cloudy, 20°C",
    }
    return weather_data.get(city.lower(), f"Weather data not available for {city}")


@tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression."""
    try:
        # Safe evaluation of simple math expressions
        result = eval(expression, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def main():
    # Create the Kalibr callback handler
    handler = KalibrCallbackHandler(
        tenant_id="demo-tenant",
        environment="dev",
        service="langchain-agent-demo",
        workflow_id="agent-with-tools",
    )

    # Create the LLM
    llm = ChatOpenAI(model="gpt-4o-mini")

    # Define the tools
    tools = [get_weather, calculate]

    # Create the prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. Use the available tools to help the user."),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Create the agent
    agent = create_openai_tools_agent(llm, tools, prompt)

    # Create the agent executor
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
    )

    # Run the agent with callbacks
    print("Running agent with tool calls...\n")

    queries = [
        "What's the weather like in Paris?",
        "What is 25 * 4 + 100?",
        "Compare the weather in London and Tokyo",
    ]

    for query in queries:
        print(f"\nQuery: {query}")
        print("-" * 50)

        result = executor.invoke(
            {"input": query},
            config={"callbacks": [handler]}
        )

        print(f"Result: {result['output']}")

    # Flush and shutdown
    handler.flush()
    handler.shutdown()

    print("\n" + "=" * 50)
    print("Done! Check your Kalibr dashboard for agent traces.")
    print("You should see nested spans for:")
    print("  - Agent chain execution")
    print("  - LLM calls for reasoning")
    print("  - Tool invocations")


if __name__ == "__main__":
    main()
