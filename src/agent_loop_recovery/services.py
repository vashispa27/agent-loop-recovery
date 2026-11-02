"""Seeded business services served over real loopback HTTP, never production APIs."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

import httpx

ORDER_ID = "ORD-1042"
OLD_TRACKING = "TRK-OLD-1042"
NEW_TRACKING = "TRK-NEW-1042"
SCENARIOS = ("stale-label", "healthy", "carrier-delay", "unrecoverable", "order-outage")


def canonical_reference(value: str) -> str:
    return value.replace("-", "").strip().upper()


@dataclass(frozen=True)
class FixtureConfig:
    """Independent synthetic conditions; delay counts requests, not wall-clock time."""

    delay_requests: int = 0
    order_tracking: str = NEW_TRACKING
    order_id: str = ORDER_ID
    order_unavailable: bool = False
    carrier_unavailable: bool = False
    shipment_exists: bool = True

    def __post_init__(self):
        if self.delay_requests < 0:
            raise ValueError("delay_requests must be nonnegative")


@contextmanager
def fixture_services(scenario: str, *, config: FixtureConfig | None = None):
    """Bind an ephemeral port; keep fixture state isolated for every experiment."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    config = config or FixtureConfig(
        delay_requests=2 if scenario == "carrier-delay" else 0,
        order_tracking=OLD_TRACKING if scenario == "unrecoverable" else NEW_TRACKING,
        order_unavailable=scenario == "order-outage",
    )
    carrier_requests = 0

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            nonlocal carrier_requests
            path = unquote(urlparse(self.path).path)
            status = 404
            body = {"error": "resource_not_found"}
            if path == f"/orders/{ORDER_ID}":
                if config.order_unavailable:
                    status, body = 503, {"error": "order_service_unavailable"}
                else:
                    status, body = (
                        200,
                        {"order_id": config.order_id, "tracking_id": config.order_tracking},
                    )
            elif path.startswith("/carrier/shipments/"):
                carrier_requests += 1
                reference = path.rsplit("/", 1)[-1]
                valid = canonical_reference(reference) == canonical_reference(NEW_TRACKING)
                pending = carrier_requests <= config.delay_requests
                if config.carrier_unavailable:
                    status, body = 503, {"error": "service_unavailable"}
                elif valid and not pending and config.shipment_exists:
                    status, body = (
                        200,
                        {
                            "tracking_id": NEW_TRACKING,
                            "status": "in_transit",
                            "latest_event": "Arrived at destination sorting facility",
                        },
                    )
                else:
                    body = {"error": "shipment_not_found", "tracking_id": reference}
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield ServiceClient(f"http://127.0.0.1:{server.server_port}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def _get(self, path: str) -> dict:
        try:
            # Ignore proxy environment variables for this local-only demonstration.
            with httpx.Client(timeout=2, trust_env=False) as client:
                response = client.get(self.base_url + path)
                return {"http_status": response.status_code, **response.json()}
        except (httpx.HTTPError, ValueError):
            return {"http_status": 503, "error": "service_unavailable"}

    def track(self, tracking_id: str) -> dict:
        from urllib.parse import quote

        return self._get("/carrier/shipments/" + quote(tracking_id, safe=""))

    def order(self, order_id: str) -> dict:
        from urllib.parse import quote

        return self._get("/orders/" + quote(order_id, safe=""))
