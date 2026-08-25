"""
server.py — HTTP routing layer only.

Knows about requests, cookies, and redirects. Contains NO auth logic —
everything auth-related is delegated to login.py.

Dev-only server. In production, run behind a real WSGI/ASGI server and
terminate TLS at a reverse proxy (nginx, etc.), and serve everything
over HTTPS — never plain HTTP.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from login import (
    MicrosoftAuthHandler,
    UserLogin,
    UserSignOut,
    SessionManager,
    LoginStateStore,
)

HOST = "localhost"
PORT = 8000

# Set to True only when actually served over HTTPS.
# Must be True in production — Secure cookies are never sent over plain HTTP.
COOKIES_SECURE = False


def _session_id_from_cookie(cookie_header: str | None) -> str | None:
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        if "=" in part:
            key, value = part.strip().split("=", 1)
            if key == "session_id":
                return value
    return None


def _session_cookie_header(session_id: str) -> str:
    flags = "HttpOnly; Path=/; SameSite=Lax"
    if COOKIES_SECURE:
        flags += "; Secure"
    return f"session_id={session_id}; {flags}"


def _clear_cookie_header() -> str:
    flags = "HttpOnly; Path=/; SameSite=Lax; Max-Age=0"
    if COOKIES_SECURE:
        flags += "; Secure"
    return f"session_id=; {flags}"


class AuthRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/login":
            self._handle_login()
        elif parsed.path == "/auth/callback":
            self._handle_callback(parsed)
        elif parsed.path == "/logout":
            self._handle_logout()
        elif parsed.path == "/":
            self._handle_home()
        else:
            self.send_response(404)
            self.end_headers()

    # ---- route handlers --------------------------------------------

    def _handle_login(self):
        state = LoginStateStore.issue_state()
        login_url = MicrosoftAuthHandler().get_login_url(state)
        self.send_response(302)
        self.send_header("Location", login_url)
        self.end_headers()

    def _handle_callback(self, parsed):
        params = parse_qs(parsed.query)
        auth_code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        if not state or not LoginStateStore.verify_and_consume(state):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid or expired login attempt. Please try again.")
            return

        if not auth_code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing auth code")
            return

        try:
            user_info = UserLogin().login_with_code(auth_code)
            session_id = SessionManager.create_session(user_info)

            self.send_response(302)
            self.send_header("Set-Cookie", _session_cookie_header(session_id))
            self.send_header("Location", "/")
            self.end_headers()
        except PermissionError as e:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def _handle_logout(self):
        session_id = _session_id_from_cookie(self.headers.get("Cookie"))
        if not session_id:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        microsoft_logout_url = UserSignOut().sign_out(session_id)

        self.send_response(302)
        self.send_header("Set-Cookie", _clear_cookie_header())
        self.send_header("Location", microsoft_logout_url)
        self.end_headers()

    def _handle_home(self):
        session_id = _session_id_from_cookie(self.headers.get("Cookie"))
        session = SessionManager.get_session(session_id) if session_id else None

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

        if session:
            email = session["user"]["email"]
            self.wfile.write(f"Logged in as {email}. Go to /logout to sign out.".encode())
        else:
            self.wfile.write(b"Not logged in. Go to /login to sign in with Microsoft.")


def run():
    server = HTTPServer((HOST, PORT), AuthRequestHandler)
    print(f"Listening on http://{HOST}:{PORT} — go to /login to start")
    server.serve_forever()
