"""Kalibr - Simple function-level API builder"""

import inspect
import os
from typing import Any, Callable, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from kalibr.middleware.auto_tracer import AutoTracerMiddleware
from kalibr.schemas import (
    generate_copilot_schema,
    generate_gemini_schema,
    generate_mcp_schema,
    get_base_url,
    get_supported_models,
)
from pydantic import BaseModel, create_model


class Kalibr:
    """Simple function-level API builder for multi-model integration"""

    def __init__(
        self,
        title: str = "Kalibr API",
        version: str = "1.0.0",
        auto_trace: bool = True,
        agent_name: str = None,
    ):
        self.app = FastAPI(title=title, version=version)
        self.actions: List[Dict[str, Any]] = []
        self.base_url = get_base_url()
        self.agent_name = agent_name or title

        # Phase 3B: Auto-attach tracing middleware
        if auto_trace and os.getenv("KALIBR_TRACE_ENABLED", "true").lower() == "true":
            self.app.add_middleware(
                AutoTracerMiddleware,
                agent_name=self.agent_name,
            )

        self._setup_routes()

    def action(self, name: str, description: str = ""):
        """Decorator to register a function as an action"""

        def decorator(func: Callable):
            # Extract function signature
            sig = inspect.signature(func)
            schema = self._generate_schema(sig)

            # Store action metadata
            self.actions.append(
                {
                    "name": name,
                    "description": description or func.__doc__ or "",
                    "function": func,
                    "schema": schema,
                }
            )

            # Register proxy endpoint
            self._register_proxy_endpoint(name, func, schema)

            return func

        return decorator

    def _generate_schema(self, sig: inspect.Signature) -> Dict[str, Any]:
        """Generate JSON schema from function signature"""
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            param_type = "string"  # Default type

            # Map Python types to JSON schema types
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
                elif param.annotation == dict:
                    param_type = "object"

            properties[param_name] = {"type": param_type}

            # Check if parameter is required (no default value)
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        return {"type": "object", "properties": properties, "required": required}

    def _register_proxy_endpoint(self, name: str, func: Callable, schema: Dict[str, Any]):
        """Register a proxy endpoint for the action"""
        # Create Pydantic model for request validation
        fields = {}
        for prop_name, prop_schema in schema["properties"].items():
            field_type = str  # Default
            if prop_schema["type"] == "integer":
                field_type = int
            elif prop_schema["type"] == "number":
                field_type = float
            elif prop_schema["type"] == "boolean":
                field_type = bool

            # Check if required
            if prop_name in schema.get("required", []):
                fields[prop_name] = (field_type, ...)
            else:
                fields[prop_name] = (Optional[field_type], None)

        RequestModel = create_model(f"{name}_Request", **fields)

        @self.app.post(f"/proxy/{name}")
        async def proxy_endpoint(request: RequestModel):
            try:
                result = func(**request.dict(exclude_none=True))
                return result
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})

    def _setup_routes(self):
        """Setup built-in routes"""

        @self.app.get("/")
        async def root():
            return {
                "message": "Kalibr API is running",
                "actions": [action["name"] for action in self.actions],
                "schemas": {
                    "gpt_actions": f"{self.base_url}/gpt-actions.json",
                    "openapi_swagger": f"{self.base_url}/openapi.json",
                    "claude_mcp": f"{self.base_url}/mcp.json",
                    "gemini": f"{self.base_url}/schemas/gemini",
                    "copilot": f"{self.base_url}/schemas/copilot",
                },
            }

        @self.app.get("/gpt-actions.json")
        async def gpt_actions_schema():
            """Generates OpenAPI 3.0 schema for GPT Actions integration.
            (Alternative endpoint since /openapi.json is used by FastAPI)"""
            return self.app.openapi()

        @self.app.get("/mcp.json")
        async def mcp_schema():
            return generate_mcp_schema(self.actions, self.base_url)

        @self.app.get("/schemas/gemini")
        async def gemini_schema():
            return generate_gemini_schema(self.actions, self.base_url)

        @self.app.get("/schemas/copilot")
        async def copilot_schema():
            return generate_copilot_schema(self.actions, self.base_url)

        @self.app.get("/models/supported")
        async def models_supported():
            return get_supported_models()

    def get_app(self) -> FastAPI:
        """Get the FastAPI app instance"""
        return self.app

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the Kalibr server"""
        uvicorn.run(self.app, host=host, port=port)
