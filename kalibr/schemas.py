"""Schema generation for multiple AI model ecosystems"""

import os
from typing import Any, Dict, List


def get_base_url() -> str:
    """Auto-detect base URL based on environment"""
    # Check for custom base URL
    if custom_url := os.getenv("KALIBR_BASE_URL"):
        return custom_url

    # Detect Fly.io
    if fly_app := os.getenv("FLY_APP_NAME"):
        return f"https://{fly_app}.fly.dev"

    # Detect Render
    if render_url := os.getenv("RENDER_EXTERNAL_URL"):
        return render_url

    # Default to localhost
    return "http://localhost:8000"


def generate_mcp_schema(actions: List[Dict[str, Any]], base_url: str) -> Dict[str, Any]:
    """Generate Claude MCP schema"""
    tools = []
    for action in actions:
        tool = {
            "name": action["name"],
            "description": action["description"],
            "input_schema": action["schema"],
            "server": {"url": f"{base_url}/proxy/{action['name']}"},
        }
        tools.append(tool)

    return {"mcp": "1.0", "name": "kalibr-enhanced", "tools": tools}


def generate_gemini_schema(actions: List[Dict[str, Any]], base_url: str) -> Dict[str, Any]:
    """Generate Gemini Extensions schema"""
    functions = []
    for action in actions:
        func = {
            "name": action["name"],
            "description": action["description"],
            "parameters": action["schema"],
            "server": {"url": f"{base_url}/proxy/{action['name']}"},
        }
        functions.append(func)

    return {
        "gemini_extension": "1.0",
        "name": "kalibr_enhanced",
        "description": "Enhanced Kalibr API for Gemini integration",
        "functions": functions,
    }


def generate_copilot_schema(actions: List[Dict[str, Any]], base_url: str) -> Dict[str, Any]:
    """Generate Copilot Plugins schema"""
    apis = []
    for action in actions:
        api = {
            "name": action["name"],
            "description": action["description"],
            "url": f"{base_url}/proxy/{action['name']}",
            "method": "POST",
            "request_schema": action["schema"],
            "response_schema": {"type": "object", "description": "API response"},
        }
        apis.append(api)

    return {
        "schema_version": "v1",
        "name_for_model": "kalibr_enhanced",
        "name_for_human": "Enhanced Kalibr API",
        "description_for_model": "Enhanced Kalibr API with advanced capabilities",
        "description_for_human": "API for advanced AI model integrations",
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": f"{base_url}/openapi.json"},
        "apis": apis,
    }


def get_supported_models() -> Dict[str, Any]:
    """Return list of supported AI models"""
    return {
        "supported_models": [
            {
                "name": "GPT Actions",
                "provider": "OpenAI",
                "schema_endpoint": "/gpt-actions.json",
                "format": "OpenAPI 3.1.0",
            },
            {
                "name": "Claude MCP",
                "provider": "Anthropic",
                "schema_endpoint": "/mcp.json",
                "format": "MCP 1.0",
            },
            {
                "name": "Gemini Extensions",
                "provider": "Google",
                "schema_endpoint": "/schemas/gemini",
                "format": "Gemini Extension 1.0",
            },
            {
                "name": "Copilot Plugins",
                "provider": "Microsoft",
                "schema_endpoint": "/schemas/copilot",
                "format": "Copilot Plugin v1",
            },
        ],
        "version": "1.0.28",
    }
