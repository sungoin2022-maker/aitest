"""Custom WSGI authentication application."""
from __future__ import annotations

import os
import secrets
import sqlite3
from datetime import datetime
from typing import Callable, Dict, Tuple

from .database import Database
from .http import Request, Response, TestClient, json_response
from .security import hash_password, verify_password


Handler = Callable[[Request], Response]


class AuthApplication:
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.database = Database(config["DATABASE"])
        self.secret_key = config.get("SECRET_KEY", secrets.token_hex(16))
        self.routes: Dict[Tuple[str, str], Handler] = {}
        self._register_routes()

    def _register_routes(self) -> None:
        self.add_route("GET", "/", self._healthcheck)
        self.add_route("POST", "/auth/register", self._register)
        self.add_route("POST", "/auth/login", self._login)
        self.add_route("POST", "/auth/logout", self._logout)
        self.add_route("GET", "/auth/me", self._current_user)

    def add_route(self, method: str, path: str, handler: Handler) -> None:
        self.routes[(method.upper(), path)] = handler

    def __call__(self, environ, start_response):
        request = Request.from_environ(environ)
        handler = self.routes.get((request.method, request.path))
        if handler is None:
            response = json_response({"error": "未找到接口"}, status=404)
        else:
            try:
                response = handler(request)
            except ValueError as exc:
                response = json_response({"error": str(exc)}, status=400)
            except Exception:
                response = json_response({"error": "服务器内部错误"}, status=500)
        status_line, headers, body_iter = response.to_wsgi()
        start_response(status_line, headers)
        return body_iter

    # Public helpers -----------------------------------------------------
    def test_client(self) -> TestClient:
        return TestClient(self)

    # Route handlers -----------------------------------------------------
    def _healthcheck(self, request: Request) -> Response:
        return json_response({"status": "ok"})

    def _register(self, request: Request) -> Response:
        payload = request.json()
        username, password = self._validate_credentials(payload)
        password_hash = hash_password(password)
        with self.database.connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO user (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
            except sqlite3.IntegrityError:
                return json_response({"error": "用户名已存在"}, status=400)
        return json_response({"message": "注册成功", "username": username}, status=201)

    def _login(self, request: Request) -> Response:
        payload = request.json()
        username, password = self._validate_credentials(payload)
        with self.database.connection() as conn:
            user = conn.execute(
                "SELECT id, username, password_hash FROM user WHERE username = ?",
                (username,),
            ).fetchone()
            if user is None or not verify_password(user["password_hash"], password):
                return json_response({"error": "用户名或密码错误"}, status=401)
            token = secrets.token_hex(32)
            conn.execute(
                "INSERT OR REPLACE INTO session (token, user_id) VALUES (?, ?)",
                (token, user["id"]),
            )
        response = json_response({"message": "登录成功", "username": username})
        response.add_header("Set-Cookie", f"session={token}; Path=/; HttpOnly")
        return response

    def _logout(self, request: Request) -> Response:
        token = request.cookies.get("session")
        if token:
            with self.database.connection() as conn:
                conn.execute("DELETE FROM session WHERE token = ?", (token,))
        response = json_response({"message": "登出成功"})
        response.add_header("Set-Cookie", "session=; Path=/; Max-Age=0")
        return response

    def _current_user(self, request: Request) -> Response:
        user = self._load_user_from_request(request)
        if user is None:
            return json_response({"error": "未登录"}, status=401)
        created_at = user["created_at"]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        return json_response(
            {
                "id": user["id"],
                "username": user["username"],
                "created_at": created_at,
            }
        )

    # Helpers ------------------------------------------------------------
    def _validate_credentials(self, payload: Dict[str, str]) -> tuple[str, str]:
        raw_username = payload.get("username")
        if raw_username is None:
            username = ""
        elif isinstance(raw_username, str):
            username = raw_username.strip()
        else:
            raise ValueError("用户名必须为字符串")

        raw_password = payload.get("password")
        if raw_password is None:
            password = ""
        elif isinstance(raw_password, str):
            password = raw_password
        else:
            raise ValueError("密码必须为字符串")
        if not username:
            raise ValueError("用户名不能为空")
        if len(password) < 6:
            raise ValueError("密码长度至少为6位")
        return username, password

    def _load_user_from_request(self, request: Request):
        token = request.cookies.get("session")
        if not token:
            return None
        with self.database.connection() as conn:
            row = conn.execute(
                """
                SELECT user.id, user.username, user.created_at
                FROM session JOIN user ON session.user_id = user.id
                WHERE session.token = ?
                """,
                (token,),
            ).fetchone()
        return row


def create_app(test_config: Dict[str, str] | None = None) -> AuthApplication:
    base_path = os.path.join(os.getcwd(), "instance")
    os.makedirs(base_path, exist_ok=True)
    config = {
        "DATABASE": os.path.join(base_path, "auth.sqlite"),
        "SECRET_KEY": "dev-secret-key",
    }
    if test_config:
        config.update(test_config)
    return AuthApplication(config)
