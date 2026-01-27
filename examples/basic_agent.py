"""
Basic Agent Example with Auto-Instrumentation

This example demonstrates:
1. Zero-config LLM SDK tracing
2. OpenTelemetry span emission
3. Cost and latency tracking
4. File export of traces

Note: Requires API keys to actually make LLM calls.
Set environment variables:
- OPENAI_API_KEY for OpenAI
- ANTHROPIC_API_KEY for Anthropic
- GOOGLE_API_KEY for Google
"""

import os
from kalibr import Kalibr

# Create Kalibr app
app = Kalibr(title="Basic Agent", description="Demo of auto-instrumentation")


@app.action("chat_with_openai", "Chat using OpenAI")
def chat_with_openai(message: str) -> dict:
    """
    This action calls OpenAI's API.
    The SDK call is automatically traced!
    """
    try:
        import openai
        
        # Check if API key is available
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {
                "error": "OPENAI_API_KEY not set",
                "message": "This is a mock response. Set OPENAI_API_KEY to test real calls."
            }
        
        # This call is automatically instrumented!
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": message}
            ],
            max_tokens=100
        )
        
        return {
            "response": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
    except Exception as e:
        return {"error": str(e)}


@app.action("chat_with_anthropic", "Chat using Anthropic Claude")
def chat_with_anthropic(message: str) -> dict:
    """
    This action calls Anthropic's API.
    The SDK call is automatically traced!
    """
    try:
        import anthropic
        
        # Check if API key is available
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return {
                "error": "ANTHROPIC_API_KEY not set",
                "message": "This is a mock response. Set ANTHROPIC_API_KEY to test real calls."
            }
        
        # This call is automatically instrumented!
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": message}]
        )
        
        return {
            "response": response.content[0].text,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }
    except Exception as e:
        return {"error": str(e)}


@app.action("chat_with_google", "Chat using Google Gemini")
def chat_with_google(message: str) -> dict:
    """
    This action calls Google's Generative AI API.
    The SDK call is automatically traced!
    """
    try:
        import google.generativeai as genai
        
        # Check if API key is available
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return {
                "error": "GOOGLE_API_KEY not set",
                "message": "This is a mock response. Set GOOGLE_API_KEY to test real calls."
            }
        
        # This call is automatically instrumented!
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(message)
        
        return {
            "response": response.text,
            "model": "gemini-1.5-flash",
            "usage": {
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count
            } if hasattr(response, 'usage_metadata') else {}
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Starting Basic Agent with Auto-Instrumentation")
    print("=" * 60)
    print("\nServer starting on http://localhost:8002")
    print("\nSpans will be exported to: /tmp/kalibr_otel_spans.jsonl")
    print("\nTest endpoints:")
    print("  POST http://localhost:8002/proxy/chat_with_openai")
    print("  POST http://localhost:8002/proxy/chat_with_anthropic")
    print("  POST http://localhost:8002/proxy/chat_with_google")
    print("\nExample:")
    print('  curl -X POST http://localhost:8002/proxy/chat_with_openai \\')
    print('       -H "Content-Type: application/json" \\')
    print('       -d \'{"message": "Hello, world!"}\'')
    print("\n" + "=" * 60 + "\n")
    
    app.run(port=8002)
