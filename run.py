"""Run the authentication service using Python's built-in WSGI server."""
from __future__ import annotations

from wsgiref.simple_server import make_server

from auth_service import create_app


def main() -> None:
    app = create_app()
    with make_server("127.0.0.1", 5000, app) as httpd:
        print("Serving on http://127.0.0.1:5000")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
