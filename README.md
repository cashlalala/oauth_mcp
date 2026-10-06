# OAuth2 client testing with mock-oauth2-server (Python)

Python port of https://www.wimdeblauwe.com/blog/2026/07/07/testing-oauth2-client-login-with-mock-oauth2-server/

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    pytest

Tests start the mock server with `docker compose up -d` if it isn't already running on :8081.
