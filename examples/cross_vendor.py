"""
Cross-Vendor Example with Auto-Instrumentation

This example demonstrates:
1. Calling multiple LLM providers in a single request
2. All SDK calls are automatically traced
3. Cost aggregation across vendors
4. Latency comparison

Note: This is a demonstration script that requires API keys.
Set environment variables for the providers you want to test:
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- GOOGLE_API_KEY
"""

import os
from kalibr import Kalibr

app = Kalibr(title="Cross-Vendor Agent", description="Compare responses across providers")


@app.action("compare_providers", "Get responses from multiple LLM providers")
def compare_providers(question: str) -> dict:
    """
    Ask the same question to multiple providers and compare.
    All SDK calls are automatically instrumented!
    """
    results = {
        "question": question,
        "providers": {}
    }
    
    # Try OpenAI
    try:
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": question}],
                max_tokens=150
            )
            results["providers"]["openai"] = {
                "response": response.choices[0].message.content,
                "model": response.model,
                "tokens": response.usage.total_tokens
            }
        else:
            results["providers"]["openai"] = {"error": "API key not set"}
    except Exception as e:
        results["providers"]["openai"] = {"error": str(e)}
    
    # Try Anthropic
    try:
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=150,
                messages=[{"role": "user", "content": question}]
            )
            results["providers"]["anthropic"] = {
                "response": response.content[0].text,
                "model": response.model,
                "tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        else:
            results["providers"]["anthropic"] = {"error": "API key not set"}
    except Exception as e:
        results["providers"]["anthropic"] = {"error": str(e)}
    
    # Try Google
    try:
        import google.generativeai as genai
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(question)
            results["providers"]["google"] = {
                "response": response.text,
                "model": "gemini-1.5-flash",
                "tokens": getattr(response.usage_metadata, 'total_token_count', 0) if hasattr(response, 'usage_metadata') else 0
            }
        else:
            results["providers"]["google"] = {"error": "API key not set"}
    except Exception as e:
        results["providers"]["google"] = {"error": str(e)}
    
    return results


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Cross-Vendor Agent with Auto-Instrumentation")
    print("=" * 60)
    print("\nThis example calls multiple LLM providers in a single request.")
    print("All SDK calls are automatically traced!")
    print("\nServer starting on http://localhost:8003")
    print("\nSpans will be exported to: /tmp/kalibr_otel_spans.jsonl")
    print("\nTest endpoint:")
    print("  POST http://localhost:8003/proxy/compare_providers")
    print("\nExample:")
    print('  curl -X POST http://localhost:8003/proxy/compare_providers \\')
    print('       -H "Content-Type: application/json" \\')
    print('       -d \'{"question": "What is 2+2?"}\'')
    print("\n" + "=" * 60 + "\n")
    
    app.run(port=8003)
