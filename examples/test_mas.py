"""
Test Multi-Agent System (MAS) with Kalibr Observability

This example demonstrates:
1. Multi-agent workflow with parent-child trace relationships
2. Auto-instrumentation across OpenAI, Anthropic, and Google
3. Proper trace propagation and observability
4. Environment-based configuration

Agents:
- Researcher: Uses OpenAI to gather information
- Writer: Uses Anthropic Claude to draft content
- Analyzer: Uses Google Gemini to analyze and summarize

Usage:
    export KALIBR_API_KEY=your-kalibr-api-key
    export KALIBR_COLLECTOR_URL=http://localhost:8000/api/v1/traces
    export KALIBR_TENANT_ID=acme-prod
    export OPENAI_API_KEY=<your-key>
    export ANTHROPIC_API_KEY=<your-key>
    export GOOGLE_API_KEY=<your-key>
    
    python3 test_mas.py --skip-env-check
"""

import argparse
import os
import sys
import time
from typing import Dict, Any


def check_environment():
    """Check that all required environment variables are set."""
    required_vars = {
        "KALIBR_API_KEY": "Kalibr API key for authentication",
        "KALIBR_COLLECTOR_URL": "Collector endpoint URL",
        "KALIBR_TENANT_ID": "Tenant identifier",
        "OPENAI_API_KEY": "OpenAI API key",
        "ANTHROPIC_API_KEY": "Anthropic API key",
        "GOOGLE_API_KEY": "Google API key (optional)",
    }
    
    missing = []
    for var, description in required_vars.items():
        if not os.getenv(var) and var != "GOOGLE_API_KEY":
            missing.append(f"  - {var}: {description}")
    
    if missing:
        print("❌ Missing required environment variables:")
        print("\n".join(missing))
        print("\nSet these variables before running test_mas.py")
        return False
    
    return True


def research_agent(topic: str) -> Dict[str, Any]:
    """
    Researcher Agent: Uses OpenAI to gather information
    
    This agent is automatically instrumented by Kalibr.
    """
    print(f"\n🔍 Researcher Agent: Gathering information about '{topic}'...")
    
    try:
        import openai
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"error": "OPENAI_API_KEY not set", "research": None}
        
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a research assistant. Provide concise, factual information."},
                {"role": "user", "content": f"Provide 3 key facts about: {topic}"}
            ],
            max_tokens=200
        )
        
        research = response.choices[0].message.content
        print(f"✅ Research completed: {len(research)} chars")
        
        return {
            "agent": "researcher",
            "model": "gpt-4o-mini",
            "research": research,
            "tokens": response.usage.total_tokens,
            "status": "success"
        }
        
    except Exception as e:
        print(f"❌ Research agent error: {e}")
        return {"agent": "researcher", "error": str(e), "status": "failed"}


def writer_agent(research_data: str) -> Dict[str, Any]:
    """
    Writer Agent: Uses Anthropic Claude to draft content
    
    This agent is automatically instrumented by Kalibr.
    """
    print(f"\n✍️  Writer Agent: Drafting content based on research...")
    
    try:
        import anthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return {"error": "ANTHROPIC_API_KEY not set", "draft": None}
        
        client = anthropic.Anthropic(api_key=api_key)
        
        # Use the correct Claude Sonnet 4 model identifier
        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # ✅ Fixed: Using Claude Sonnet 4
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": f"Based on this research, write a brief summary:\n\n{research_data}"
                }
            ]
        )
        
        draft = response.content[0].text
        print(f"✅ Draft completed: {len(draft)} chars")
        
        return {
            "agent": "writer",
            "model": "claude-sonnet-4-20250514",
            "draft": draft,
            "tokens": response.usage.input_tokens + response.usage.output_tokens,
            "status": "success"
        }
        
    except Exception as e:
        print(f"❌ Writer agent error: {e}")
        return {"agent": "writer", "error": str(e), "status": "failed"}


def analyzer_agent(draft: str, research: str) -> Dict[str, Any]:
    """
    Analyzer Agent: Uses Google Gemini to analyze and summarize
    
    This agent is automatically instrumented by Kalibr.
    """
    print(f"\n📊 Analyzer Agent: Analyzing content quality...")
    
    try:
        import google.generativeai as genai
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("⚠️  GOOGLE_API_KEY not set, skipping analyzer")
            return {"agent": "analyzer", "status": "skipped", "reason": "No API key"}
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""Analyze the following draft and provide a quality score (1-10):

