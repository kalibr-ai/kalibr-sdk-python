"""Async usage with Kalibr LangChain integration.

This example shows how to use the AsyncKalibrCallbackHandler with
async LangChain operations.

Prerequisites:
    pip install kalibr langchain-openai
    export OPENAI_API_KEY="your-openai-key"
    export KALIBR_API_KEY="your-kalibr-key"
"""

import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from kalibr_langchain import AsyncKalibrCallbackHandler


async def main():
    # Create the async Kalibr callback handler
    handler = AsyncKalibrCallbackHandler(
        tenant_id="demo-tenant",
        environment="dev",
        service="langchain-async-demo",
        workflow_id="parallel-generation",
    )

    # Build a chain
    prompt = ChatPromptTemplate.from_template(
        "Write a one-sentence description of {country}."
    )
    llm = ChatOpenAI(model="gpt-4o-mini")
    parser = StrOutputParser()

    chain = prompt | llm | parser

    # Run multiple chains in parallel - all will be traced
    print("Generating descriptions for multiple countries in parallel...")

    countries = ["France", "Japan", "Brazil", "Egypt", "Australia"]

    # Create tasks for parallel execution
    tasks = [
        chain.ainvoke(
            {"country": country},
            config={"callbacks": [handler]}
        )
        for country in countries
    ]

    # Run all tasks concurrently
    results = await asyncio.gather(*tasks)

    # Print results
    for country, result in zip(countries, results):
        print(f"\n{country}: {result}")

    # Flush remaining events and close
    await handler.flush()
    await handler.close()

    print("\nDone! Check your Kalibr dashboard for the async traces.")
    print("You should see parallel traces with the same workflow ID.")


if __name__ == "__main__":
    asyncio.run(main())
