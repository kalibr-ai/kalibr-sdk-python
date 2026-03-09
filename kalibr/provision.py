"""Auto-exchange a provisioning token for an API key."""

import os
import socket
import threading
from typing import Optional, Tuple

import requests

_lock = threading.Lock()
_cached_api_key: Optional[str] = None
_cached_tenant_id: Optional[str] = None

PROVISION_URL = "https://kalibr-backend.fly.dev/api/provisioning/provision"


def resolve_credentials(
    api_key: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve API key and tenant ID.

    Priority: explicit args > env vars > provisioning token exchange.

    Returns (api_key, tenant_id).
    """
    global _cached_api_key, _cached_tenant_id

    resolved_key = api_key or os.getenv("KALIBR_API_KEY")
    resolved_tenant = tenant_id or os.getenv("KALIBR_TENANT_ID")

    if resolved_key:
        return resolved_key, resolved_tenant

    prov_token = os.getenv("KALIBR_PROVISIONING_TOKEN")
    if not prov_token:
        return None, resolved_tenant

    # Use cached result if already exchanged this process lifetime
    with _lock:
        if _cached_api_key:
            return _cached_api_key, _cached_tenant_id

        try:
            name = os.getenv("KALIBR_AGENT_NAME") or socket.gethostname()
            response = requests.post(
                PROVISION_URL,
                json={
                    "provisioning_token": prov_token,
                    "name": name,
                    "source": "sdk-auto",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            _cached_api_key = data["api_key"]
            _cached_tenant_id = data.get("tenant_id", resolved_tenant)

            # Also set env vars so other SDK components pick them up
            os.environ["KALIBR_API_KEY"] = _cached_api_key
            if _cached_tenant_id:
                os.environ["KALIBR_TENANT_ID"] = _cached_tenant_id

            print(f"[Kalibr SDK] Provisioned API key via token (tenant: {_cached_tenant_id})")
            return _cached_api_key, _cached_tenant_id

        except Exception as e:
            print(f"[Kalibr SDK] Failed to exchange provisioning token: {e}")
            return None, resolved_tenant
