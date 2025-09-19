from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auth_service import create_app


@pytest.fixture()
def app(tmp_path):
    test_db = tmp_path / "test.sqlite"
    application = create_app(
        {
            "DATABASE": str(test_db),
            "SECRET_KEY": "test",
        }
    )
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def test_register_login_logout_flow(client):
    response = client.post("/auth/register", {"username": "alice", "password": "secret1"})
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["message"] == "注册成功"

    response = client.post("/auth/register", {"username": "alice", "password": "secret1"})
    assert response.status_code == 400

    response = client.post("/auth/login", {"username": "alice", "password": "wrongpass"})
    assert response.status_code == 401

    response = client.post("/auth/login", {"username": "alice", "password": "secret1"})
    assert response.status_code == 200
    assert response.get_json()["message"] == "登录成功"

    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.get_json()["username"] == "alice"

    response = client.post("/auth/logout")
    assert response.status_code == 200
    assert response.get_json()["message"] == "登出成功"

    response = client.get("/auth/me")
    assert response.status_code == 401


def test_validation_errors(client):
    response = client.post("/auth/register", {"username": "", "password": "123"})
    assert response.status_code == 400

    response = client.post("/auth/login", {})
    assert response.status_code == 400
