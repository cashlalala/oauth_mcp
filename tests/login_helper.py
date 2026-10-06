import json

import requests


def login(base_url: str, username: str, *roles: str) -> requests.Session:
    """Drive the authorization code flow against mock-oauth2-server.

    The mock login page accepts a `claims` JSON field, which plays the role of the
    enqueued token callback in the Java guide.
    """
    session = requests.Session()  # keeps the client app's session cookie
    r = session.get(f"{base_url}/login")  # redirects to mock server's login page
    assert r.status_code == 200, r.text
    claims = {"preferred_username": username, "realm_access": {"roles": list(roles)}}
    # The login form posts back to the authorize URL we were redirected to.
    r = session.post(r.url, data={"username": username, "claims": json.dumps(claims)})
    assert r.status_code == 200, r.text  # followed redirects back to the client app
    return session


def login_user(base_url):
    return login(base_url, "user", "USER")


def login_admin(base_url):
    return login(base_url, "admin", "USER", "ADMIN")
