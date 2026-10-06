import requests

from tests.login_helper import login_admin, login_user


def test_not_logged_in_redirects(live_server):
    r = requests.get(f"{live_server}/", allow_redirects=False)
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/login")


def test_logged_in(live_server):
    s = login_user(live_server)
    r = s.get(f"{live_server}/")
    assert r.status_code == 200
    assert r.json() == {"name": "user", "roles": ["ROLE_USER"]}


def test_user_cannot_access_admin(live_server):
    s = login_user(live_server)
    assert s.get(f"{live_server}/admin").status_code == 403


def test_admin_access(live_server):
    s = login_admin(live_server)
    r = s.get(f"{live_server}/admin")
    assert r.status_code == 200
    assert "ROLE_ADMIN" in r.json()["roles"]
