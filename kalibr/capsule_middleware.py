"""
Kalibr Capsule Middleware for FastAPI.

Automatically extracts, propagates, and injects trace capsules in HTTP requests.

Usage in FastAPI app:
    from kalibr.capsule_middleware import add_capsule_middleware

    app = FastAPI()
    add_capsule_middleware(app)

    # Now all requests have request.state.capsule available
    @app.get("/")
    def endpoint(request: Request):
        capsule = request.state.capsule
        # Use capsule...
"""

import logging

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .trace_capsule import TraceCapsule, get_or_create_capsule

logger = logging.getLogger(__name__)

CAPSULE_HEADER = "X-Kalibr-Capsule"


class CapsuleMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts and propagates Kalibr trace capsules.

    This middleware:
    1. Extracts capsule from incoming X-Kalibr-Capsule header
    2. Attaches capsule to request.state for access in endpoints
    3. Automatically injects updated capsule in response headers
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and response with capsule handling.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain

        Returns:
            Response with X-Kalibr-Capsule header attached
        """
        # Extract capsule from header (or create new one)
        capsule_header = request.headers.get(CAPSULE_HEADER)

        if capsule_header:
            capsule = TraceCapsule.from_json(capsule_header)
            logger.debug(f"📦 Received capsule: {capsule}")
        else:
            capsule = TraceCapsule()
            logger.debug(f"📦 Created new capsule: {capsule.trace_id}")

        # Attach capsule to request state
        request.state.capsule = capsule

        # Process request
        response = await call_next(request)

        # Inject updated capsule in response headers
        try:
            capsule_json = capsule.to_json()
            response.headers[CAPSULE_HEADER] = capsule_json
            logger.debug(f"📦 Sending capsule: {capsule}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to serialize capsule: {e}")

        return response


def add_capsule_middleware(app: FastAPI) -> None:
    """Add capsule middleware to FastAPI application.

    Args:
        app: FastAPI application instance

    Example:
        app = FastAPI()
        add_capsule_middleware(app)
    """
    app.add_middleware(CapsuleMiddleware)
    logger.info("✅ Kalibr Capsule middleware added")


def get_capsule(request: Request) -> TraceCapsule:
    """Get capsule from request state (convenience function).

    Args:
        request: FastAPI Request object

    Returns:
        TraceCapsule attached to request

    Raises:
        AttributeError: If middleware not installed
    """
    if not hasattr(request.state, "capsule"):
        logger.warning("⚠️ Capsule middleware not installed, creating new capsule")
        request.state.capsule = TraceCapsule()

    return request.state.capsule
