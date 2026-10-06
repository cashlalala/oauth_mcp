# Result Summary

Python port of [Testing OAuth2 Client Login with mock-oauth2-server](https://www.wimdeblauwe.com/blog/2026/07/07/testing-oauth2-client-login-with-mock-oauth2-server/). The original is Spring Boot/Java; this version uses a Flask client and pytest.

**Status:** 4 tests pass (`pytest`, ~36 s).

## Layout

| File | Purpose |
|---|---|
| `compose.yaml` | Runs `ghcr.io/navikt/mock-oauth2-server:5.0.2` on port 8081 |
| `app/main.py` | Flask OAuth2 client (Authlib, authorization code + PKCE S256), role checks |
| `tests/conftest.py` | Fixtures: start/reuse mock server, run the client app on a free port |
| `tests/login_helper.py` | `login()`, `login_user()`, `login_admin()` |
| `tests/test_login.py` | The four tests |
| `requirements.txt`, `.venv/` | Dependencies and virtualenv |

## Mapping from the guide

| Guide (Java) | Here (Python) |
|---|---|
| Spring Security OAuth2 client | Flask + Authlib, issuer `http://localhost:8081/issuer1` |
| `ClaimsToRolesConverter` | `roles_from_claims()` (`realm_access` + `resource_access`, `ROLE_` prefix) |
| `MockOAuth2ServerInitializer` | Session fixtures in `conftest.py` |
| `MockOAuth2ServerLogin` | `tests/login_helper.py` |
| `WebEnvironment.RANDOM_PORT` | Flask served on a random port in a background thread |

## Tests

- Unauthenticated request to `/` returns 302 to `/login`.
- Logged-in user gets 200 on `/` with `{"name": "user", "roles": ["ROLE_USER"]}`.
- User gets 403 on `/admin`.
- Admin gets 200 on `/admin`.

## Notes

- **Token claims:** Python can't enqueue a token callback like the Java API. The helper posts a `claims` JSON field to the mock server's login form instead.
- **Real server needed:** the OAuth2 redirects require a reachable client port, so the app runs live during tests.
- **Docker:** tests run `docker compose up -d` if nothing listens on :8081, and `down` afterwards.
- **Image tag:** Pinned to `5.0.2`, the version used in the guide.

## Run

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest
```