Research: {research}

Draft: {draft}

Provide: 1) Quality score, 2) Strengths, 3) Suggestions"""
        
        response = model.generate_content(prompt)
        analysis = response.text
        print(f"✅ Analysis completed: {len(analysis)} chars")
        
        return {
            "agent": "analyzer",
            "model": "gemini-1.5-flash",
            "analysis": analysis,
            "tokens": getattr(response.usage_metadata, 'total_token_count', 0) if hasattr(response, 'usage_metadata') else 0,
            "status": "success"
        }
        
    except Exception as e:
        print(f"❌ Analyzer agent error: {e}")
        return {"agent": "analyzer", "error": str(e), "status": "failed"}


def run_multi_agent_workflow(topic: str = "Artificial Intelligence in Healthcare"):
    """
    Run the complete multi-agent workflow.
    
    This orchestrates three agents in sequence:
    1. Researcher (OpenAI)
    2. Writer (Anthropic)
    3. Analyzer (Google)
    
    All LLM calls are automatically instrumented by Kalibr.
    """
    print("\n" + "=" * 70)
    print(f"🚀 Starting Multi-Agent Workflow: '{topic}'")
    print("=" * 70)
    
    start_time = time.time()
    
    # Step 1: Research
    research_result = research_agent(topic)
    
    if research_result.get("status") != "success":
        print("\n❌ Workflow failed at research stage")
        return {
            "status": "failed",
            "stage": "research",
            "error": research_result.get("error")
        }
    
    # Step 2: Write
    writer_result = writer_agent(research_result["research"])
    
    if writer_result.get("status") != "success":
        print("\n❌ Workflow failed at writing stage")
        return {
            "status": "failed",
            "stage": "writing",
            "error": writer_result.get("error")
        }
    
    # Step 3: Analyze
    analyzer_result = analyzer_agent(
        draft=writer_result["draft"],
        research=research_result["research"]
    )
    
    # Calculate total stats
    elapsed = time.time() - start_time
    total_tokens = (
        research_result.get("tokens", 0) +
        writer_result.get("tokens", 0) +
        analyzer_result.get("tokens", 0)
    )
    
    print("\n" + "=" * 70)
    print("✅ Multi-Agent Workflow Completed Successfully!")
    print("=" * 70)
    print(f"⏱️  Total time: {elapsed:.2f}s")
    print(f"🎯 Total tokens: {total_tokens}")
    print(f"📊 Agents executed: 3")
    print(f"   - Researcher: {research_result.get('status')}")
    print(f"   - Writer: {writer_result.get('status')}")
    print(f"   - Analyzer: {analyzer_result.get('status')}")
    
    return {
        "status": "success",
        "elapsed_time": elapsed,
        "total_tokens": total_tokens,
        "research": research_result,
        "writer": writer_result,
        "analyzer": analyzer_result
    }


def main():
    """Main entry point for test_mas.py"""
    parser = argparse.ArgumentParser(description="Test Multi-Agent System with Kalibr")
    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="Skip environment variable validation"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="Artificial Intelligence in Healthcare",
        help="Topic for the multi-agent workflow"
    )
    
    args = parser.parse_args()
    
    # Check environment
    if not args.skip_env_check:
        if not check_environment():
            sys.exit(1)
    
    print("\n🔧 Kalibr Configuration:")
    print(f"   API Key: {os.getenv('KALIBR_API_KEY', 'Not set')[:20]}...")
    print(f"   Collector: {os.getenv('KALIBR_COLLECTOR_URL', 'Not set')}")
    print(f"   Tenant ID: {os.getenv('KALIBR_TENANT_ID', 'Not set')}")
    
    # Run workflow
    result = run_multi_agent_workflow(topic=args.topic)
    
    if result["status"] == "success":
        print("\n✅ Test MAS completed successfully!")
        print("\n📝 Check traces in ClickHouse:")
        print("   SELECT COUNT(*) FROM kalibr.traces WHERE tenant_id = 'acme-prod'")
        sys.exit(0)
    else:
        print(f"\n❌ Test MAS failed at {result.get('stage')} stage")
        sys.exit(1)


if __name__ == "__main__":
    main()
