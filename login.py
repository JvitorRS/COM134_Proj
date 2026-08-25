"""
login.py — Microsoft-only authentication logic (no username/password).

This module has NO knowledge of HTTP. It doesn't read requests, set cookies,
or send redirects. It only knows how to:
  - build a Microsoft login URL
  - exchange an auth code for tokens
  - validate token claims
  - resolve identity + role
  - manage server-side sessions

The HTTP/routing layer lives in server.py and imports from here.

Requires: pip install msal
"""

import time
import uuid
import secrets
import msal


# ---- Config -----------------------------------------------------
CLIENT_ID = "<SPI CLIENT ID>"
CLIENT_SECRET = "<SPI CLIENT SECRET>"
TENANT_ID = "<SPI TENANT ID>"           # or "common" for multi-tenant
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = "<SPI REDIRECT URI>"     # e.g. https://outlines.spi.edu/auth/callback
SCOPES = ["User.Read"]                  # minimal Graph scope to confirm identity

SESSION_LIFETIME_SECONDS = 8 * 60 * 60  # 8 hours


# ---- Base class -----------------------------------------------------
class Login:
    def __init__(self):
        self.auth_handler = MicrosoftAuthHandler()
        self.token_validator = TokenValidator()


# ---- Talks to Microsoft: builds login URL, exchanges code for tokens ----
class MicrosoftAuthHandler:
    def __init__(self):
        self.app = msal.ConfidentialClientApplication(
            CLIENT_ID,
            authority=AUTHORITY,
            client_credential=CLIENT_SECRET,
        )

    def get_login_url(self, state: str) -> str:
        return self.app.get_authorization_request_url(
            SCOPES,
            state=state,
            redirect_uri=REDIRECT_URI,
        )

    def acquire_token_by_auth_code(self, auth_code: str) -> dict:
        result = self.app.acquire_token_by_authorization_code(
            auth_code,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )
        if "error" in result:
            raise PermissionError(result.get("error_description", "Auth failed"))
        return result  # contains id_token, access_token, id_token_claims, etc.


# ---- Validates token claims and extracts identity/roles -----------------
class TokenValidator:
    def __init__(self, tenant_id: str = TENANT_ID):
        self.tenant_id = tenant_id

    def validate_claims(self, id_token_claims: dict) -> bool:
        # Signature/issuer verification is already done internally by msal
        # during acquire_token_by_authorization_code. This is an extra
        # sanity check on top of that.
        now = time.time()
        if id_token_claims.get("exp", 0) < now:
            raise PermissionError("Token expired")
        if id_token_claims.get("aud") != CLIENT_ID:
            raise PermissionError("Token audience mismatch")
        return True

    def get_email(self, id_token_claims: dict) -> str:
        return id_token_claims.get("preferred_username") or id_token_claims.get("email")

    def get_roles(self, id_token_claims: dict) -> list[str]:
        # Populated only if App Roles are configured in Azure AD for this app,
        # and the signed-in user has been assigned one.
        return id_token_claims.get("roles", [])


# ---- Verifies the person and resolves their role from the token ---------
class UserLogin(Login):
    def __init__(self):
        super().__init__()

    def login_with_code(self, auth_code: str) -> dict:
        token_result = self.auth_handler.acquire_token_by_auth_code(auth_code)
        claims = token_result["id_token_claims"]
        self.token_validator.validate_claims(claims)

        email = self.token_validator.get_email(claims)
        roles = self.token_validator.get_roles(claims)

        if not roles:
            # No App Role assigned in Azure AD = not provisioned for this app
            raise PermissionError(f"{email} has no role assigned for this system")

        return {"email": email, "roles": roles}


# ---- Role lookup, straight from token-derived user info ------------------
class UserRole(Login):
    def __init__(self, user_info: dict):
        super().__init__()
        self.user_info = user_info

    def get_role(self) -> str:
        # If a user could have multiple roles, decide precedence here
        roles = self.user_info.get("roles", [])
        return roles[0] if roles else "unknown"


# ---- Server-side session store --------------------------------------------
class SessionManager:
    """
    In-memory session store — fine for a single-process dev setup with a
    handful of staff users. For production, swap this for a DB-backed or
    Redis-backed store so sessions survive restarts and work across
    multiple processes.
    """

    _sessions: dict[str, dict] = {}

    @classmethod
    def create_session(cls, user_info: dict) -> str:
        session_id = secrets.token_urlsafe(32)
        cls._sessions[session_id] = {
            "user": user_info,
            "created_at": time.time(),
            "expires_at": time.time() + SESSION_LIFETIME_SECONDS,
        }
        return session_id

    @classmethod
    def get_session(cls, session_id: str) -> dict | None:
        session = cls._sessions.get(session_id)
        if session is None:
            return None
        if session["expires_at"] < time.time():
            cls._sessions.pop(session_id, None)
            return None
        return session

    @classmethod
    def destroy_session(cls, session_id: str):
        cls._sessions.pop(session_id, None)


# ---- Sign out --------------------------------------------------------------
class UserSignOut(Login):
    def __init__(self):
        super().__init__()

    def sign_out(self, session_id: str) -> str:
        """Clears the local session and returns Microsoft's logout URL."""
        SessionManager.destroy_session(session_id)
        return (
            f"{AUTHORITY}/oauth2/v2.0/logout"
            f"?post_logout_redirect_uri=<SPI POST LOGOUT REDIRECT URI>"
        )


# ---- CSRF protection helper for the login redirect --------------------------
class LoginStateStore:
    """
    Tracks the 'state' value issued when a login flow starts, so the
    callback can confirm the response actually corresponds to a request
    this server made — not a forged/replayed callback.
    """

    _pending_states: dict[str, float] = {}
    STATE_LIFETIME_SECONDS = 10 * 60  # 10 minutes to complete login

    @classmethod
    def issue_state(cls) -> str:
        state = str(uuid.uuid4())
        cls._pending_states[state] = time.time() + cls.STATE_LIFETIME_SECONDS
        return state

    @classmethod
    def verify_and_consume(cls, state: str) -> bool:
        expiry = cls._pending_states.pop(state, None)
        if expiry is None:
            return False
        return expiry >= time.time()
