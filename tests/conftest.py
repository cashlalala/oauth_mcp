import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import requests
from werkzeug.serving import make_server

from app.main import create_app

ROOT = Path(__file__).resolve().parent.parent
MOCK_BASE = "http://localhost:8081"
ISSUER = f"{MOCK_BASE}/issuer1"


def _wait_for(url: str, retries: int = 10):
    for i in range(retries):
        try:
            if requests.get(url, timeout=2).ok:
                return
        except requests.RequestException:
            pass
        time.sleep(min(2 ** i * 0.1, 2))
    raise RuntimeError(f"{url} not reachable")


@pytest.fixture(scope="session")
def mock_oauth2_server():
    # Reuse an already running server, otherwise start one via docker compose.
    started = False
    try:
        requests.get(f"{ISSUER}/.well-known/openid-configuration", timeout=1)
    except requests.RequestException:
        subprocess.run(["docker", "compose", "up", "-d"], cwd=ROOT, check=True)
        started = True
    _wait_for(f"{ISSUER}/.well-known/openid-configuration", 30)
    yield ISSUER
    if started:
        subprocess.run(["docker", "compose", "down"], cwd=ROOT, check=True)


@pytest.fixture(scope="session")
def live_server(mock_oauth2_server):
    """The client app must run for real: the OAuth2 redirects need a reachable port."""
    with socket.socket() as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
    server = make_server("localhost", port, create_app(mock_oauth2_server))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://localhost:{port}"
    server.shutdown()
