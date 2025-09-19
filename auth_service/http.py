"""Minimal HTTP utilities for the custom WSGI application."""
from __future__ import annotations

import io
import json
import sys
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Tuple


@dataclass
class Request:
    method: str
    path: str
    headers: Dict[str, str]
    body: bytes
    cookies: Dict[str, str]

    @classmethod
    def from_environ(cls, environ: dict) -> "Request":
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")
        headers = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-").title()
                headers[header_name] = value
        if "CONTENT_TYPE" in environ:
            headers["Content-Type"] = environ["CONTENT_TYPE"]
        if "CONTENT_LENGTH" in environ and environ["CONTENT_LENGTH"]:
            headers["Content-Length"] = environ["CONTENT_LENGTH"]
        length = int(environ.get("CONTENT_LENGTH") or 0)
        body = environ["wsgi.input"].read(length) if length > 0 else b""
        cookies = parse_cookies(headers.get("Cookie", ""))
        return cls(method, path, headers, body, cookies)

    def json(self) -> dict:
        if not self.body:
            return {}
        try:
            return json.loads(self.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON payload") from exc


def parse_cookies(cookie_header: str) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    if not cookie_header:
        return cookies
    parts = [part.strip() for part in cookie_header.split(";") if part.strip()]
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key] = value
    return cookies


@dataclass
class Response:
    status: int
    headers: List[Tuple[str, str]]
    body: bytes

    def add_header(self, name: str, value: str) -> None:
        self.headers.append((name, value))

    def to_wsgi(self) -> Tuple[str, List[Tuple[str, str]], Iterable[bytes]]:
        status_line = f"{self.status} {HTTP_STATUS_MESSAGES.get(self.status, 'OK')}"
        return status_line, self.headers, [self.body]

    def get_json(self) -> dict:
        return json.loads(self.body.decode("utf-8"))


HTTP_STATUS_MESSAGES = {
    200: "OK",
    201: "Created",
    400: "Bad Request",
    401: "Unauthorized",
    404: "Not Found",
    405: "Method Not Allowed",
    500: "Internal Server Error",
}


def json_response(payload: dict, status: int = 200) -> Response:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [("Content-Type", "application/json; charset=utf-8")]
    return Response(status=status, headers=headers, body=body)


class TestClient:
    """A tiny WSGI test client that supports cookies and JSON payloads."""

    def __init__(self, app: Callable):
        self.app = app
        self.cookies: Dict[str, str] = {}

    def _build_environ(self, method: str, path: str, body: bytes, content_type: str | None) -> dict:
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "80",
            "wsgi.version": (1, 0),
            "wsgi.input": io.BytesIO(body),
            "wsgi.errors": sys.stderr,
            "wsgi.multithread": False,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            "wsgi.url_scheme": "http",
            "CONTENT_LENGTH": str(len(body)) if body else "0",
        }
        if content_type:
            environ["CONTENT_TYPE"] = content_type
        if self.cookies:
            cookie_header = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
            environ["HTTP_COOKIE"] = cookie_header
        return environ

    def _handle_response(self, status: str, headers: List[Tuple[str, str]], body_chunks: Iterable[bytes]):
        status_code = int(status.split()[0])
        body = b"".join(body_chunks)
        for name, value in headers:
            if name.lower() == "set-cookie":
                cookie_pair = value.split(";", 1)[0]
                key, cookie_value = cookie_pair.split("=", 1)
                if cookie_value == "":
                    self.cookies.pop(key, None)
                else:
                    self.cookies[key] = cookie_value
        return TestResponse(status_code, headers, body)

    def request(self, method: str, path: str, json_payload: dict | None = None) -> "TestResponse":
        body = b""
        content_type = None
        if json_payload is not None:
            body = json.dumps(json_payload).encode("utf-8")
            content_type = "application/json"
        environ = self._build_environ(method, path, body, content_type)
        status_headers: Dict[str, List[Tuple[str, str]] | str] = {}

        def start_response(status: str, headers: List[Tuple[str, str]]):
            status_headers["status"] = status
            status_headers["headers"] = headers

        body_iter = self.app(environ, start_response)
        return self._handle_response(
            status_headers["status"],
            status_headers["headers"],
            body_iter,
        )

    def get(self, path: str) -> "TestResponse":
        return self.request("GET", path)

    def post(self, path: str, json_payload: dict | None = None) -> "TestResponse":
        return self.request("POST", path, json_payload)


@dataclass
class TestResponse:
    status_code: int
    headers: List[Tuple[str, str]]
    data: bytes

    def get_json(self) -> dict:
        return json.loads(self.data.decode("utf-8"))
