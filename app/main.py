"""Flask OAuth2 client (authorization code + PKCE) that mirrors the Spring Boot sample."""
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, jsonify, redirect, session, url_for

CLIENT_ID = "my-application-backend-client"


def roles_from_claims(claims: dict) -> set[str]:
    """Collect roles from realm_access and resource_access (like ClaimsToRolesConverter)."""
    roles = set(claims.get("realm_access", {}).get("roles", []))
    for resource in claims.get("resource_access", {}).values():
        roles.update(resource.get("roles", []))
    return {f"ROLE_{r}" for r in roles}


def create_app(issuer_uri: str) -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"

    oauth = OAuth(app)
    oauth.register(
        name="keycloak",
        client_id=CLIENT_ID,
        server_metadata_url=f"{issuer_uri}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid", "code_challenge_method": "S256"},
        token_endpoint_auth_method="none",
    )

    def require_role(role):
        def deco(fn):
            @wraps(fn)
            def wrapper(*a, **kw):
                if "user" not in session:
                    return redirect(url_for("login"))
                if f"ROLE_{role}" not in session["user"]["roles"]:
                    abort(403)
                return fn(*a, **kw)
            return wrapper
        return deco

    @app.get("/login")
    def login():
        return oauth.keycloak.authorize_redirect(url_for("callback", _external=True))

    @app.get("/login/oauth2/code/keycloak")
    def callback():
        token = oauth.keycloak.authorize_access_token()
        claims = dict(token["userinfo"])
        session["user"] = {
            "name": claims.get("preferred_username"),
            "roles": sorted(roles_from_claims(claims)),
        }
        return redirect("/")

    @app.get("/")
    @require_role("USER")
    def index():
        return jsonify(session["user"])

    @app.get("/admin")
    @require_role("ADMIN")
    def admin():
        return jsonify(session["user"])

    return app


if __name__ == "__main__":
    create_app("http://localhost:8081/issuer1").run(port=8080)
