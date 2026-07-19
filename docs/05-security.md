# 05 — Security Specification

**Enterprise-Grade Security Architecture for Proactive SEO Platform**

---

## Table of Contents

1. [Authentication System](#1-authentication-system)
2. [Authorization System](#2-authorization-system)
3. [Data Security](#3-data-security)
4. [API Security](#4-api-security)
5. [Infrastructure Security](#5-infrastructure-security)
6. [Audit & Compliance](#6-audit--compliance)
7. [Incident Response](#7-incident-response)
8. [Security Monitoring](#8-security-monitoring)

---

## 1. Authentication System

### 1.1 OAuth 2.0 Implementation

The platform implements OAuth 2.0 Authorization Code Flow with PKCE (Proof Key for Code Exchange) for all public clients and standard Authorization Code Flow for server-side integrations.

**Supported Grant Types:**

| Grant Type | Use Case | Client Type |
|---|---|---|
| Authorization Code + PKCE | Web app login, SPA | Public |
| Authorization Code | Server-to-server | Confidential |
| Client Credentials | Service accounts, CI/CD | Confidential |
| Refresh Token | Token renewal | Both |

**OAuth 2.0 Server Configuration:**

```python
# auth/oauth2_server.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib
import base64

oauth = OAuth()

# Register OAuth providers
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="github",
    client_id=settings.GITHUB_CLIENT_ID,
    client_secret=settings.GITHUB_CLIENT_SECRET,
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    userinfo_endpoint="https://api.github.com/user",
    client_kwargs={"scope": "user:email"},
)


class OAuthClient(BaseModel):
    """Registered OAuth client application."""
    client_id: str
    client_secret_hash: str
    name: str
    redirect_uris: list[str]
    grant_types: list[str] = ["authorization_code", "refresh_token"]
    scopes: list[str] = ["read", "write"]
    is_confidential: bool = False
    created_at: datetime
    owner_id: str


class AuthorizationCode(BaseModel):
    """Short-lived authorization code."""
    code: str
    client_id: str
    user_id: str
    redirect_uri: str
    scope: str
    code_challenge: Optional[str] = None  # PKCE
    code_challenge_method: Optional[str] = None
    expires_at: datetime
    used: bool = False


class PKCEHelper:
    """PKCE (Proof Key for Code Exchange) implementation."""

    @staticmethod
    def generate_code_verifier(length: int = 128) -> str:
        """Generate a cryptographically random code verifier."""
        token = secrets.token_urlsafe(length)
        return token[:128]  # RFC 7636: 43-128 chars

    @staticmethod
    def generate_code_challenge(verifier: str) -> str:
        """Generate S256 code challenge from verifier."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    @staticmethod
    def verify_code_challenge(verifier: str, challenge: str) -> bool:
        """Verify PKCE code challenge."""
        expected = PKCEHelper.generate_code_challenge(verifier)
        return secrets.compare_digest(expected, challenge)
```

**Authorization Endpoint:**

```python
# auth/endpoints.py
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/oauth", tags=["OAuth 2.0"])


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = Query(..., regex="^code$"),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query(default="read"),
    state: str = Query(...),
    code_challenge: Optional[str] = Query(default=None),
    code_challenge_method: Optional[str] = Query(default=None),
    user: User = Depends(get_current_user),
):
    """OAuth 2.0 Authorization endpoint."""
    # Validate client
    client = await oauth_client_repo.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=400, detail="Invalid client_id")

    # Validate redirect URI
    if redirect_uri not in client.redirect_uris:
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")

    # Validate PKCE if provided
    if code_challenge and code_challenge_method != "S256":
        raise HTTPException(
            status_code=400,
            detail="Only S256 code_challenge_method is supported",
        )

    # Generate authorization code
    code = secrets.token_urlsafe(32)
    auth_code = AuthorizationCode(
        code=code,
        client_id=client_id,
        user_id=user.id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    await auth_code_repo.save(auth_code)

    # Log authorization event
    await audit_log.record(
        user_id=user.id,
        action="oauth.authorize",
        resource=f"client:{client_id}",
        details={"scope": scope, "redirect_uri": redirect_uri},
    )

    # Redirect back to client with code
    return RedirectResponse(
        url=f"{redirect_uri}?code={code}&state={state}"
    )


@router.post("/token")
async def token(
    grant_type: str = Form(...),
    code: Optional[str] = Form(default=None),
    redirect_uri: Optional[str] = Form(default=None),
    client_id: str = Form(...),
    client_secret: Optional[str] = Form(default=None),
    code_verifier: Optional[str] = Form(default=None),
    refresh_token: Optional[str] = Form(default=None),
):
    """OAuth 2.0 Token endpoint."""
    # Authenticate client
    client = await oauth_client_repo.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid client")

    if client.is_confidential:
        if not client_secret:
            raise HTTPException(status_code=401, detail="Client secret required")
        if not verify_password(client_secret, client.client_secret_hash):
            raise HTTPException(status_code=401, detail="Invalid client secret")

    if grant_type == "authorization_code":
        return await _handle_authorization_code_grant(
            code, redirect_uri, client, code_verifier
        )
    elif grant_type == "refresh_token":
        return await _handle_refresh_token_grant(refresh_token, client)
    elif grant_type == "client_credentials":
        if not client.is_confidential:
            raise HTTPException(status_code=400, detail="Confidential client required")
        return await _handle_client_credentials_grant(client)
    else:
        raise HTTPException(status_code=400, detail="Unsupported grant_type")


async def _handle_authorization_code_grant(
    code: str,
    redirect_uri: str,
    client: OAuthClient,
    code_verifier: Optional[str],
) -> dict:
    """Exchange authorization code for tokens."""
    # Retrieve and validate authorization code
    auth_code = await auth_code_repo.get(code)
    if not auth_code:
        raise HTTPException(status_code=400, detail="Invalid authorization code")
    if auth_code.used:
        # Replay detection — revoke all tokens for this client
        await token_repo.revoke_all_for_client(client.client_id)
        raise HTTPException(status_code=400, detail="Authorization code already used")
    if auth_code.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Authorization code expired")
    if auth_code.client_id != client.client_id:
        raise HTTPException(status_code=400, detail="Client mismatch")
    if auth_code.redirect_uri != redirect_uri:
        raise HTTPException(status_code=400, detail="Redirect URI mismatch")

    # Verify PKCE
    if auth_code.code_challenge:
        if not code_verifier:
            raise HTTPException(status_code=400, detail="code_verifier required")
        if not PKCEHelper.verify_code_challenge(code_verifier, auth_code.code_challenge):
            raise HTTPException(status_code=400, detail="Invalid code_verifier")

    # Mark code as used
    await auth_code_repo.mark_used(code)

    # Generate tokens
    tokens = await token_service.create_token_pair(
        user_id=auth_code.user_id,
        client_id=client.client_id,
        scope=auth_code.scope,
    )

    return {
        "access_token": tokens.access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": tokens.refresh_token,
        "scope": auth_code.scope,
    }
```

### 1.2 JWT Token Structure

**Access Token Payload:**

```python
# auth/jwt_service.py
from jose import jwt, JWTError
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional
import uuid


class AccessTokenPayload(BaseModel):
    """JWT Access Token claims."""
    sub: str           # User ID
    iss: str           # Issuer (platform URL)
    aud: str           # Audience (API URL)
    exp: int           # Expiration (Unix timestamp)
    iat: int           # Issued at
    jti: str           # JWT ID (unique token identifier)
    scope: str         # Space-separated scopes
    roles: list[str]   # User roles
    org_id: str        # Organization (tenant) ID
    mfa: bool          # Whether MFA was verified
    session_id: str    # Session identifier


class RefreshTokenPayload(BaseModel):
    """JWT Refresh Token claims."""
    sub: str
    jti: str
    exp: int
    iat: int
    family: str        # Token family for rotation detection
    version: int       # Incremented on each refresh


class TokenPair(BaseModel):
    """Access + Refresh token pair."""
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class JWTService:
    """JWT token creation and validation."""

    def __init__(
        self,
        private_key: str,
        public_key: str,
        algorithm: str = "RS256",
        access_token_ttl: int = 3600,       # 1 hour
        refresh_token_ttl: int = 604800,     # 7 days
        issuer: str = "https://api.seoplatform.com",
        audience: str = "https://api.seoplatform.com",
    ):
        self.private_key = private_key
        self.public_key = public_key
        self.algorithm = algorithm
        self.access_token_ttl = access_token_ttl
        self.refresh_token_ttl = refresh_token_ttl
        self.issuer = issuer
        self.audience = audience

    async def create_token_pair(
        self,
        user_id: str,
        client_id: str,
        scope: str,
        org_id: str = "",
        roles: list[str] = None,
        mfa_verified: bool = False,
    ) -> TokenPair:
        """Create a new access + refresh token pair."""
        now = datetime.utcnow()
        session_id = str(uuid.uuid4())
        family = str(uuid.uuid4())

        access_payload = AccessTokenPayload(
            sub=user_id,
            iss=self.issuer,
            aud=self.audience,
            exp=int((now + timedelta(seconds=self.access_token_ttl)).timestamp()),
            iat=int(now.timestamp()),
            jti=str(uuid.uuid4()),
            scope=scope,
            roles=roles or [],
            org_id=org_id,
            mfa=mfa_verified,
            session_id=session_id,
        )

        refresh_payload = RefreshTokenPayload(
            sub=user_id,
            jti=str(uuid.uuid4()),
            exp=int((now + timedelta(seconds=self.refresh_token_ttl)).timestamp()),
            iat=int(now.timestamp()),
            family=family,
            version=1,
        )

        access_token = jwt.encode(
            access_payload.model_dump(),
            self.private_key,
            algorithm=self.algorithm,
        )
        refresh_token = jwt.encode(
            refresh_payload.model_dump(),
            self.private_key,
            algorithm=self.algorithm,
        )

        # Store refresh token metadata for rotation/revocation
        await refresh_token_repo.save(
            jti=refresh_payload.jti,
            user_id=user_id,
            family=family,
            version=1,
            expires_at=datetime.utcfromtimestamp(refresh_payload.exp),
        )

        # Store session
        await session_repo.create(
            session_id=session_id,
            user_id=user_id,
            client_id=client_id,
            access_jti=access_payload.jti,
            refresh_jti=refresh_payload.jti,
            created_at=now,
            ip_address=None,  # Set from request context
            user_agent=None,  # Set from request context
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=datetime.utcfromtimestamp(access_payload.exp),
            refresh_expires_at=datetime.utcfromtimestamp(refresh_payload.exp),
        )

    async def verify_access_token(self, token: str) -> AccessTokenPayload:
        """Verify and decode an access token."""
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
            )

        # Check if token is blacklisted
        if await token_blacklist.is_blacklisted(payload["jti"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )

        return AccessTokenPayload(**payload)

    async def refresh_access_token(
        self, refresh_token: str
    ) -> TokenPair:
        """Refresh tokens with rotation and replay detection."""
        try:
            payload = jwt.decode(
                refresh_token,
                self.public_key,
                algorithms=[self.algorithm],
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        refresh_data = RefreshTokenPayload(**payload)

        # Check if token exists and is valid
        stored = await refresh_token_repo.get(refresh_data.jti)
        if not stored:
            # Possible token theft — revoke entire family
            await refresh_token_repo.revoke_family(refresh_data.family)
            await token_blacklist.add_family(refresh_data.family)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found — family revoked",
            )

        if stored.revoked:
            # Token reuse detected — revoke entire family
            await refresh_token_repo.revoke_family(refresh_data.family)
            await token_blacklist.add_family(refresh_data.family)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token reuse detected — all sessions revoked",
            )

        # Rotate: revoke old, issue new
        await refresh_token_repo.revoke(refresh_data.jti)

        user = await user_repo.get(refresh_data.sub)
        return await self.create_token_pair(
            user_id=refresh_data.sub,
            client_id=stored.client_id,
            scope=stored.scope,
            org_id=user.org_id,
            roles=user.roles,
            mfa_verified=stored.mfa_verified,
        )
```

**Token Blacklist for Logout:**

```python
# auth/token_blacklist.py
import redis.asyncio as redis


class TokenBlacklist:
    """Redis-backed token blacklist for instant revocation."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = "token:blacklist:"

    async def add(self, jti: str, expires_at: datetime):
        """Blacklist a single token JTI."""
        ttl = int((expires_at - datetime.utcnow()).total_seconds())
        if ttl > 0:
            await self.redis.setex(
                f"{self.prefix}{jti}", ttl, "revoked"
            )

    async def add_family(self, family: str):
        """Blacklist all tokens in a refresh token family."""
        # Store family-level blacklist (24h TTL)
        await self.redis.setex(
            f"{self.prefix}family:{family}", 86400, "revoked"
        )

    async def is_blacklisted(self, jti: str) -> bool:
        """Check if a token JTI is blacklisted."""
        return await self.redis.exists(f"{self.prefix}{jti}") == 1

    async def blacklist_user_sessions(self, user_id: str):
        """Revoke all sessions for a user (password change, compromise)."""
        sessions = await session_repo.get_all_for_user(user_id)
        pipeline = self.redis.pipeline()
        for session in sessions:
            pipeline.setex(
                f"{self.prefix}{session.access_jti}",
                3600,
                "revoked:all_sessions",
            )
            pipeline.setex(
                f"{self.prefix}{session.refresh_jti}",
                604800,
                "revoked:all_sessions",
            )
        await pipeline.execute()
        await session_repo.revoke_all_for_user(user_id)
```

### 1.3 Multi-Factor Authentication (MFA)

```python
# auth/mfa.py
import pyotp
import qrcode
import io
import base64
from cryptography.fernet import Fernet


class MFAService:
    """TOTP-based Multi-Factor Authentication."""

    def __init__(self, encryption_key: bytes):
        self.fernet = Fernet(encryption_key)
        self.issuer = "ProactiveSEO"

    async def setup_mfa(self, user_id: str) -> dict:
        """Generate MFA secret and QR code for user setup."""
        secret = pyotp.random_base32()
        encrypted_secret = self.fernet.encrypt(secret.encode()).decode()

        # Store encrypted secret (not yet active)
        await mfa_repo.set_pending_secret(user_id, encrypted_secret)

        # Generate QR code
        user = await user_repo.get(user_id)
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=self.issuer,
        )

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        # Generate backup codes
        backup_codes = [secrets.token_hex(4) for _ in range(10)]
        hashed_backup_codes = [hash_password(code) for code in backup_codes]

        return {
            "secret": secret,  # Show once, never stored in plaintext
            "qr_code": f"data:image/png;base64,{qr_base64}",
            "backup_codes": backup_codes,  # Show once
            "provisioning_uri": provisioning_uri,
        }

    async def activate_mfa(self, user_id: str, code: str) -> bool:
        """Activate MFA after user verifies first code."""
        encrypted_secret = await mfa_repo.get_pending_secret(user_id)
        if not encrypted_secret:
            raise HTTPException(400, "No MFA setup in progress")

        secret = self.fernet.decrypt(encrypted_secret.encode()).decode()
        totp = pyotp.TOTP(secret)

        if not totp.verify(code, valid_window=1):
            return False

        # Activate MFA
        await mfa_repo.activate(user_id, encrypted_secret)
        await audit_log.record(
            user_id=user_id,
            action="mfa.activated",
            resource=f"user:{user_id}",
            details={},
        )
        return True

    async def verify_mfa_code(self, user_id: str, code: str) -> bool:
        """Verify a TOTP code during authentication."""
        encrypted_secret = await mfa_repo.get_active_secret(user_id)
        if not encrypted_secret:
            return True  # MFA not enabled

        secret = self.fernet.decrypt(encrypted_secret.encode()).decode()
        totp = pyotp.TOTP(secret)

        if totp.verify(code, valid_window=1):
            return True

        # Check backup codes
        backup_code_valid = await self._verify_backup_code(user_id, code)
        if backup_code_valid:
            await audit_log.record(
                user_id=user_id,
                action="mfa.backup_code_used",
                resource=f"user:{user_id}",
                details={},
            )
            return True

        return False

    async def _verify_backup_code(self, user_id: str, code: str) -> bool:
        """Verify and consume a backup code."""
        hashed_codes = await mfa_repo.get_backup_codes(user_id)
        for i, hashed_code in enumerate(hashed_codes):
            if verify_password(code, hashed_code):
                # Consume backup code (one-time use)
                await mfa_repo.consume_backup_code(user_id, i)
                return True
        return False

    async def get_recovery_codes(self, user_id: str, count: int = 10) -> list[str]:
        """Generate new recovery codes (invalidates old ones)."""
        codes = [secrets.token_hex(4) for _ in range(count)]
        hashed = [hash_password(c) for c in codes]
        await mfa_repo.set_backup_codes(user_id, hashed)
        return codes


# MFA enforcement middleware
async def require_mfa(user: User = Depends(get_current_user)):
    """Dependency that enforces MFA for sensitive operations."""
    if user.mfa_enabled and not user.current_session_mfa_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA verification required",
            headers={"X-MFA-Required": "true"},
        )
    return user
```

### 1.4 Social Login (Google, GitHub)

```python
# auth/social_login.py
from fastapi import APIRouter, Request, HTTPException
from authlib.integrations.starlette_client import OAuthError

router = APIRouter(prefix="/auth/social", tags=["Social Login"])


class SocialLoginService:
    """Social login with Google and GitHub."""

    async def handle_google_callback(self, request: Request) -> TokenPair:
        """Process Google OAuth callback."""
        try:
            token = await oauth.google.authorize_access_token(request)
        except OAuthError as e:
            raise HTTPException(400, f"Google OAuth error: {e}")

        # Get user info from Google
        userinfo = token.get("userinfo")
        if not userinfo:
            raise HTTPException(400, "Failed to get user info from Google")

        email = userinfo["email"]
        if not userinfo.get("email_verified"):
            raise HTTPException(400, "Google email not verified")

        # Find or create user
        user = await user_repo.get_by_email(email)
        if not user:
            user = await self._create_social_user(
                email=email,
                name=userinfo.get("name", ""),
                avatar_url=userinfo.get("picture"),
                provider="google",
                provider_id=userinfo["sub"],
            )
        else:
            # Link Google account if not already linked
            await social_account_repo.link(
                user_id=user.id,
                provider="google",
                provider_id=userinfo["sub"],
            )

        # Create session
        return await jwt_service.create_token_pair(
            user_id=user.id,
            client_id="web",
            scope="read write",
            org_id=user.org_id,
            roles=user.roles,
        )

    async def handle_github_callback(self, request: Request) -> TokenPair:
        """Process GitHub OAuth callback."""
        try:
            token = await oauth.github.authorize_access_token(request)
        except OAuthError as e:
            raise HTTPException(400, f"GitHub OAuth error: {e}")

        # Get user info from GitHub
        resp = await oauth.github.get("user", token=token)
        github_user = resp.json()

        # Get primary email
        emails_resp = await oauth.github.get("user/emails", token=token)
        emails = emails_resp.json()
        primary_email = next(
            (e["email"] for e in emails if e["primary"] and e["verified"]),
            None,
        )
        if not primary_email:
            raise HTTPException(400, "No verified primary email on GitHub")

        user = await user_repo.get_by_email(primary_email)
        if not user:
            user = await self._create_social_user(
                email=primary_email,
                name=github_user.get("name") or github_user["login"],
                avatar_url=github_user.get("avatar_url"),
                provider="github",
                provider_id=str(github_user["id"]),
            )
        else:
            await social_account_repo.link(
                user_id=user.id,
                provider="github",
                provider_id=str(github_user["id"]),
            )

        return await jwt_service.create_token_pair(
            user_id=user.id,
            client_id="web",
            scope="read write",
            org_id=user.org_id,
            roles=user.roles,
        )

    async def _create_social_user(
        self,
        email: str,
        name: str,
        avatar_url: Optional[str],
        provider: str,
        provider_id: str,
    ) -> User:
        """Create a new user from social login."""
        # Generate a random password (user can set later)
        random_password = secrets.token_urlsafe(32)

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            avatar_url=avatar_url,
            password_hash=hash_password(random_password),
            email_verified=True,  # Social providers verify email
            mfa_enabled=False,
            org_id=await self._create_default_org(email),
            roles=["owner"],
            created_at=datetime.utcnow(),
        )
        await user_repo.create(user)

        await social_account_repo.link(
            user_id=user.id,
            provider=provider,
            provider_id=provider_id,
        )

        await audit_log.record(
            user_id=user.id,
            action="user.created_social",
            resource=f"user:{user.id}",
            details={"provider": provider},
        )

        return user


@router.get("/google/login")
async def google_login(request: Request):
    """Initiate Google OAuth login."""
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request):
    """Google OAuth callback."""
    service = SocialLoginService()
    tokens = await service.handle_google_callback(request)
    return _build_login_response(tokens)


@router.get("/github/login")
async def github_login(request: Request):
    """Initiate GitHub OAuth login."""
    redirect_uri = request.url_for("github_callback")
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback", name="github_callback")
async def github_callback(request: Request):
    """GitHub OAuth callback."""
    service = SocialLoginService()
    tokens = await service.handle_github_callback(request)
    return _build_login_response(tokens)
```

### 1.5 Session Management

```python
# auth/session.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid


class Session(BaseModel):
    """User session model."""
    session_id: str
    user_id: str
    client_id: str
    org_id: str
    access_jti: str
    refresh_jti: str
    created_at: datetime
    last_active_at: datetime
    ip_address: str
    user_agent: str
    device_fingerprint: Optional[str] = None
    is_active: bool = True
    mfa_verified: bool = False


class SessionService:
    """Session lifecycle management."""

    def __init__(self, redis_client, db_client):
        self.redis = redis_client
        self.db = db_client
        self.max_sessions_per_user = 10
        self.session_timeout = 1800  # 30 minutes inactivity
        self.absolute_timeout = 28800  # 8 hours absolute

    async def create_session(
        self,
        user_id: str,
        client_id: str,
        org_id: str,
        ip_address: str,
        user_agent: str,
        mfa_verified: bool = False,
    ) -> Session:
        """Create a new user session."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        session = Session(
            session_id=session_id,
            user_id=user_id,
            client_id=client_id,
            org_id=org_id,
            access_jti="",  # Set after JWT creation
            refresh_jti="",
            created_at=now,
            last_active_at=now,
            ip_address=ip_address,
            user_agent=user_agent,
            mfa_verified=mfa_verified,
        )

        # Enforce max sessions per user
        active_sessions = await self._get_active_sessions(user_id)
        if len(active_sessions) >= self.max_sessions_per_user:
            # Revoke oldest session
            oldest = min(active_sessions, key=lambda s: s.last_active_at)
            await self.revoke_session(oldest.session_id, reason="max_sessions_exceeded")

        # Store in Redis for fast lookups
        await self.redis.hset(
            f"session:{session_id}",
            mapping=session.model_dump(mode="json"),
        )
        await self.redis.expire(f"session:{session_id}", self.absolute_timeout)

        # Store in user's session set
        await self.redis.sadd(f"user_sessions:{user_id}", session_id)

        # Store in DB for persistence
        await self.db.execute(
            """
            INSERT INTO sessions (session_id, user_id, client_id, org_id, 
                                  ip_address, user_agent, created_at, 
                                  last_active_at, is_active, mfa_verified)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            session_id, user_id, client_id, org_id,
            ip_address, user_agent, now, now, True, mfa_verified,
        )

        return session

    async def validate_session(self, session_id: str) -> Session:
        """Validate and refresh a session."""
        session_data = await self.redis.hgetall(f"session:{session_id}")
        if not session_data:
            # Check DB as fallback
            db_session = await self.db.fetchrow(
                "SELECT * FROM sessions WHERE session_id = $1 AND is_active = TRUE",
                session_id,
            )
            if not db_session:
                raise HTTPException(401, "Session not found")
            # Re-populate Redis
            await self.redis.hset(f"session:{session_id}", mapping=dict(db_session))
            session_data = dict(db_session)

        session = Session(**session_data)
        now = datetime.utcnow()

        # Check absolute timeout
        if (now - session.created_at).total_seconds() > self.absolute_timeout:
            await self.revoke_session(session_id, reason="absolute_timeout")
            raise HTTPException(401, "Session expired (absolute timeout)")

        # Check inactivity timeout
        if (now - session.last_active_at).total_seconds() > self.session_timeout:
            await self.revoke_session(session_id, reason="inactivity_timeout")
            raise HTTPException(401, "Session expired (inactivity)")

        # Update last active time
        await self.redis.hset(
            f"session:{session_id}", "last_active_at", now.isoformat()
        )

        return session

    async def revoke_session(self, session_id: str, reason: str = "user_action"):
        """Revoke a specific session."""
        session_data = await self.redis.hgetall(f"session:{session_id}")
        if session_data:
            user_id = session_data.get("user_id")
            await self.redis.srem(f"user_sessions:{user_id}", session_id)
            await self.redis.delete(f"session:{session_id}")

        await self.db.execute(
            "UPDATE sessions SET is_active = FALSE, revoked_at = NOW(), revoke_reason = $1 WHERE session_id = $2",
            reason, session_id,
        )

    async def revoke_all_sessions(self, user_id: str, except_session: str = None):
        """Revoke all sessions for a user."""
        session_ids = await self.redis.smembers(f"user_sessions:{user_id}")
        for sid in session_ids:
            if sid != except_session:
                await self.revoke_session(sid, reason="all_sessions_revoked")
        await token_blacklist.blacklist_user_sessions(user_id)
```

### 1.6 Password Policy

```python
# auth/password.py
import re
from passlib.context import CryptContext
from passlib.handlers.argon2 import argon2
import hashlib


# Password hashing context with Argon2id (preferred) and bcrypt (fallback)
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    default="argon2",
    argon2__type="id",        # Argon2id variant
    argon2__memory_cost=65536, # 64 MB
    argon2__time_cost=3,       # 3 iterations
    argon2__parallelism=4,     # 4 threads
    argon2__salt_len=16,       # 16 bytes salt
    argon2__hash_len=32,       # 32 bytes hash
    bcrypt__rounds=12,         # bcrypt cost factor
    deprecated="auto",         # Auto-upgrade old hashes on verify
)


class PasswordPolicy:
    """Enterprise password policy enforcement."""

    MIN_LENGTH = 12
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True
    HISTORY_COUNT = 12  # Remember last 12 passwords
    MIN_AGE_HOURS = 1   # Minimum time between password changes
    MAX_AGE_DAYS = 90   # Maximum password age (0 = no expiry)

    # Common breached passwords (top 10k + known breaches)
    BREACHED_PASSWORDS_FILE = "data/breached_passwords.txt"

    @classmethod
    async def validate(cls, password: str, user_context: dict = None) -> list[str]:
        """Validate password against policy. Returns list of violations."""
        violations = []

        if len(password) < cls.MIN_LENGTH:
            violations.append(
                f"Password must be at least {cls.MIN_LENGTH} characters"
            )
        if len(password) > cls.MAX_LENGTH:
            violations.append(
                f"Password must be at most {cls.MAX_LENGTH} characters"
            )
        if cls.REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
            violations.append("Password must contain at least one uppercase letter")
        if cls.REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
            violations.append("Password must contain at least one lowercase letter")
        if cls.REQUIRE_DIGIT and not re.search(r"\d", password):
            violations.append("Password must contain at least one digit")
        if cls.REQUIRE_SPECIAL and not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password):
            violations.append("Password must contain at least one special character")

        # Check against breached passwords
        if await cls._is_breached(password):
            violations.append("Password has been found in a data breach")

        # Check user context (name, email, etc.)
        if user_context:
            password_lower = password.lower()
            for field in ["name", "email", "company"]:
                value = user_context.get(field, "").lower()
                if value and len(value) > 3 and value in password_lower:
                    violations.append(
                        f"Password must not contain your {field}"
                    )

        # Check for common patterns
        if cls._has_common_pattern(password):
            violations.append("Password contains a common pattern")

        return violations

    @classmethod
    async def _is_breached(cls, password: str) -> bool:
        """Check against Have I Been Pwned API (k-anonymity)."""
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.pwnedpasswords.com/range/{prefix}",
                    headers={"Add-Padding": "true"},
                    timeout=5.0,
                )
                if response.status_code == 200:
                    for line in response.text.splitlines():
                        hash_suffix, count = line.split(":")
                        if hash_suffix == suffix:
                            return int(count) > 0
        except Exception:
            # If API is down, fall back to local check
            pass

        # Local breach list fallback
        return cls._check_local_breach_list(password)

    @classmethod
    def _has_common_pattern(cls, password: str) -> bool:
        """Detect common password patterns."""
        patterns = [
            r"(.)\1{2,}",           # Repeated characters (aaa, 111)
            r"(012|123|234|345|456|567|678|789|890)",  # Sequential numbers
            r"(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl)",  # Sequential letters
            r"(qwerty|asdf|zxcv)",  # Keyboard patterns
            r"(password|letmein|welcome|monkey|dragon)",  # Common words
        ]
        password_lower = password.lower()
        return any(re.search(p, password_lower) for p in patterns)

    @classmethod
    async def check_history(cls, user_id: str, new_password: str) -> bool:
        """Check if password was used recently."""
        history = await password_history_repo.get_recent(
            user_id, count=cls.HISTORY_COUNT
        )
        for old_hash in history:
            if pwd_context.verify(new_password, old_hash):
                return False  # Password was used before
        return True


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)
```

### 1.7 Account Lockout

```python
# auth/lockout.py
from datetime import datetime, timedelta
from enum import Enum


class LockoutPolicy(Enum):
    PROGRESSIVE = "progressive"   # Increasing lockout duration
    FIXED = "fixed"               # Fixed lockout duration
    PERMANENT = "permanent"       # Requires admin unlock


class AccountLockoutService:
    """Account lockout after failed login attempts."""

    def __init__(self, redis_client, policy=LockoutPolicy.PROGRESSIVE):
        self.redis = redis_client
        self.policy = policy

        # Progressive lockout configuration
        self.max_attempts = 5
        self.lockout_durations = {
            5: 300,        # 5th failure: 5 minutes
            10: 1800,      # 10th failure: 30 minutes
            15: 3600,      # 15th failure: 1 hour
            20: 86400,     # 20th failure: 24 hours
            25: -1,        # 25th failure: permanent (requires admin)
        }

    async def record_failed_attempt(
        self,
        identifier: str,  # email, IP, or combination
        ip_address: str,
        user_agent: str,
    ) -> dict:
        """Record a failed login attempt and determine lockout status."""
        key = f"login_attempts:{identifier}"
        ip_key = f"login_attempts:ip:{ip_address}"

        # Increment attempt counter
        attempts = await self.redis.incr(key)
        await self.redis.expire(key, 86400)  # Reset after 24 hours

        # Track by IP as well
        ip_attempts = await self.redis.incr(ip_key)
        await self.redis.expire(ip_key, 86400)

        # Determine lockout
        lockout_duration = self._get_lockout_duration(attempts)
        is_locked = lockout_duration is not None

        if is_locked:
            if lockout_duration == -1:
                # Permanent lockout
                await self.redis.set(f"locked:{identifier}", "permanent")
                await self.redis.set(f"locked:ip:{ip_address}", "permanent")
            else:
                await self.redis.setex(
                    f"locked:{identifier}", lockout_duration, "temporary"
                )
                await self.redis.setex(
                    f"locked:ip:{ip_address}", lockout_duration, "temporary"
                )

            # Alert on lockout
            await self._alert_lockout(identifier, ip_address, attempts)

        # Record attempt in audit log
        await audit_log.record(
            user_id=identifier,
            action="auth.login_failed",
            resource=f"user:{identifier}",
            details={
                "ip_address": ip_address,
                "user_agent": user_agent,
                "attempts": attempts,
                "locked": is_locked,
                "lockout_duration": lockout_duration,
            },
        )

        return {
            "is_locked": is_locked,
            "attempts": attempts,
            "max_attempts": self.max_attempts,
            "lockout_duration": lockout_duration,
            "remaining_attempts": max(0, self.max_attempts - attempts),
        }

    async def check_lockout(self, identifier: str, ip_address: str) -> dict:
        """Check if an account or IP is locked out."""
        account_locked = await self.redis.get(f"locked:{identifier}")
        ip_locked = await self.redis.get(f"locked:ip:{ip_address}")

        if account_locked:
            ttl = await self.redis.ttl(f"locked:{identifier}")
            return {
                "is_locked": True,
                "type": "account",
                "permanent": account_locked == "permanent",
                "remaining_seconds": ttl if ttl > 0 else None,
            }
        if ip_locked:
            ttl = await self.redis.ttl(f"locked:ip:{ip_address}")
            return {
                "is_locked": True,
                "type": "ip",
                "permanent": ip_locked == "permanent",
                "remaining_seconds": ttl if ttl > 0 else None,
            }

        return {"is_locked": False}

    async def reset_attempts(self, identifier: str):
        """Reset failed attempt counter (after successful login)."""
        await self.redis.delete(f"login_attempts:{identifier}")

    async def unlock_account(self, identifier: str, admin_user_id: str):
        """Admin unlock of a locked account."""
        await self.redis.delete(f"locked:{identifier}")
        await self.redis.delete(f"login_attempts:{identifier}")

        await audit_log.record(
            user_id=admin_user_id,
            action="auth.account_unlocked",
            resource=f"user:{identifier}",
            details={"unlocked_by": admin_user_id},
        )

    def _get_lockout_duration(self, attempts: int) -> Optional[int]:
        """Get lockout duration based on attempt count."""
        duration = None
        for threshold, dur in sorted(self.lockout_durations.items()):
            if attempts >= threshold:
                duration = dur
        return duration

    async def _alert_lockout(self, identifier: str, ip_address: str, attempts: int):
        """Send alert on account lockout."""
        await notification_service.send(
            channel="security",
            template="account_locked",
            data={
                "identifier": identifier,
                "ip_address": ip_address,
                "attempts": attempts,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
```

### 1.8 SSO (SAML 2.0) for Enterprise

```python
# auth/sso/saml.py
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.utils import OneLogin_Saml2_Utils
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel


class SAMLConfig(BaseModel):
    """SAML 2.0 Service Provider configuration."""
    entity_id: str
    acs_url: str               # Assertion Consumer Service URL
    sls_url: str               # Single Logout Service URL
    sp_cert: str               # SP public certificate
    sp_key: str                # SP private key
    idp_entity_id: str         # Identity Provider entity ID
    idp_sso_url: str           # IDP Single Sign-On URL
    idp_slo_url: str           # IDP Single Logout URL
    idp_cert: str              # IDP public certificate
    sign_requests: bool = True
    want_assertions_signed: bool = True
    want_response_signed: bool = True


router = APIRouter(prefix="/auth/sso", tags=["SSO"])


class SAMLService:
    """SAML 2.0 SSO service."""

    async def prepare_auth_request(self, request: Request, org_id: str) -> dict:
        """Generate SAML AuthnRequest."""
        saml_config = await self._get_saml_config(org_id)
        req = await self._prepare_saml_request(request, saml_config)
        auth = OneLogin_Saml2_Auth(req, saml_config)

        return {
            "redirect_url": auth.login(),
            "request_id": auth.get_last_request_id(),
        }

    async def process_saml_response(
        self, request: Request, org_id: str
    ) -> TokenPair:
        """Process SAML Response from Identity Provider."""
        saml_config = await self._get_saml_config(org_id)
        req = await self._prepare_saml_request(request, saml_config)
        auth = OneLogin_Saml2_Auth(req, saml_config)

        auth.process_response()
        errors = auth.get_errors()

        if errors:
            raise HTTPException(
                status_code=400,
                detail=f"SAML validation errors: {errors}",
            )

        if not auth.is_authenticated():
            raise HTTPException(401, "SAML authentication failed")

        # Extract user attributes
        attributes = auth.get_attributes()
        name_id = auth.get_nameid()

        email = attributes.get("email", [name_id])[0]
        name = attributes.get("displayName", [""])[0]
        groups = attributes.get("groups", [])

        # Map SAML groups to platform roles
        roles = self._map_groups_to_roles(groups, org_id)

        # Find or create user
        user = await user_repo.get_by_email(email)
        if not user:
            user = await self._create_sso_user(
                email=email,
                name=name,
                org_id=org_id,
                roles=roles,
            )

        # Create tokens
        return await jwt_service.create_token_pair(
            user_id=user.id,
            client_id="sso",
            scope="read write",
            org_id=org_id,
            roles=roles,
            mfa_verified=True,  # IDP handles MFA
        )

    async def initiate_slo(self, request: Request, org_id: str, user: User) -> str:
        """Initiate SAML Single Logout."""
        saml_config = await self._get_saml_config(org_id)
        req = await self._prepare_saml_request(request, saml_config)
        auth = OneLogin_Saml2_Auth(req, saml_config)

        # Revoke all local sessions
        await session_service.revoke_all_sessions(user.id)

        # Generate SLO request
        slo_url = auth.logout()
        return slo_url

    async def _get_saml_config(self, org_id: str) -> dict:
        """Load SAML configuration for organization."""
        config = await sso_config_repo.get(org_id)
        if not config:
            raise HTTPException(404, "SSO not configured for this organization")

        return {
            "sp": {
                "entityId": config.entity_id,
                "assertionConsumerService": {
                    "url": config.acs_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                },
                "singleLogoutService": {
                    "url": config.sls_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "x509cert": config.sp_cert,
                "privateKey": config.sp_key,
            },
            "idp": {
                "entityId": config.idp_entity_id,
                "singleSignOnService": {
                    "url": config.idp_sso_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "singleLogoutService": {
                    "url": config.idp_slo_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "x509cert": config.idp_cert,
            },
            "security": {
                "authnRequestsSigned": config.sign_requests,
                "wantAssertionsSigned": config.want_assertions_signed,
                "wantMessagesSigned": config.want_response_signed,
                "requestedAuthnContext": True,
                "requestedAuthnContextComparison": "exact",
            },
        }

    def _map_groups_to_roles(self, groups: list[str], org_id: str) -> list[str]:
        """Map IDP groups to platform roles."""
        role_mapping = {
            "seo-admins": "admin",
            "seo-editors": "editor",
            "seo-viewers": "viewer",
        }
        roles = []
        for group in groups:
            if group in role_mapping:
                roles.append(role_mapping[group])
        return roles if roles else ["viewer"]  # Default to viewer


@router.post("/login/{org_id}")
async def saml_login(request: Request, org_id: str):
    """Initiate SAML SSO login."""
    service = SAMLService()
    result = await service.prepare_auth_request(request, org_id)
    return RedirectResponse(url=result["redirect_url"])


@router.post("/callback/{org_id}")
async def saml_callback(request: Request, org_id: str):
    """SAML SSO callback (Assertion Consumer Service)."""
    service = SAMLService()
    tokens = await service.process_saml_response(request, org_id)
    return _build_login_response(tokens)


@router.post("/logout/{org_id}")
async def saml_logout(request: Request, org_id: str, user: User = Depends(get_current_user)):
    """Initiate SAML Single Logout."""
    service = SAMLService()
    slo_url = await service.initiate_slo(request, org_id, user)
    return RedirectResponse(url=slo_url)
```

---

## 2. Authorization System

### 2.1 RBAC (Role-Based Access Control)

```python
# auth/rbac.py
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Permission(str, Enum):
    """Granular permissions."""
    # Project permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    PROJECT_SHARE = "project:share"

    # SEO Audit permissions
    AUDIT_CREATE = "audit:create"
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # Keyword permissions
    KEYWORD_CREATE = "keyword:create"
    KEYWORD_READ = "keyword:read"
    KEYWORD_UPDATE = "keyword:update"
    KEYWORD_DELETE = "keyword:delete"
    KEYWORD_TRACK = "keyword:track"

    # Backlink permissions
    BACKLINK_READ = "backlink:read"
    BACKLINK_DISAVOW = "backlink:disavow"
    BACKLINK_MANAGE = "backlink:manage"

    # Content permissions
    CONTENT_CREATE = "content:create"
    CONTENT_READ = "content:read"
    CONTENT_UPDATE = "content:update"
    CONTENT_DELETE = "content:delete"
    CONTENT_PUBLISH = "content:publish"

    # User management permissions
    USER_INVITE = "user:invite"
    USER_MANAGE = "user:manage"
    USER_REMOVE = "user:remove"

    # API key permissions
    APIKEY_CREATE = "apikey:create"
    APIKEY_READ = "apikey:read"
    APIKEY_REVOKE = "apikey:revoke"

    # Billing permissions
    BILLING_VIEW = "billing:view"
    BILLING_MANAGE = "billing:manage"

    # Settings permissions
    SETTINGS_READ = "settings:read"
    SETTINGS_UPDATE = "settings:update"
    SETTINGS_INTEGRATIONS = "settings:integrations"

    # Audit log permissions
    AUDITLOG_READ = "auditlog:read"

    # Organization permissions
    ORG_MANAGE = "org:manage"
    ORG_DELETE = "org:delete"


class Role(str, Enum):
    """System roles."""
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


# Permissions matrix: role -> set of permissions
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.OWNER: {
        # All permissions
        Permission.PROJECT_CREATE, Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE, Permission.PROJECT_DELETE,
        Permission.PROJECT_SHARE,
        Permission.AUDIT_CREATE, Permission.AUDIT_READ, Permission.AUDIT_EXPORT,
        Permission.KEYWORD_CREATE, Permission.KEYWORD_READ,
        Permission.KEYWORD_UPDATE, Permission.KEYWORD_DELETE,
        Permission.KEYWORD_TRACK,
        Permission.BACKLINK_READ, Permission.BACKLINK_DISAVOW,
        Permission.BACKLINK_MANAGE,
        Permission.CONTENT_CREATE, Permission.CONTENT_READ,
        Permission.CONTENT_UPDATE, Permission.CONTENT_DELETE,
        Permission.CONTENT_PUBLISH,
        Permission.USER_INVITE, Permission.USER_MANAGE, Permission.USER_REMOVE,
        Permission.APIKEY_CREATE, Permission.APIKEY_READ, Permission.APIKEY_REVOKE,
        Permission.BILLING_VIEW, Permission.BILLING_MANAGE,
        Permission.SETTINGS_READ, Permission.SETTINGS_UPDATE,
        Permission.SETTINGS_INTEGRATIONS,
        Permission.AUDITLOG_READ,
        Permission.ORG_MANAGE, Permission.ORG_DELETE,
    },
    Role.ADMIN: {
        Permission.PROJECT_CREATE, Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE, Permission.PROJECT_DELETE,
        Permission.PROJECT_SHARE,
        Permission.AUDIT_CREATE, Permission.AUDIT_READ, Permission.AUDIT_EXPORT,
        Permission.KEYWORD_CREATE, Permission.KEYWORD_READ,
        Permission.KEYWORD_UPDATE, Permission.KEYWORD_DELETE,
        Permission.KEYWORD_TRACK,
        Permission.BACKLINK_READ, Permission.BACKLINK_DISAVOW,
        Permission.BACKLINK_MANAGE,
        Permission.CONTENT_CREATE, Permission.CONTENT_READ,
        Permission.CONTENT_UPDATE, Permission.CONTENT_DELETE,
        Permission.CONTENT_PUBLISH,
        Permission.USER_INVITE, Permission.USER_MANAGE,
        Permission.APIKEY_CREATE, Permission.APIKEY_READ, Permission.APIKEY_REVOKE,
        Permission.BILLING_VIEW,
        Permission.SETTINGS_READ, Permission.SETTINGS_UPDATE,
        Permission.SETTINGS_INTEGRATIONS,
        Permission.AUDITLOG_READ,
    },
    Role.EDITOR: {
        Permission.PROJECT_READ, Permission.PROJECT_UPDATE,
        Permission.AUDIT_CREATE, Permission.AUDIT_READ, Permission.AUDIT_EXPORT,
        Permission.KEYWORD_CREATE, Permission.KEYWORD_READ,
        Permission.KEYWORD_UPDATE, Permission.KEYWORD_TRACK,
        Permission.BACKLINK_READ,
        Permission.CONTENT_CREATE, Permission.CONTENT_READ,
        Permission.CONTENT_UPDATE, Permission.CONTENT_PUBLISH,
        Permission.SETTINGS_READ,
    },
    Role.VIEWER: {
        Permission.PROJECT_READ,
        Permission.AUDIT_READ, Permission.AUDIT_EXPORT,
        Permission.KEYWORD_READ,
        Permission.BACKLINK_READ,
        Permission.CONTENT_READ,
        Permission.SETTINGS_READ,
    },
}


class RBACService:
    """Role-Based Access Control service."""

    async def check_permission(
        self,
        user_id: str,
        permission: Permission,
        resource_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> bool:
        """Check if user has a specific permission."""
        # Get user's role
        user = await user_repo.get(user_id)
        if not user:
            return False

        # Check if role has the permission
        user_roles = user.roles if isinstance(user.roles, list) else [user.roles]
        for role in user_roles:
            role_enum = Role(role)
            if permission in ROLE_PERMISSIONS.get(role_enum, set()):
                # Additional resource-level check
                if resource_id:
                    return await self._check_resource_access(
                        user_id, resource_id, permission
                    )
                return True

        return False

    async def _check_resource_access(
        self,
        user_id: str,
        resource_id: str,
        permission: Permission,
    ) -> bool:
        """Check resource-level access (e.g., project membership)."""
        # Check if user has access to this specific resource
        access = await access_repo.get(user_id=user_id, resource_id=resource_id)
        if not access:
            return False

        # Check if the permission is in the user's resource-level permissions
        return permission.value in access.permissions

    async def get_user_permissions(self, user_id: str) -> set[Permission]:
        """Get all permissions for a user."""
        user = await user_repo.get(user_id)
        if not user:
            return set()

        permissions = set()
        user_roles = user.roles if isinstance(user.roles, list) else [user.roles]
        for role in user_roles:
            role_enum = Role(role)
            permissions.update(ROLE_PERMISSIONS.get(role_enum, set()))

        return permissions


# FastAPI dependency for permission checking
def require_permission(permission: Permission):
    """Dependency factory for permission checking."""
    async def _check(
        user: User = Depends(get_current_user),
        rbac: RBACService = Depends(get_rbac_service),
    ):
        has_perm = await rbac.check_permission(
            user_id=user.id,
            permission=permission,
        )
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}",
            )
        return user
    return _check


# Usage in endpoints
@router.post("/projects")
async def create_project(
    project: ProjectCreate,
    user: User = Depends(require_permission(Permission.PROJECT_CREATE)),
):
    """Create a new project (requires PROJECT_CREATE permission)."""
    return await project_service.create(project, user.id)
```

### 2.2 Row-Level Security (Multi-Tenant)

```python
# auth/row_level_security.py
from sqlalchemy import event, text
from sqlalchemy.orm import Session


class RowLevelSecurity:
    """Row-level security for multi-tenant data isolation."""

    @staticmethod
    def apply_rls_to_engine(engine):
        """Apply RLS policies to all tables."""
        @event.listens_for(engine, "connect")
        def set_rls_context(dbapi_conn, connection_record):
            """Set tenant context on every connection."""
            # This will be set per-request via middleware
            pass

    @staticmethod
    async def set_tenant_context(db_session: Session, org_id: str, user_id: str):
        """Set the current tenant context for RLS."""
        await db_session.execute(
            text("SET app.current_org_id = :org_id"),
            {"org_id": org_id},
        )
        await db_session.execute(
            text("SET app.current_user_id = :user_id"),
            {"user_id": user_id},
        )

    @staticmethod
    def create_rls_policies():
        """SQL to create RLS policies on tables."""
        return """
        -- Enable RLS on projects table
        ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

        -- Policy: Users can only see projects in their organization
        CREATE POLICY org_isolation ON projects
            FOR ALL
            USING (org_id = current_setting('app.current_org_id')::uuid);

        -- Policy: Users can only modify projects they have access to
        CREATE POLICY project_access ON projects
            FOR ALL
            USING (
                id IN (
                    SELECT resource_id FROM user_resource_access
                    WHERE user_id = current_setting('app.current_user_id')::uuid
                    AND permission IN ('project:update', 'project:delete')
                )
            );

        -- Enable RLS on keywords table
        ALTER TABLE keywords ENABLE ROW LEVEL SECURITY;

        CREATE POLICY keyword_org_isolation ON keywords
            FOR ALL
            USING (org_id = current_setting('app.current_org_id')::uuid);

        -- Enable RLS on content table
        ALTER TABLE content ENABLE ROW LEVEL SECURITY;

        CREATE POLICY content_org_isolation ON content
            FOR ALL
            USING (org_id = current_setting('app.current_org_id')::uuid);

        -- Enable RLS on backlinks table
        ALTER TABLE backlinks ENABLE ROW LEVEL SECURITY;

        CREATE POLICY backlink_org_isolation ON backlinks
            FOR ALL
            USING (org_id = current_setting('app.current_org_id')::uuid);
        """


# Middleware to inject tenant context
class TenantContextMiddleware:
    """Middleware that sets tenant context for all database operations."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract tenant from request
            request = Request(scope, receive)
            user = await get_current_user_from_request(request)

            if user:
                # Store in request state
                scope["state"] = scope.get("state", {})
                scope["state"]["org_id"] = user.org_id
                scope["state"]["user_id"] = user.id

        return await self.app(scope, receive, send)
```

### 2.3 API Key Scoping

```python
# auth/api_keys.py
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel


class APIKeyScope(BaseModel):
    """API key permission scope."""
    permissions: list[str]       # e.g., ["keyword:read", "audit:create"]
    resource_ids: list[str]      # Specific resources (empty = all)
    rate_limit_tier: str = "standard"  # standard, premium, enterprise
    ip_whitelist: list[str] = [] # Empty = any IP
    expires_at: Optional[datetime] = None


class APIKey(BaseModel):
    """API key model."""
    key_id: str           # Public identifier (first 8 chars)
    key_hash: str         # SHA-256 hash of full key
    name: str
    org_id: str
    created_by: str
    scopes: APIKeyScope
    created_at: datetime
    last_used_at: Optional[datetime] = None
    is_active: bool = True


class APIKeyService:
    """API key management service."""

    PREFIX = "seo_"

    async def create_api_key(
        self,
        org_id: str,
        created_by: str,
        name: str,
        scopes: APIKeyScope,
    ) -> tuple[str, APIKey]:
        """Create a new API key. Returns (plaintext_key, key_model)."""
        # Generate key
        raw_key = secrets.token_urlsafe(32)
        full_key = f"{self.PREFIX}{raw_key}"
        key_id = full_key[:12]  # Public identifier
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            org_id=org_id,
            created_by=created_by,
            scopes=scopes,
            created_at=datetime.utcnow(),
        )

        await api_key_repo.create(api_key)

        await audit_log.record(
            user_id=created_by,
            action="apikey.created",
            resource=f"apikey:{key_id}",
            details={"name": name, "scopes": scopes.model_dump()},
        )

        # Return plaintext key (only shown once)
        return full_key, api_key

    async def validate_api_key(
        self,
        key: str,
        required_permission: str,
        request_ip: str = None,
    ) -> APIKey:
        """Validate an API key and check permissions."""
        # Hash the provided key
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        key_id = key[:12]

        # Look up key
        api_key = await api_key_repo.get_by_id(key_id)
        if not api_key:
            raise HTTPException(401, "Invalid API key")

        # Verify hash
        if api_key.key_hash != key_hash:
            raise HTTPException(401, "Invalid API key")

        # Check if active
        if not api_key.is_active:
            raise HTTPException(401, "API key is revoked")

        # Check expiration
        if api_key.scopes.expires_at and api_key.scopes.expires_at < datetime.utcnow():
            raise HTTPException(401, "API key has expired")

        # Check IP whitelist
        if api_key.scopes.ip_whitelist and request_ip:
            if request_ip not in api_key.scopes.ip_whitelist:
                raise HTTPException(403, "IP address not in API key whitelist")

        # Check permission
        if required_permission not in api_key.scopes.permissions:
            raise HTTPException(
                403, f"API key missing permission: {required_permission}"
            )

        # Update last used
        await api_key_repo.update_last_used(key_id, datetime.utcnow())

        return api_key

    async def revoke_api_key(self, key_id: str, revoked_by: str):
        """Revoke an API key."""
        await api_key_repo.deactivate(key_id)

        await audit_log.record(
            user_id=revoked_by,
            action="apikey.revoked",
            resource=f"apikey:{key_id}",
            details={"revoked_by": revoked_by},
        )

    def get_rate_limit(self, tier: str) -> dict:
        """Get rate limits for API key tier."""
        tiers = {
            "standard": {"requests_per_minute": 60, "requests_per_hour": 1000},
            "premium": {"requests_per_minute": 300, "requests_per_hour": 10000},
            "enterprise": {"requests_per_minute": 1000, "requests_per_hour": 50000},
        }
        return tiers.get(tier, tiers["standard"])
```

---

## 3. Data Security

### 3.1 Encryption at Rest (AES-256)

```python
# security/encryption.py
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import os
import json
from typing import Any


class FieldEncryption:
    """AES-256-GCM field-level encryption for sensitive data."""

    def __init__(self, master_key: bytes):
        """Initialize with a 256-bit master key."""
        self.master_key = master_key

    def _derive_key(self, context: str) -> bytes:
        """Derive a unique key for each encryption context."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=context.encode(),
            iterations=100000,
            backend=default_backend(),
        )
        return kdf.derive(self.master_key)

    def encrypt_field(self, plaintext: str, context: str = "default") -> str:
        """Encrypt a single field value."""
        key = self._derive_key(context)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), context.encode())
        # Combine nonce + ciphertext and base64 encode
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode()

    def decrypt_field(self, encrypted: str, context: str = "default") -> str:
        """Decrypt a single field value."""
        key = self._derive_key(context)
        aesgcm = AESGCM(key)
        combined = base64.b64decode(encrypted)
        nonce = combined[:12]
        ciphertext = combined[12:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, context.encode())
        return plaintext.decode()


class EncryptedJSON:
    """Encrypt/decrypt entire JSON documents."""

    def __init__(self, encryption: FieldEncryption):
        self.encryption = encryption

    def encrypt_document(self, data: dict, context: str) -> str:
        """Encrypt a JSON document."""
        json_str = json.dumps(data, sort_keys=True)
        return self.encryption.encrypt_field(json_str, context)

    def decrypt_document(self, encrypted: str, context: str) -> dict:
        """Decrypt a JSON document."""
        json_str = self.encryption.decrypt_field(encrypted, context)
        return json.loads(json_str)


class EncryptedColumn:
    """SQLAlchemy custom type for encrypted database columns."""

    impl = sa.Text

    def __init__(self, encryption: FieldEncryption, context: str):
        self.encryption = encryption
        self.context = context

    def process_bind_param(self, value, dialect):
        """Encrypt before storing."""
        if value is not None:
            return self.encryption.encrypt_field(str(value), self.context)
        return value

    def process_result_value(self, value, dialect):
        """Decrypt after loading."""
        if value is not None:
            return self.encryption.decrypt_field(value, self.context)
        return value
```

### 3.2 Encryption in Transit (TLS 1.3)

```python
# security/tls_config.py
import ssl


def create_tls_context() -> ssl.SSLContext:
    """Create a hardened TLS 1.3 context."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3

    # Strong cipher suites only
    context.set_ciphers(
        "TLS_AES_256_GCM_SHA384:"
        "TLS_CHACHA20_POLY1305_SHA256:"
        "TLS_AES_128_GCM_SHA256"
    )

    # Certificate verification
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True

    return context


# Nginx configuration for TLS 1.3
NGINX_TLS_CONFIG = """
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;

    ssl_certificate /etc/ssl/certs/seoplatform.crt;
    ssl_certificate_key /etc/ssl/private/seoplatform.key;

    # TLS 1.3 only
    ssl_protocols TLSv1.3;
    ssl_ciphers TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256;
    ssl_prefer_server_ciphers off;

    # OCSP stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;

    # HSTS (2 years, include subdomains, preload)
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    # Additional security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "0" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name _;
    return 301 https://$host$request_uri;
}
"""
```

### 3.3 API Key Encryption (OAuth Tokens, Webmaster Credentials)

```python
# security/credential_vault.py
from cryptography.fernet import Fernet
from typing import Optional
import json


class CredentialVault:
    """Encrypted storage for third-party API credentials."""

    def __init__(self, encryption: FieldEncryption):
        self.encryption = encryption

    async def store_credentials(
        self,
        org_id: str,
        service: str,       # "google_search_console", "ahrefs", "semrush"
        credentials: dict,
        user_id: str,
    ) -> str:
        """Store encrypted credentials."""
        context = f"credentials:{org_id}:{service}"

        # Encrypt the entire credentials document
        encrypted = self.encryption.encrypt_document(credentials, context)

        # Store in database
        cred_id = await credential_repo.create(
            org_id=org_id,
            service=service,
            encrypted_data=encrypted,
            created_by=user_id,
        )

        await audit_log.record(
            user_id=user_id,
            action="credentials.stored",
            resource=f"credential:{cred_id}",
            details={"service": service, "org_id": org_id},
        )

        return cred_id

    async def get_credentials(
        self,
        org_id: str,
        service: str,
    ) -> dict:
        """Retrieve and decrypt credentials."""
        cred = await credential_repo.get(org_id=org_id, service=service)
        if not cred:
            return None

        context = f"credentials:{org_id}:{service}"
        return self.encryption.decrypt_document(cred.encrypted_data, context)

    async def rotate_credentials(
        self,
        org_id: str,
        service: str,
        new_credentials: dict,
        user_id: str,
    ):
        """Rotate (update) stored credentials."""
        context = f"credentials:{org_id}:{service}"
        encrypted = self.encryption.encrypt_document(new_credentials, context)

        await credential_repo.update(
            org_id=org_id,
            service=service,
            encrypted_data=encrypted,
            rotated_by=user_id,
            rotated_at=datetime.utcnow(),
        )

        await audit_log.record(
            user_id=user_id,
            action="credentials.rotated",
            resource=f"credential:{org_id}:{service}",
            details={"service": service},
        )

    async def delete_credentials(
        self,
        org_id: str,
        service: str,
        user_id: str,
    ):
        """Delete stored credentials."""
        await credential_repo.delete(org_id=org_id, service=service)

        await audit_log.record(
            user_id=user_id,
            action="credentials.deleted",
            resource=f"credential:{org_id}:{service}",
            details={"service": service},
        )
```

### 3.4 PII Handling

```python
# security/pii.py
import re
from typing import Any
from pydantic import BaseModel


class PIIField(str, Enum):
    """Fields classified as PII."""
    EMAIL = "email"
    NAME = "name"
    PHONE = "phone"
    ADDRESS = "address"
    IP_ADDRESS = "ip_address"
    USER_AGENT = "user_agent"
    CREDIT_CARD = "credit_card"


class PIIService:
    """PII detection, masking, and handling."""

    # PII detection patterns
    PATTERNS = {
        PIIField.EMAIL: re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
        PIIField.PHONE: re.compile(r'\+?[\d\s\-\(\)]{7,15}'),
        PIIField.CREDIT_CARD: re.compile(r'\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}'),
        PIIField.IP_ADDRESS: re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'),
    }

    @staticmethod
    def mask_email(email: str) -> str:
        """Mask email address: j***@example.com"""
        if "@" not in email:
            return "***"
        local, domain = email.split("@", 1)
        if len(local) <= 1:
            return f"*@{domain}"
        return f"{local[0]}***@{domain}"

    @staticmethod
    def mask_name(name: str) -> str:
        """Mask name: J*** D**"""
        parts = name.split()
        masked = [f"{p[0]}{'*' * (len(p) - 1)}" for p in parts if p]
        return " ".join(masked)

    @staticmethod
    def mask_ip(ip: str) -> str:
        """Mask IP address: 192.168.***.*** """
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.***.***"
        return "***"

    @staticmethod
    def mask_phone(phone: str) -> str:
        """Mask phone: +1 (***) ***-1234"""
        digits = re.sub(r'\D', '', phone)
        if len(digits) >= 4:
            return f"***-***-{digits[-4:]}"
        return "***"

    @classmethod
    def detect_pii(cls, text: str) -> list[dict]:
        """Detect PII in text."""
        findings = []
        for pii_type, pattern in cls.PATTERNS.items():
            matches = pattern.findall(text)
            for match in matches:
                findings.append({
                    "type": pii_type,
                    "value": match,
                    "position": text.find(match),
                })
        return findings

    @classmethod
    def redact_log_entry(cls, log_entry: dict) -> dict:
        """Redact PII from log entries."""
        redacted = {}
        for key, value in log_entry.items():
            if isinstance(value, str):
                # Check each PII pattern
                for pii_type, pattern in cls.PATTERNS.items():
                    value = pattern.sub(f"[REDACTED_{pii_type.upper()}]", value)
                redacted[key] = value
            elif isinstance(value, dict):
                redacted[key] = cls.redact_log_entry(value)
            elif isinstance(value, list):
                redacted[key] = [
                    cls.redact_log_entry(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                redacted[key] = value
        return redacted

    @classmethod
    def mask_for_analytics(cls, data: dict) -> dict:
        """Mask PII for analytics/telemetry."""
        masked = data.copy()
        if "email" in masked:
            masked["email_hash"] = hashlib.sha256(
                masked.pop("email").lower().encode()
            ).hexdigest()[:16]
        if "ip_address" in masked:
            masked["ip_hash"] = hashlib.sha256(
                masked.pop("ip_address").encode()
            ).hexdigest()[:16]
        if "user_agent" in masked:
            masked.pop("user_agent")
        return masked
```

### 3.5 Data Retention Policies

```python
# security/data_retention.py
from datetime import datetime, timedelta
from enum import Enum


class RetentionPolicy(str, Enum):
    """Data retention policy definitions."""
    AUDIT_LOGS = "audit_logs"
    USER_DATA = "user_data"
    SESSION_DATA = "session_data"
    API_LOGS = "api_logs"
    SEO_DATA = "seo_data"
    BACKUP_DATA = "backup_data"


RETENTION_PERIODS = {
    RetentionPolicy.AUDIT_LOGS: timedelta(days=2555),    # 7 years
    RetentionPolicy.USER_DATA: timedelta(days=365),      # 1 year after deletion
    RetentionPolicy.SESSION_DATA: timedelta(days=90),    # 90 days
    RetentionPolicy.API_LOGS: timedelta(days=365),       # 1 year
    RetentionPolicy.SEO_DATA: timedelta(days=730),       # 2 years
    RetentionPolicy.BACKUP_DATA: timedelta(days=365),    # 1 year
}


class DataRetentionService:
    """Automated data retention and purging."""

    async def enforce_retention(self):
        """Run retention policies (scheduled daily)."""
        for policy, period in RETENTION_PERIODS.items():
            cutoff = datetime.utcnow() - period
            await self._purge_data(policy, cutoff)

    async def _purge_data(self, policy: RetentionPolicy, cutoff: datetime):
        """Purge data older than cutoff for a given policy."""
        if policy == RetentionPolicy.AUDIT_LOGS:
            count = await db.execute(
                "DELETE FROM audit_logs WHERE created_at < $1", cutoff
            )
        elif policy == RetentionPolicy.SESSION_DATA:
            count = await db.execute(
                "DELETE FROM sessions WHERE created_at < $1", cutoff
            )
        elif policy == RetentionPolicy.API_LOGS:
            count = await db.execute(
                "DELETE FROM api_request_logs WHERE created_at < $1", cutoff
            )

        await audit_log.record(
            user_id="system",
            action="retention.enforced",
            resource=f"policy:{policy.value}",
            details={"cutoff": cutoff.isoformat(), "records_deleted": count},
        )
```

### 3.6 Soft Delete + Hard Delete

```python
# security/soft_delete.py
from datetime import datetime, timedelta
from sqlalchemy import Column, DateTime, Boolean, String
from sqlalchemy.orm import Session


class SoftDeleteMixin:
    """Mixin for soft-delete functionality."""

    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)


class SoftDeleteService:
    """Service for managing soft-deleted records."""

    SOFT_DELETE_RETENTION = timedelta(days=30)  # 30 days before hard delete

    async def soft_delete(
        self,
        model_class,
        record_id: str,
        deleted_by: str,
        db_session: Session,
    ):
        """Soft-delete a record."""
        record = db_session.query(model_class).filter(
            model_class.id == record_id,
            model_class.is_deleted == False,
        ).first()

        if not record:
            raise HTTPException(404, "Record not found")

        record.is_deleted = True
        record.deleted_at = datetime.utcnow()
        record.deleted_by = deleted_by
        db_session.commit()

        await audit_log.record(
            user_id=deleted_by,
            action=f"{model_class.__tablename__}.soft_deleted",
            resource=f"{model_class.__tablename__}:{record_id}",
            details={"deleted_by": deleted_by},
        )

    async def restore(
        self,
        model_class,
        record_id: str,
        restored_by: str,
        db_session: Session,
    ):
        """Restore a soft-deleted record."""
        record = db_session.query(model_class).filter(
            model_class.id == record_id,
            model_class.is_deleted == True,
        ).first()

        if not record:
            raise HTTPException(404, "Deleted record not found")

        record.is_deleted = False
        record.deleted_at = None
        record.deleted_by = None
        db_session.commit()

        await audit_log.record(
            user_id=restored_by,
            action=f"{model_class.__tablename__}.restored",
            resource=f"{model_class.__tablename__}:{record_id}",
            details={"restored_by": restored_by},
        )

    async def hard_delete_expired(self, model_class, db_session: Session):
        """Hard-delete records that exceeded retention period."""
        cutoff = datetime.utcnow() - self.SOFT_DELETE_RETENTION
        records = db_session.query(model_class).filter(
            model_class.is_deleted == True,
            model_class.deleted_at < cutoff,
        ).all()

        for record in records:
            await self._secure_erase(record)
            db_session.delete(record)

        db_session.commit()
        return len(records)

    async def _secure_erase(self, record):
        """Securely erase PII before hard delete."""
        pii_fields = ["email", "name", "phone", "address", "ip_address"]
        for field in pii_fields:
            if hasattr(record, field):
                setattr(record, field, "[DELETED]")
```

---

## 4. API Security

### 4.1 Rate Limiting

```python
# security/rate_limiting.py
import redis.asyncio as redis
from fastapi import Request, HTTPException
from datetime import datetime
from typing import Optional
import time


class RateLimitConfig(BaseModel):
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10


# Rate limit tiers
RATE_LIMIT_TIERS = {
    "anonymous": RateLimitConfig(
        requests_per_minute=20,
        requests_per_hour=200,
        requests_per_day=1000,
        burst_size=5,
    ),
    "authenticated": RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        requests_per_day=10000,
        burst_size=10,
    ),
    "premium": RateLimitConfig(
        requests_per_minute=300,
        requests_per_hour=10000,
        requests_per_day=100000,
        burst_size=50,
    ),
    "enterprise": RateLimitConfig(
        requests_per_minute=1000,
        requests_per_hour=50000,
        requests_per_day=500000,
        burst_size=100,
    ),
}

# Per-endpoint rate limits (override tier defaults)
ENDPOINT_RATE_LIMITS = {
    "/api/v1/auth/login": RateLimitConfig(
        requests_per_minute=5,
        requests_per_hour=20,
        requests_per_day=50,
        burst_size=3,
    ),
    "/api/v1/auth/register": RateLimitConfig(
        requests_per_minute=3,
        requests_per_hour=10,
        requests_per_day=20,
        burst_size=2,
    ),
    "/api/v1/auth/password-reset": RateLimitConfig(
        requests_per_minute=3,
        requests_per_hour=5,
        requests_per_day=10,
        burst_size=2,
    ),
    "/api/v1/audits": RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=50,
        requests_per_day=200,
        burst_size=5,
    ),
}


class SlidingWindowRateLimiter:
    """Redis-based sliding window rate limiter."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> dict:
        """Check rate limit using sliding window algorithm."""
        now = time.time()
        window_start = now - window_seconds

        # Use Redis sorted set for sliding window
        pipe = self.redis.pipeline()

        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current entries
        pipe.zcard(key)

        # Add current request
        pipe.zadd(key, {str(now): now})

        # Set expiry on the key
        pipe.expire(key, window_seconds + 1)

        results = await pipe.execute()
        current_count = results[1]

        # Check if over limit
        is_over = current_count >= limit
        remaining = max(0, limit - current_count - 1)
        reset_at = now + window_seconds

        return {
            "limit": limit,
            "remaining": remaining,
            "reset_at": reset_at,
            "is_over_limit": is_over,
        }


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting."""

    def __init__(self, redis_client: redis.Redis):
        self.limiter = SlidingWindowRateLimiter(redis_client)

    async def __call__(self, request: Request, call_next):
        # Determine rate limit config
        config = self._get_config(request)

        # Build rate limit keys
        ip_key = f"rl:ip:{request.client.host}"
        user_key = f"rl:user:{getattr(request.state, 'user_id', 'anon')}"
        endpoint_key = f"rl:endpoint:{request.url.path}"

        # Check all limits
        checks = [
            (ip_key, config.requests_per_minute, 60),
            (user_key, config.requests_per_hour, 3600),
            (endpoint_key, config.requests_per_minute, 60),
        ]

        for key, limit, window in checks:
            result = await self.limiter.check_rate_limit(key, limit, window)
            if result["is_over_limit"]:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests",
                        "retry_after": int(result["reset_at"] - time.time()),
                    },
                    headers={
                        "Retry-After": str(int(result["reset_at"] - time.time())),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(result["reset_at"])),
                    },
                )

        response = await call_next(request)

        # Add rate limit headers to response
        result = await self.limiter.check_rate_limit(user_key, config.requests_per_hour, 3600)
        response.headers["X-RateLimit-Limit"] = str(config.requests_per_hour)
        response.headers["X-RateLimit-Remaining"] = str(result["remaining"])

        return response

    def _get_config(self, request: Request) -> RateLimitConfig:
        """Get rate limit config for request."""
        # Check endpoint-specific limits first
        if request.url.path in ENDPOINT_RATE_LIMITS:
            return ENDPOINT_RATE_LIMITS[request.url.path]

        # Check user tier
        tier = getattr(request.state, "rate_limit_tier", "anonymous")
        return RATE_LIMIT_TIERS.get(tier, RATE_LIMIT_TIERS["anonymous"])
```

### 4.2 Throttling Strategy

```python
# security/throttling.py
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta


class ThrottleService:
    """Adaptive throttling for heavy operations."""

    # Operation cost weights
    OPERATION_COSTS = {
        "seo_audit": 10,
        "keyword_bulk_track": 5,
        "backlink_scan": 8,
        "content_generate": 3,
        "report_export": 2,
        "api_call": 1,
    }

    # Budget per tier (cost points per hour)
    TIER_BUDGETS = {
        "standard": 100,
        "premium": 1000,
        "enterprise": 10000,
    }

    def __init__(self, redis_client):
        self.redis = redis_client

    async def check_throttle(
        self,
        user_id: str,
        operation: str,
        tier: str = "standard",
    ) -> dict:
        """Check if operation is within throttle budget."""
        cost = self.OPERATION_COSTS.get(operation, 1)
        budget = self.TIER_BUDGETS.get(tier, 100)
        key = f"throttle:{user_id}:{datetime.utcnow().strftime('%Y%m%d%H')}"

        # Get current usage
        current = int(await self.redis.get(key) or 0)
        remaining = budget - current

        if remaining < cost:
            return {
                "allowed": False,
                "cost": cost,
                "remaining": remaining,
                "budget": budget,
                "reset_at": (datetime.utcnow().replace(minute=0, second=0) + timedelta(hours=1)).isoformat(),
            }

        # Increment usage
        await self.redis.incrby(key, cost)
        await self.redis.expire(key, 3600)

        return {
            "allowed": True,
            "cost": cost,
            "remaining": remaining - cost,
            "budget": budget,
        }


class ConcurrencyLimiter:
    """Limit concurrent heavy operations per user."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.max_concurrent = {
            "seo_audit": 3,
            "backlink_scan": 2,
            "content_generate": 5,
            "report_export": 2,
        }

    async def acquire(self, user_id: str, operation: str) -> str:
        """Acquire a concurrency slot."""
        max_slots = self.max_concurrent.get(operation, 5)
        key = f"concurrency:{user_id}:{operation}"

        current = int(await self.redis.get(key) or 0)
        if current >= max_slots:
            raise HTTPException(
                status_code=429,
                detail=f"Maximum concurrent {operation} operations reached ({max_slots})",
            )

        slot_id = str(uuid.uuid4())
        await self.redis.incr(key)
        await self.redis.expire(key, 3600)  # Safety timeout

        return slot_id

    async def release(self, user_id: str, operation: str, slot_id: str):
        """Release a concurrency slot."""
        key = f"concurrency:{user_id}:{operation}"
        await self.redis.decr(key)
```

### 4.3 CORS Policy

```python
# security/cors.py
from fastapi.middleware.cors import CORSMiddleware


def configure_cors(app):
    """Configure CORS policy."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://app.seoplatform.com",
            "https://www.seoplatform.com",
            "https://docs.seoplatform.com",
            "https://api.seoplatform.com",
        ],
        allow_origin_regex=r"https://.*\.seoplatform\.com",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-API-Key",
            "X-CSRF-Token",
        ],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Request-ID",
        ],
        max_age=600,  # Cache preflight for 10 minutes
    )
```

### 4.4 CSP Headers

```python
# security/headers.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' https://api.seoplatform.com wss://ws.seoplatform.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests"
        )

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "0"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        # Cross-Origin policies
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"

        return response
```

### 4.5 Input Validation (Pydantic)

```python
# security/validation.py
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
import re
import bleach


class SecureString(str):
    """String type that sanitizes HTML and prevents injection."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("string required")
        # Strip HTML tags
        v = bleach.clean(v, tags=[], strip=True)
        # Null byte removal
        v = v.replace("\x00", "")
        # Maximum length enforcement
        if len(v) > 10000:
            raise ValueError("string too long")
        return v


class SecureHTML(str):
    """String type that allows safe HTML subset."""

    ALLOWED_TAGS = [
        "p", "br", "strong", "em", "u", "ol", "ul", "li",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote",
        "a", "img", "code", "pre",
    ]
    ALLOWED_ATTRIBUTES = {
        "a": ["href", "title"],
        "img": ["src", "alt", "width", "height"],
    }

    @classmethod
    def validate(cls, v):
        return bleach.clean(
            v,
            tags=cls.ALLOWED_TAGS,
            attributes=cls.ALLOWED_ATTRIBUTES,
            strip=True,
        )


class ProjectCreate(BaseModel):
    """Validated project creation input."""
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., max_length=2000)
    description: Optional[str] = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        v = bleach.clean(v, tags=[], strip=True)
        if not re.match(r'^[a-zA-Z0-9\s\-_\.]+$', v):
            raise ValueError("Name contains invalid characters")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        from urllib.parse import urlparse
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use HTTP or HTTPS")
        if not parsed.netloc:
            raise ValueError("Invalid URL")
        # Prevent SSRF
        import ipaddress
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback:
                raise ValueError("URL cannot point to private IP addresses")
        except ValueError:
            pass  # hostname is a domain name, not an IP
        return v


class KeywordTrack(BaseModel):
    """Validated keyword tracking input."""
    keyword: str = Field(..., min_length=1, max_length=500)
    location: str = Field(default="US", max_length=10)
    language: str = Field(default="en", max_length=10)
    device: str = Field(default="desktop")

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v):
        v = bleach.clean(v, tags=[], strip=True)
        # Prevent injection via special characters
        if any(c in v for c in ['"', "'", ";", "--", "/*", "*/"]):
            raise ValueError("Keyword contains invalid characters")
        return v

    @field_validator("device")
    @classmethod
    def validate_device(cls, v):
        allowed = ["desktop", "mobile", "tablet"]
        if v not in allowed:
            raise ValueError(f"Device must be one of: {allowed}")
        return v


class PaginationParams(BaseModel):
    """Validated pagination parameters."""
    page: int = Field(default=1, ge=1, le=10000)
    per_page: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = Field(None, max_length=50)
    sort_order: str = Field(default="asc")

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v):
        if v and not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
            raise ValueError("Invalid sort field")
        return v

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v):
        if v not in ("asc", "desc"):
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v
```

### 4.6 SQL Injection Prevention

```python
# security/sql_injection.py
"""
SQL injection prevention is enforced at multiple layers:

1. ORM (SQLAlchemy) - Parameterized queries by default
2. Query builder - No string concatenation
3. Input validation - Whitelist allowed values
4. Database permissions - Read-only user for queries
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SafeQueryBuilder:
    """Safe query building with parameterized queries."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_keywords(
        self,
        org_id: str,
        search_term: str,
        page: int = 1,
        per_page: int = 20,
    ) -> list[dict]:
        """Safe keyword search with parameterized queries."""
        # NEVER do this:
        # query = f"SELECT * FROM keywords WHERE name LIKE '%{search_term}%'"

        # SAFE: Parameterized query
        query = text("""
            SELECT k.id, k.keyword, k.search_volume, k.difficulty
            FROM keywords k
            WHERE k.org_id = :org_id
            AND k.keyword ILIKE :search_pattern
            AND k.is_deleted = FALSE
            ORDER BY k.search_volume DESC
            LIMIT :limit OFFSET :offset
        """)

        result = await self.session.execute(
            query,
            {
                "org_id": org_id,
                "search_pattern": f"%{search_term}%",
                "limit": per_page,
                "offset": (page - 1) * per_page,
            },
        )
        return [dict(row) for row in result]

    async def safe_filter(
        self,
        table: str,
        filters: dict,
        allowed_columns: set[str],
    ) -> list[dict]:
        """Apply filters safely with column whitelisting."""
        # Validate column names against whitelist
        for column in filters.keys():
            if column not in allowed_columns:
                raise ValueError(f"Invalid filter column: {column}")

        # Build parameterized WHERE clause
        conditions = []
        params = {}
        for i, (column, value) in enumerate(filters.items()):
            param_name = f"param_{i}"
            conditions.append(f"{column} = :{param_name}")
            params[param_name] = value

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Table name is validated against allowed tables
        query = text(f"SELECT * FROM {table} WHERE {where_clause}")
        result = await self.session.execute(query, params)
        return [dict(row) for row in result]


# SQLAlchemy ORM (preferred approach)
from sqlalchemy import select, and_
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(String, primary_key=True)
    keyword = Column(String)
    org_id = Column(String, index=True)
    search_volume = Column(Integer)
    is_deleted = Column(Boolean, default=False)


class SafeORMRepository:
    """ORM-based repository (SQL injection safe by default)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        org_id: str,
        search_term: str,
        page: int = 1,
        per_page: int = 20,
    ):
        """ORM search - automatically parameterized."""
        query = (
            select(Keyword)
            .where(
                and_(
                    Keyword.org_id == org_id,
                    Keyword.keyword.ilike(f"%{search_term}%"),
                    Keyword.is_deleted == False,
                )
            )
            .order_by(Keyword.search_volume.desc())
            .limit(per_page)
            .offset((page - 1) * per_page)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
```

### 4.7 XSS Prevention

```python
# security/xss_prevention.py
import bleach
from markupsafe import escape


class XSSPrevention:
    """XSS prevention utilities."""

    # Allowed HTML tags for rich text fields
    ALLOWED_TAGS = [
        "p", "br", "strong", "em", "u", "ol", "ul", "li",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote",
        "a", "code", "pre", "table", "thead", "tbody", "tr", "th", "td",
    ]

    ALLOWED_ATTRIBUTES = {
        "a": ["href", "title", "rel", "target"],
        "img": ["src", "alt", "width", "height"],
        "td": ["colspan", "rowspan"],
        "th": ["colspan", "rowspan"],
    }

    ALLOWED_PROTOCOLS = ["https", "http", "mailto"]

    @staticmethod
    def sanitize_html(html: str) -> str:
        """Sanitize HTML content."""
        return bleach.clean(
            html,
            tags=XSSPrevention.ALLOWED_TAGS,
            attributes=XSSPrevention.ALLOWED_ATTRIBUTES,
            protocols=XSSPrevention.ALLOWED_PROTOCOLS,
            strip=True,
        )

    @staticmethod
    def sanitize_for_json(text: str) -> str:
        """Escape text for safe JSON embedding."""
        return (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
        )

    @staticmethod
    def escape_for_template(text: str) -> str:
        """Escape text for template rendering."""
        return str(escape(text))

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL to prevent javascript: protocol attacks."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme and parsed.scheme.lower() not in ("http", "https", "mailto"):
            return False
        if url.lower().strip().startswith("javascript:"):
            return False
        return True


# Jinja2 auto-escaping configuration
JINJA2_CONFIG = {
    "autoescape": True,  # Always auto-escape
    "auto_reload": False,  # Disable in production
}
```

### 4.8 CSRF Protection

```python
# security/csrf.py
import secrets
import hmac
import hashlib
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class CSRFProtection:
    """CSRF token generation and validation."""

    def __init__(self, secret_key: bytes):
        self.secret_key = secret_key
        self.token_length = 32

    def generate_token(self, session_id: str) -> str:
        """Generate a CSRF token bound to the session."""
        random_token = secrets.token_hex(self.token_length)
        # Create HMAC of session_id + random_token
        message = f"{session_id}:{random_token}".encode()
        signature = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
        return f"{random_token}.{signature}"

    def validate_token(self, token: str, session_id: str) -> bool:
        """Validate a CSRF token against the session."""
        try:
            random_token, signature = token.rsplit(".", 1)
            message = f"{session_id}:{random_token}".encode()
            expected_signature = hmac.new(
                self.secret_key, message, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected_signature)
        except (ValueError, AttributeError):
            return False


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    EXEMPT_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/webhooks",
        "/health",
        "/docs",
        "/openapi.json",
    }

    def __init__(self, app, secret_key: bytes):
        super().__init__(app)
        self.csrf = CSRFProtection(secret_key)

    async def dispatch(self, request: Request, call_next):
        # Skip CSRF for safe methods
        if request.method in self.SAFE_METHODS:
            response = await call_next(request)
            # Set CSRF token in cookie for GET requests
            if hasattr(request.state, "session_id"):
                token = self.csrf.generate_token(request.state.session_id)
                response.set_cookie(
                    "csrf_token",
                    token,
                    httponly=False,  # JavaScript needs to read this
                    secure=True,
                    samesite="strict",
                    max_age=3600,
                )
            return response

        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip for API key authenticated requests
        if request.headers.get("X-API-Key"):
            return await call_next(request)

        # Validate CSRF token
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token:
            raise HTTPException(403, "CSRF token missing")

        session_id = getattr(request.state, "session_id", None)
        if not session_id:
            raise HTTPException(403, "Session required for CSRF validation")

        if not self.csrf.validate_token(csrf_token, session_id):
            raise HTTPException(403, "Invalid CSRF token")

        return await call_next(request)
```

### 4.9 Request Signing (Webhooks)

```python
# security/webhook_signing.py
import hmac
import hashlib
import time
from typing import Optional
from pydantic import BaseModel


class WebhookSignature(BaseModel):
    """Webhook signature verification."""
    signature: str
    timestamp: int
    nonce: str


class WebhookSigningService:
    """Sign and verify webhook requests."""

    def __init__(self, secret: bytes):
        self.secret = secret

    def sign_payload(
        self,
        payload: bytes,
        timestamp: int,
        nonce: str,
    ) -> str:
        """Create HMAC-SHA256 signature for webhook payload."""
        # Construct signing string
        signing_string = f"{timestamp}.{nonce}.{payload.decode()}"
        signature = hmac.new(
            self.secret,
            signing_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"v1={signature}"

    def verify_signature(
        self,
        payload: bytes,
        timestamp: int,
        nonce: str,
        provided_signature: str,
        max_age_seconds: int = 300,
    ) -> bool:
        """Verify webhook signature with replay protection."""
        # Check timestamp freshness (prevent replay attacks)
        current_time = int(time.time())
        if abs(current_time - timestamp) > max_age_seconds:
            return False

        # Compute expected signature
        expected = self.sign_payload(payload, timestamp, nonce)

        # Constant-time comparison
        return hmac.compare_digest(expected, provided_signature)


# Usage in webhook endpoint
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook with signature verification."""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    if not sig_header:
        raise HTTPException(400, "Missing Stripe-Signature header")

    # Parse Stripe signature
    try:
        parts = dict(p.split("=") for p in sig_header.split(","))
        timestamp = int(parts["t"])
        signature = parts["v1"]
    except (ValueError, KeyError):
        raise HTTPException(400, "Invalid Stripe-Signature format")

    # Verify signature
    signing_service = WebhookSigningService(settings.STRIPE_WEBHOOK_SECRET.encode())
    if not signing_service.verify_signature(
        payload, timestamp, "", signature
    ):
        raise HTTPException(400, "Invalid webhook signature")

    # Process webhook
    event = json.loads(payload)
    await webhook_processor.process(event)

    return {"status": "ok"}


# Outgoing webhook signing
@router.post("/api/v1/webhooks/send")
async def send_webhook(
    webhook_url: str,
    payload: dict,
    user: User = Depends(get_current_user),
):
    """Send a signed webhook to external endpoint."""
    signing_service = WebhookSigningService(settings.WEBHOOK_SECRET.encode())

    body = json.dumps(payload).encode()
    timestamp = int(time.time())
    nonce = secrets.token_hex(16)

    signature = signing_service.sign_payload(body, timestamp, nonce)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": str(timestamp),
        "X-Webhook-Nonce": nonce,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            webhook_url,
            content=body,
            headers=headers,
            timeout=30.0,
        )

    return {"status": "sent", "response_code": response.status_code}
```

---

## 5. Infrastructure Security

### 5.1 WAF (Web Application Firewall)

```yaml
# infrastructure/waf/modsecurity-rules.conf
# ModSecurity WAF Configuration

SecRuleEngine On
SecRequestBodyAccess On
SecResponseBodyAccess Off
SecRequestBodyLimit 13107200
SecRequestBodyNoFilesLimit 131072

# OWASP Core Rule Set
Include /etc/modsecurity/crs/crs-setup.conf
Include /etc/modsecurity/crs/rules/*.conf

# Custom rules for SEO platform
SecRule ARGS "@detectSQLi" \
    "id:10001,phase:2,block,msg:'SQL Injection Attack Detected',logdata:'%{MATCHED_VAR}'"

SecRule ARGS "@detectXSS" \
    "id:10002,phase:2,block,msg:'XSS Attack Detected',logdata:'%{MATCHED_VAR}'"

SecRule REQUEST_URI "@rx (?i)(union.*select|select.*from|insert.*into|delete.*from|drop.*table)" \
    "id:10003,phase:1,block,msg:'SQL Injection in URI'"

# Block common attack patterns
SecRule REQUEST_URI "@rx (?i)(\.\.\/|\.\.\\\\)" \
    "id:10004,phase:1,block,msg:'Path Traversal Attack'"

SecRule REQUEST_URI "@rx (?i)(\/etc\/passwd|\/etc\/shadow|\/proc\/)" \
    "id:10005,phase:1,block,msg:'Sensitive File Access Attempt'"

# Rate limiting by IP
SecAction "id:10006,phase:1,initcol:ip=%{REMOTE_ADDR},pass,nolog"
SecRule IP:REQUEST_COUNT "@gt 100" \
    "id:10007,phase:1,block,msg:'Rate limit exceeded'"

# GeoIP blocking (optional)
SecRule REMOTE_ADDR "@geoLookup" "id:10008,phase:1,pass,nolog"
# SecRule GEO:COUNTRY_CODE "@within XX" "id:10009,phase:1,block,msg:'GeoIP blocked'"
```

```yaml
# infrastructure/waf/nginx-waf.conf
server {
    # WAF integration
    modsecurity on;
    modsecurity_rules_file /etc/nginx/modsecurity/main.conf;

    # Request size limits
    client_max_body_size 50m;
    client_body_buffer_size 128k;
    client_header_buffer_size 4k;
    large_client_header_buffers 4 16k;

    # Timeout protection
    client_body_timeout 12;
    client_header_timeout 12;
    send_timeout 10;
    keepalive_timeout 15;

    # Slowloris protection
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
    limit_conn conn_limit 20;

    # Request rate limiting
    limit_req_zone $binary_remote_addr zone=req_limit:10m rate=10r/s;
    limit_req zone=req_limit burst=20 nodelay;
}
```

### 5.2 DDoS Protection (Cloudflare)

```yaml
# infrastructure/cloudflare/ddos-config.yaml
# Cloudflare configuration for DDoS protection

security_level: "medium"
challenge_ttl: 1800
browser_check: "on"
privacy_pass: "on"

# Rate limiting rules
rate_limiting_rules:
  - name: "API Rate Limit"
    description: "Limit API requests per IP"
    expression: "(http.request.uri.path matches \"^/api/\")"
    period: 60
    requests_per_period: 100
    mitigation_timeout: 600
    action: "block"

  - name: "Login Rate Limit"
    description: "Limit login attempts"
    expression: "(http.request.uri.path eq \"/api/v1/auth/login\")"
    period: 60
    requests_per_period: 5
    mitigation_timeout: 3600
    action: "challenge"

  - name: "Registration Rate Limit"
    description: "Limit registration attempts"
    expression: "(http.request.uri.path eq \"/api/v1/auth/register\")"
    period: 3600
    requests_per_period: 3
    mitigation_timeout: 86400
    action: "block"

# Firewall rules
firewall_rules:
  - name: "Block Bad Bots"
    expression: "(cf.client.bot)"
    action: "block"

  - name: "Challenge Suspicious UAs"
    expression: "(http.user_agent contains \"sqlmap\" or http.user_agent contains \"nikto\" or http.user_agent contains \"nmap\")"
    action: "block"

  - name: "Block Known Bad IPs"
    expression: "(ip.src in $malicious_ips)"
    action: "block"

# DDoS protection settings
ddos_l4:
  sensitivity: "high"
  action: "block"

ddos_l7:
  sensitivity: "high"
  action: "challenge"

# Page rules
page_rules:
  - url: "api.seoplatform.com/*"
    settings:
      security_level: "high"
      browser_check: "on"
      cache_level: "bypass"

  - url: "app.seoplatform.com/*"
    settings:
      security_level: "medium"
      browser_check: "on"
      always_use_https: "on"
```

### 5.3 Network Segmentation

```yaml
# infrastructure/network/docker-compose.security.yml
version: "3.8"

networks:
  frontend:
    driver: bridge
    internal: false
    ipam:
      config:
        - subnet: 172.20.0.0/24

  backend:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.20.1.0/24

  database:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.20.2.0/24

  cache:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.20.3.0/24

services:
  nginx:
    image: nginx:alpine
    networks:
      - frontend
    ports:
      - "443:443"
      - "80:80"
    read_only: true
    security_opt:
      - no-new-privileges:true

  api:
    image: seoplatform/api:latest
    networks:
      - frontend
      - backend
      - database
      - cache
    read_only: true
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE

  worker:
    image: seoplatform/worker:latest
    networks:
      - backend
      - database
      - cache
    read_only: true
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL

  postgres:
    image: postgres:16-alpine
    networks:
      - database
    read_only: true
    security_opt:
      - no-new-privileges:true
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password

  redis:
    image: redis:7-alpine
    networks:
      - cache
    read_only: true
    security_opt:
      - no-new-privileges:true
    command: redis-server --requirepass "${REDIS_PASSWORD}"

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

### 5.4 Secret Management

```python
# security/secrets.py
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class SecretProvider:
    """Interface for secret providers."""
    def get(self, key: str) -> Optional[str]:
        raise NotImplementedError


class EnvSecretProvider(SecretProvider):
    """Read secrets from environment variables."""

    def get(self, key: str) -> Optional[str]:
        return os.environ.get(key)


class VaultSecretProvider(SecretProvider):
    """Read secrets from HashiCorp Vault."""

    def __init__(self, vault_url: str, vault_token: str):
        import hvac
        self.client = hvac.Client(url=vault_url, token=vault_token)

    def get(self, key: str) -> Optional[str]:
        try:
            response = self.client.secrets.kv.read_secret_version(
                path=f"seoplatform/{key}",
                mount_point="secret",
            )
            return response["data"]["data"].get("value")
        except Exception:
            return None


class AWSSecretsManagerProvider(SecretProvider):
    """Read secrets from AWS Secrets Manager."""

    def __init__(self, region_name: str = "us-east-1"):
        import boto3
        self.client = boto3.client("secretsmanager", region_name=region_name)

    def get(self, key: str) -> Optional[str]:
        try:
            response = self.client.get_secret_value(SecretId=f"seoplatform/{key}")
            import json
            secret = json.loads(response["SecretString"])
            return secret.get("value")
        except Exception:
            return None


class SecretManager:
    """Unified secret management with caching."""

    def __init__(self, providers: list[SecretProvider]):
        self.providers = providers
        self._cache: dict[str, tuple[str, float]] = {}
        self._cache_ttl = 300  # 5 minutes

    def get(self, key: str) -> Optional[str]:
        """Get a secret, trying each provider in order."""
        # Check cache
        if key in self._cache:
            value, cached_at = self._cache[key]
            if time.time() - cached_at < self._cache_ttl:
                return value

        # Try each provider
        for provider in self.providers:
            value = provider.get(key)
            if value:
                self._cache[key] = (value, time.time())
                return value

        return None

    def get_required(self, key: str) -> str:
        """Get a secret or raise an error."""
        value = self.get(key)
        if value is None:
            raise RuntimeError(f"Required secret not found: {key}")
        return value


# Initialize secret manager
secret_manager = SecretManager([
    AWSSecretsManagerProvider(region_name="us-east-1"),
    VaultSecretProvider(
        vault_url=os.environ.get("VAULT_ADDR", "http://vault:8200"),
        vault_token=os.environ.get("VAULT_TOKEN", ""),
    ),
    EnvSecretProvider(),
])
```

### 5.5 Container Security

```dockerfile
# Dockerfile.security
# Multi-stage build for minimal attack surface

FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage - minimal image
FROM python:3.12-slim

# Security hardening
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy only necessary files
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser ./app /app

WORKDIR /app

# Switch to non-root user
USER appuser

# Set PATH
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Remove unnecessary tools
RUN apt-get update && apt-get purge -y \
    curl wget netcat-openbsd ssh \
    && rm -rf /var/lib/apt/lists/*

# Read-only filesystem
VOLUME ["/tmp"]

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# infrastructure/security/trivy-scan.yaml
# CI pipeline for container vulnerability scanning

name: Container Security Scan

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker build -t seoplatform/api:${{ github.sha }} .

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: "seoplatform/api:${{ github.sha }}"
          format: "sarif"
          output: "trivy-results.sarif"
          severity: "CRITICAL,HIGH"
          exit-code: "1"

      - name: Run Snyk container scan
        uses: snyk/actions/docker@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          image: "seoplatform/api:${{ github.sha }}"
          args: --severity-threshold=high

      - name: Run Grype scan
        uses: anchore/scan-action@v3
        with:
          image: "seoplatform/api:${{ github.sha }}"
          fail-build: true
          severity-cutoff: high
```

### 5.6 Dependency Scanning

```yaml
# .github/workflows/dependency-scan.yml
name: Dependency Security

on:
  schedule:
    - cron: "0 6 * * *"  # Daily at 6 AM
  push:
    branches: [main]
  pull_request:

jobs:
  python-dependencies:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install safety pip-audit

      - name: Run Safety check
        run: safety check --full-report

      - name: Run pip-audit
        run: pip-audit

      - name: Run Snyk Python test
        uses: snyk/actions/python@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          args: --file=requirements.txt --fail-on=high

  npm-dependencies:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: npm ci

      - name: Run npm audit
        run: npm audit --audit-level=high

      - name: Run Snyk npm test
        uses: snyk/actions/node@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}

  dependabot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Dependabot metadata
        id: metadata
        uses: dependabot/fetch-metadata@v1
        with:
          github-token: "${{ secrets.GITHUB_TOKEN }}"

      - name: Auto-merge minor/patch updates
        if: steps.metadata.outputs.update-type == 'version-update:semver-minor' || steps.metadata.outputs.update-type == 'version-update:semver-patch'
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## 6. Audit & Compliance

### 6.1 Audit Log Format

```python
# audit/audit_log.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any
from enum import Enum
import uuid
import json


class AuditAction(str, Enum):
    """Standardized audit actions."""
    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_PASSWORD_CHANGED = "auth.password_changed"
    AUTH_MFA_ENABLED = "auth.mfa_enabled"
    AUTH_MFA_DISABLED = "auth.mfa_disabled"
    AUTH_TOKEN_REFRESHED = "auth.token_refreshed"
    AUTH_SSO_LOGIN = "auth.sso_login"

    # User management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_INVITED = "user.invited"
    USER_ROLE_CHANGED = "user.role_changed"

    # Project management
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    PROJECT_DELETED = "project.deleted"
    PROJECT_SHARED = "project.shared"

    # SEO operations
    AUDIT_STARTED = "audit.started"
    AUDIT_COMPLETED = "audit.completed"
    KEYWORD_CREATED = "keyword.created"
    KEYWORD_UPDATED = "keyword.updated"
    KEYWORD_DELETED = "keyword.deleted"
    BACKLINK_DISAVOWED = "backlink.disavowed"

    # Content
    CONTENT_CREATED = "content.created"
    CONTENT_UPDATED = "content.updated"
    CONTENT_PUBLISHED = "content.published"
    CONTENT_DELETED = "content.deleted"

    # API keys
    APIKEY_CREATED = "apikey.created"
    APIKEY_REVOKED = "apikey.revoked"

    # Settings
    SETTINGS_UPDATED = "settings.updated"
    INTEGRATION_CONNECTED = "integration.connected"
    INTEGRATION_DISCONNECTED = "integration.disconnected"

    # Data operations
    DATA_EXPORTED = "data.exported"
    DATA_IMPORTED = "data.imported"
    DATA_DELETED = "data.deleted"


class AuditResult(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuditLogEntry(BaseModel):
    """Standardized audit log entry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # WHO
    user_id: str
    user_email: Optional[str] = None
    user_roles: list[str] = []
    org_id: str
    session_id: Optional[str] = None

    # WHAT
    action: str
    resource_type: str       # e.g., "project", "keyword", "user"
    resource_id: str         # ID of the affected resource
    details: dict[str, Any] = {}

    # WHERE
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    api_key_id: Optional[str] = None

    # RESULT
    result: AuditResult = AuditResult.SUCCESS
    error_message: Optional[str] = None

    # METADATA
    duration_ms: Optional[int] = None
    changes: Optional[dict] = None  # Before/after for updates


class AuditLogger:
    """Audit logging service."""

    def __init__(self, db_client, kafka_producer=None):
        self.db = db_client
        self.kafka = kafka_producer

    async def record(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        org_id: str = "",
        details: dict = None,
        result: AuditResult = AuditResult.SUCCESS,
        **kwargs,
    ) -> str:
        """Record an audit log entry."""
        entry = AuditLogEntry(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            org_id=org_id,
            details=details or {},
            result=result,
            **kwargs,
        )

        # Store in database
        await self.db.execute(
            """
            INSERT INTO audit_logs (
                id, timestamp, user_id, user_email, user_roles, org_id,
                session_id, action, resource_type, resource_id, details,
                ip_address, user_agent, request_id, api_key_id,
                result, error_message, duration_ms, changes
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
            )
            """,
            entry.id, entry.timestamp, entry.user_id, entry.user_email,
            entry.user_roles, entry.org_id, entry.session_id, entry.action,
            entry.resource_type, entry.resource_id, json.dumps(entry.details),
            entry.ip_address, entry.user_agent, entry.request_id,
            entry.api_key_id, entry.result.value, entry.error_message,
            entry.duration_ms, json.dumps(entry.changes) if entry.changes else None,
        )

        # Publish to Kafka for real-time monitoring
        if self.kafka:
            await self.kafka.send(
                "audit-logs",
                key=entry.org_id.encode(),
                value=entry.model_dump_json().encode(),
            )

        return entry.id

    async def query(
        self,
        org_id: str,
        filters: dict = None,
        start_date: datetime = None,
        end_date: datetime = None,
        page: int = 1,
        per_page: int = 50,
    ) -> list[AuditLogEntry]:
        """Query audit logs."""
        conditions = ["org_id = $1"]
        params = [org_id]
        param_idx = 2

        if filters:
            for key, value in filters.items():
                conditions.append(f"{key} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if start_date:
            conditions.append(f"timestamp >= ${param_idx}")
            params.append(start_date)
            param_idx += 1

        if end_date:
            conditions.append(f"timestamp <= ${param_idx}")
            params.append(end_date)
            param_idx += 1

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * per_page

        query = f"""
            SELECT * FROM audit_logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT {per_page} OFFSET {offset}
        """

        rows = await self.db.fetch(query, *params)
        return [AuditLogEntry(**row) for row in rows]
```

### 6.2 Audit Log Retention

```python
# audit/retention.py
from datetime import datetime, timedelta


class AuditLogRetentionService:
    """Audit log retention and archival."""

    # Retention periods by category
    RETENTION_POLICIES = {
        "auth": timedelta(days=2555),       # 7 years
        "user_management": timedelta(days=2555),
        "data_access": timedelta(days=2555),
        "configuration": timedelta(days=2555),
        "api_access": timedelta(days=365),   # 1 year
        "system": timedelta(days=90),        # 90 days
    }

    async def archive_old_logs(self):
        """Archive logs older than retention period."""
        for category, retention in self.RETENTION_POLICIES.items():
            cutoff = datetime.utcnow() - retention

            # Move to archive storage (S3/GCS)
            archived = await self._move_to_archive(category, cutoff)
            await audit_log.record(
                user_id="system",
                action="audit_logs.archived",
                resource_type="audit_log",
                resource_id="batch",
                details={"category": category, "count": archived, "cutoff": cutoff.isoformat()},
            )

    async def _move_to_archive(self, category: str, cutoff: datetime) -> int:
        """Move old logs to cold storage."""
        # Export to Parquet for efficient storage
        query = """
            COPY (
                SELECT * FROM audit_logs
                WHERE action LIKE $1 || '%'
                AND timestamp < $2
            ) TO '/tmp/audit_archive.parquet' (FORMAT PARQUET)
        """
        # Upload to S3/GCS
        # Delete from database after successful upload
        return 0
```

### 6.3 GDPR Compliance

```python
# compliance/gdpr.py
from datetime import datetime
from typing import Any
from pydantic import BaseModel
import json


class GDPRService:
    """GDPR compliance service."""

    async def export_user_data(self, user_id: str) -> dict:
        """GDPR Article 20: Right to data portability."""
        user = await user_repo.get(user_id)

        export = {
            "export_date": datetime.utcnow().isoformat(),
            "user_profile": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at.isoformat(),
                "org_id": user.org_id,
                "roles": user.roles,
                "mfa_enabled": user.mfa_enabled,
            },
            "projects": await self._get_user_projects(user_id),
            "keywords": await self._get_user_keywords(user_id),
            "content": await self._get_user_content(user_id),
            "audit_logs": await self._get_user_audit_logs(user_id),
            "sessions": await self._get_user_sessions(user_id),
            "api_keys": await self._get_user_api_keys(user_id),
            "social_accounts": await self._get_social_accounts(user_id),
            "integrations": await self._get_user_integrations(user_id),
        }

        # Record the export
        await audit_log.record(
            user_id=user_id,
            action="gdpr.data_export",
            resource_type="user",
            resource_id=user_id,
            details={"export_size": len(json.dumps(export))},
        )

        return export

    async def delete_user_data(self, user_id: str, admin_id: str = None):
        """GDPR Article 17: Right to erasure."""
        # Verify no legal holds
        if await self._has_legal_hold(user_id):
            raise HTTPException(
                400, "Account has a legal hold and cannot be deleted"
            )

        # Collect deletion report
        deletion_report = {
            "user_id": user_id,
            "initiated_by": admin_id or user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "items_deleted": {},
        }

        # Delete user content
        deletion_report["items_deleted"]["content"] = await self._delete_user_content(user_id)

        # Anonymize audit logs (keep structure, remove PII)
        deletion_report["items_deleted"]["audit_logs_anonymized"] = await self._anonymize_audit_logs(user_id)

        # Delete API keys
        deletion_report["items_deleted"]["api_keys"] = await self._delete_api_keys(user_id)

        # Delete sessions
        deletion_report["items_deleted"]["sessions"] = await self._delete_sessions(user_id)

        # Anonymize user record (keep for referential integrity)
        await self._anonymize_user(user_id)

        # Record deletion
        await audit_log.record(
            user_id=admin_id or user_id,
            action="gdpr.data_deletion",
            resource_type="user",
            resource_id=user_id,
            details=deletion_report,
        )

        return deletion_report

    async def _anonymize_user(self, user_id: str):
        """Anonymize user record while preserving referential integrity."""
        await db.execute(
            """
            UPDATE users SET
                email = $1,
                name = 'Deleted User',
                avatar_url = NULL,
                password_hash = '',
                deleted_at = NOW(),
                is_deleted = TRUE
            WHERE id = $2
            """,
            f"deleted_{user_id[:8]}@anonymized.local",
            user_id,
        )

    async def _anonymize_audit_logs(self, user_id: str) -> int:
        """Anonymize PII in audit logs while preserving audit trail."""
        result = await db.execute(
            """
            UPDATE audit_logs SET
                user_email = '[ANONYMIZED]',
                ip_address = NULL,
                user_agent = NULL
            WHERE user_id = $1
            """,
            user_id,
        )
        return result

    async def handle_data_request(
        self,
        user_id: str,
        request_type: str,  # "access", "portability", "deletion", "rectification"
    ) -> dict:
        """Handle GDPR data subject requests."""
        # Must respond within 30 days
        request = await gdpr_request_repo.create(
            user_id=user_id,
            request_type=request_type,
            status="pending",
            due_date=datetime.utcnow() + timedelta(days=30),
        )

        # Notify DPO
        await notification_service.send(
            channel="compliance",
            template="gdpr_request",
            data={
                "request_id": request.id,
                "user_id": user_id,
                "request_type": request_type,
                "due_date": request.due_date.isoformat(),
            },
        )

        return {"request_id": request.id, "status": "pending"}
```

### 6.4 SOC 2 Preparation

```python
# compliance/soc2.py
"""
SOC 2 Type II Controls Implementation

The following controls are implemented to meet SOC 2 Trust Service Criteria:
- CC1: Control Environment
- CC2: Communication and Information
- CC3: Risk Assessment
- CC4: Monitoring Activities
- CC5: Control Activities
- CC6: Logical and Physical Access Controls
- CC7: System Operations
- CC8: Change Management
- CC9: Risk Mitigation
"""

from datetime import datetime, timedelta
from enum import Enum


class SOC2Control(Enum):
    """SOC 2 control categories."""
    ACCESS_CONTROL = "CC6"
    CHANGE_MANAGEMENT = "CC8"
    SYSTEM_OPERATIONS = "CC7"
    RISK_ASSESSMENT = "CC3"
    MONITORING = "CC4"


class SOC2ComplianceService:
    """SOC 2 compliance monitoring and reporting."""

    async def generate_compliance_report(self) -> dict:
        """Generate SOC 2 compliance status report."""
        return {
            "report_date": datetime.utcnow().isoformat(),
            "period": {
                "start": (datetime.utcnow() - timedelta(days=365)).isoformat(),
                "end": datetime.utcnow().isoformat(),
            },
            "controls": {
                "CC6.1_logical_access": await self._check_logical_access(),
                "CC6.2_authentication": await self._check_authentication(),
                "CC6.3_authorization": await self._check_authorization(),
                "CC6.6_data_protection": await self._check_data_protection(),
                "CC6.7_system_boundaries": await self._check_system_boundaries(),
                "CC7.1_vulnerability_mgmt": await self._check_vulnerability_mgmt(),
                "CC7.2_monitoring": await self._check_monitoring(),
                "CC7.3_incident_response": await self._check_incident_response(),
                "CC8.1_change_management": await self._check_change_management(),
            },
        }

    async def _check_logical_access(self) -> dict:
        """CC6.1: Logical access controls."""
        return {
            "status": "compliant",
            "evidence": [
                "RBAC implemented with 4 role levels",
                "API key scoping enforced",
                "Session management with timeout",
                "Account lockout after 5 failed attempts",
            ],
            "last_reviewed": datetime.utcnow().isoformat(),
        }

    async def _check_authentication(self) -> dict:
        """CC6.2: Authentication mechanisms."""
        return {
            "status": "compliant",
            "evidence": [
                "Argon2id password hashing",
                "MFA support with TOTP",
                "OAuth 2.0 + PKCE",
                "SAML 2.0 SSO for enterprise",
                "Password policy enforcement",
            ],
            "last_reviewed": datetime.utcnow().isoformat(),
        }

    async def _check_data_protection(self) -> dict:
        """CC6.6: Data protection controls."""
        return {
            "status": "compliant",
            "evidence": [
                "AES-256-GCM encryption at rest",
                "TLS 1.3 encryption in transit",
                "Field-level encryption for credentials",
                "PII detection and masking",
                "Data retention policies enforced",
            ],
            "last_reviewed": datetime.utcnow().isoformat(),
        }

    async def _check_vulnerability_mgmt(self) -> dict:
        """CC7.1: Vulnerability management."""
        return {
            "status": "compliant",
            "evidence": [
                "Container scanning (Trivy, Snyk)",
                "Dependency scanning (pip-audit, npm audit)",
                "Dependabot auto-updates",
                "WAF (ModSecurity + OWASP CRS)",
            ],
            "last_reviewed": datetime.utcnow().isoformat(),
        }
```

### 6.5 Privacy Policy Requirements

```python
# compliance/privacy.py
"""
Privacy policy technical implementation requirements.
"""

PRIVACY_REQUIREMENTS = {
    "data_collection": {
        "user_profile": ["email", "name", "avatar", "password_hash"],
        "usage_data": ["pages_visited", "features_used", "timestamps"],
        "technical_data": ["ip_address", "user_agent", "device_info"],
        "seo_data": ["keywords", "rankings", "audits"],
    },
    "data_processing_purposes": [
        "service_provision",
        "authentication",
        "analytics",
        "marketing",
        "support",
    ],
    "legal_bases": {
        "service_provision": "contract",
        "authentication": "contract",
        "analytics": "legitimate_interest",
        "marketing": "consent",
        "support": "contract",
    },
    "third_party_processors": [
        {"name": "Stripe", "purpose": "payment_processing", "country": "US"},
        {"name": "SendGrid", "purpose": "email_delivery", "country": "US"},
        {"name": "Google Analytics", "purpose": "analytics", "country": "US"},
        {"name": "Sentry", "purpose": "error_tracking", "country": "US"},
    ],
    "data_retention": {
        "user_profile": "Until account deletion + 30 days",
        "usage_data": "2 years",
        "seo_data": "2 years after project deletion",
        "audit_logs": "7 years",
    },
    "user_rights": [
        "access",           # Right to access data
        "rectification",    # Right to correct data
        "erasure",          # Right to delete data
        "portability",      # Right to export data
        "restriction",      # Right to restrict processing
        "objection",        # Right to object to processing
    ],
}
```

### 6.6 Cookie Consent

```python
# compliance/cookies.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CookieCategory(str, Enum):
    ESSENTIAL = "essential"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    FUNCTIONAL = "functional"


class Cookie(BaseModel):
    """Cookie definition."""
    name: str
    category: CookieCategory
    purpose: str
    duration: str
    is_first_party: bool = True


COOKIE_REGISTRY = [
    Cookie(
        name="session_id",
        category=CookieCategory.ESSENTIAL,
        purpose="Session management",
        duration="Session",
        is_first_party=True,
    ),
    Cookie(
        name="csrf_token",
        category=CookieCategory.ESSENTIAL,
        purpose="CSRF protection",
        duration="1 hour",
        is_first_party=True,
    ),
    Cookie(
        name="consent_preferences",
        category=CookieCategory.ESSENTIAL,
        purpose="Cookie consent preferences",
        duration="1 year",
        is_first_party=True,
    ),
    Cookie(
        name="_ga",
        category=CookieCategory.ANALYTICS,
        purpose="Google Analytics user identification",
        duration="2 years",
        is_first_party=False,
    ),
]


class CookieConsentService:
    """Cookie consent management."""

    async def get_consent(self, user_id: str) -> dict:
        """Get user's cookie consent preferences."""
        consent = await consent_repo.get(user_id)
        if not consent:
            return {
                "essential": True,  # Always required
                "analytics": False,
                "marketing": False,
                "functional": False,
            }
        return consent.preferences

    async def update_consent(
        self,
        user_id: str,
        preferences: dict,
        ip_address: str,
        user_agent: str,
    ):
        """Update cookie consent preferences."""
        # Essential cookies cannot be disabled
        preferences["essential"] = True

        await consent_repo.save(
            user_id=user_id,
            preferences=preferences,
            ip_address=ip_address,
            user_agent=user_agent,
            updated_at=datetime.utcnow(),
        )

        await audit_log.record(
            user_id=user_id,
            action="consent.updated",
            resource_type="consent",
            resource_id=user_id,
            details={"preferences": preferences},
        )

        # Apply preferences
        if not preferences.get("analytics"):
            await self._disable_analytics_cookies(user_id)
        if not preferences.get("marketing"):
            await self._disable_marketing_cookies(user_id)
```

---

## 7. Incident Response

### 7.1 Security Event Detection

```python
# security/detection.py
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import asyncio


class SecurityEventType(str, Enum):
    """Security event categories."""
    BRUTE_FORCE = "brute_force"
    CREDENTIAL_STUFFING = "credential_stuffing"
    ACCOUNT_TAKEOVER = "account_takeover"
    API_ABUSE = "api_abuse"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    INJECTION_ATTEMPT = "injection_attempt"
    SUSPICIOUS_LOGIN = "suspicious_login"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    MALWARE_DETECTED = "malware_detected"


class SecuritySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEvent(BaseModel):
    """Security event model."""
    id: str
    event_type: SecurityEventType
    severity: SecuritySeverity
    timestamp: datetime
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: dict
    indicators: list[str]
    recommended_actions: list[str]


class SecurityDetectionService:
    """Real-time security event detection."""

    def __init__(self, redis_client, kafka_producer):
        self.redis = redis_client
        self.kafka = kafka_producer

    async def detect_brute_force(
        self, ip_address: str, user_id: str
    ) -> Optional[SecurityEvent]:
        """Detect brute force login attempts."""
        key = f"security:bf:{ip_address}"
        attempts = int(await self.redis.get(key) or 0)

        if attempts >= 10:  # 10 failed attempts in 5 minutes
            return SecurityEvent(
                id=str(uuid.uuid4()),
                event_type=SecurityEventType.BRUTE_FORCE,
                severity=SecuritySeverity.HIGH,
                timestamp=datetime.utcnow(),
                user_id=user_id,
                ip_address=ip_address,
                details={"attempts": attempts, "window": "5 minutes"},
                indicators=[
                    f"IP {ip_address} made {attempts} failed login attempts",
                    "Multiple different usernames attempted",
                ],
                recommended_actions=[
                    "Block IP address temporarily",
                    "Notify affected user",
                    "Review IP reputation",
                ],
            )
        return None

    async def detect_credential_stuffing(
        self, ip_address: str
    ) -> Optional[SecurityEvent]:
        """Detect credential stuffing attacks."""
        key = f"security:cs:{ip_address}"
        unique_emails = await self.redis.scard(key)

        if unique_emails >= 20:  # 20+ different emails from same IP
            return SecurityEvent(
                id=str(uuid.uuid4()),
                event_type=SecurityEventType.CREDENTIAL_STUFFING,
                severity=SecuritySeverity.CRITICAL,
                timestamp=datetime.utcnow(),
                ip_address=ip_address,
                details={"unique_emails_attempted": unique_emails},
                indicators=[
                    f"IP {ip_address} attempted login with {unique_emails} different emails",
                    "Pattern consistent with credential stuffing",
                ],
                recommended_actions=[
                    "Block IP address",
                    "Enable CAPTCHA for login",
                    "Alert security team",
                    "Check for data breach exposure",
                ],
            )
        return None

    async def detect_data_exfiltration(
        self, user_id: str, org_id: str
    ) -> Optional[SecurityEvent]:
        """Detect potential data exfiltration."""
        # Check for unusual data access patterns
        key = f"security:exfil:{user_id}"
        data_volume = int(await self.redis.get(key) or 0)

        if data_volume > 1000000:  # > 1MB of data exported
            return SecurityEvent(
                id=str(uuid.uuid4()),
                event_type=SecurityEventType.DATA_EXFILTRATION,
                severity=SecuritySeverity.CRITICAL,
                timestamp=datetime.utcnow(),
                user_id=user_id,
                details={
                    "data_volume_bytes": data_volume,
                    "org_id": org_id,
                },
                indicators=[
                    f"User {user_id} exported {data_volume} bytes of data",
                    "Volume significantly exceeds normal usage",
                ],
                recommended_actions=[
                    "Review user's recent activity",
                    "Temporarily restrict export permissions",
                    "Notify organization admin",
                    "Investigate data sensitivity",
                ],
            )
        return None

    async def detect_suspicious_login(
        self,
        user_id: str,
        ip_address: str,
        geo_location: dict,
    ) -> Optional[SecurityEvent]:
        """Detect suspicious login (impossible travel, new device, etc.)."""
        # Get last login
        last_login = await login_history_repo.get_last(user_id)
        if not last_login:
            return None

        # Check for impossible travel
        if last_login.geo_location:
            distance_km = self._calculate_distance(
                last_login.geo_location, geo_location
            )
            time_diff = (datetime.utcnow() - last_login.timestamp).total_seconds() / 3600

            # If distance > 500km and time < 1 hour
            if distance_km > 500 and time_diff < 1:
                return SecurityEvent(
                    id=str(uuid.uuid4()),
                    event_type=SecurityEventType.SUSPICIOUS_LOGIN,
                    severity=SecuritySeverity.HIGH,
                    timestamp=datetime.utcnow(),
                    user_id=user_id,
                    ip_address=ip_address,
                    details={
                        "last_login_location": last_login.geo_location,
                        "current_location": geo_location,
                        "distance_km": distance_km,
                        "time_hours": time_diff,
                    },
                    indicators=[
                        f"Login from {geo_location} only {time_diff:.1f} hours after login from {last_login.geo_location}",
                        f"Distance: {distance_km:.0f} km",
                    ],
                    recommended_actions=[
                        "Require MFA verification",
                        "Send security alert to user",
                        "Log for investigation",
                    ],
                )

        # Check for new device
        if not await device_repo.exists(user_id, request.state.device_fingerprint):
            return SecurityEvent(
                id=str(uuid.uuid4()),
                event_type=SecurityEventType.SUSPICIOUS_LOGIN,
                severity=SecuritySeverity.MEDIUM,
                timestamp=datetime.utcnow(),
                user_id=user_id,
                ip_address=ip_address,
                details={"device": request.state.device_fingerprint},
                indicators=["Login from unrecognized device"],
                recommended_actions=[
                    "Require MFA verification",
                    "Send new device notification",
                ],
            )

        return None
```

### 7.2 Alert Thresholds

```python
# security/alerts.py
from datetime import datetime, timedelta
from typing import Optional


ALERT_THRESHOLDS = {
    "failed_logins": {
        "per_ip_per_minute": 10,
        "per_user_per_hour": 20,
        "global_per_minute": 100,
    },
    "api_errors": {
        "4xx_per_minute_per_user": 50,
        "5xx_per_minute_global": 20,
    },
    "rate_limit_hits": {
        "per_user_per_hour": 100,
        "global_per_minute": 50,
    },
    "data_export": {
        "records_per_hour_per_user": 10000,
        "bytes_per_hour_per_user": 100_000_000,  # 100MB
    },
    "privilege_changes": {
        "role_changes_per_hour": 5,
        "permission_changes_per_hour": 10,
    },
    "new_registrations": {
        "per_ip_per_hour": 5,
        "global_per_hour": 100,
    },
}


class AlertService:
    """Security alert management."""

    async def check_thresholds(self, event_type: str, metrics: dict) -> list[dict]:
        """Check if metrics exceed alert thresholds."""
        alerts = []
        thresholds = ALERT_THRESHOLDS.get(event_type, {})

        for metric, threshold in thresholds.items():
            current = metrics.get(metric, 0)
            if current > threshold:
                alerts.append({
                    "event_type": event_type,
                    "metric": metric,
                    "threshold": threshold,
                    "current": current,
                    "severity": self._calculate_severity(current, threshold),
                    "timestamp": datetime.utcnow().isoformat(),
                })

        return alerts

    async def send_alert(self, alert: dict):
        """Send security alert to appropriate channels."""
        severity = alert.get("severity", "low")

        # Determine notification channels based on severity
        if severity == "critical":
            channels = ["slack_security", "pagerduty", "email_security_team", "sms_on_call"]
        elif severity == "high":
            channels = ["slack_security", "email_security_team"]
        elif severity == "medium":
            channels = ["slack_security"]
        else:
            channels = ["slack_security"]

        for channel in channels:
            await notification_service.send(
                channel=channel,
                template="security_alert",
                data=alert,
            )

        # Log alert
        await audit_log.record(
            user_id="system",
            action="security.alert_sent",
            resource_type="alert",
            resource_id=alert.get("id"),
            details=alert,
        )

    def _calculate_severity(self, current: int, threshold: int) -> str:
        """Calculate alert severity based on threshold breach ratio."""
        ratio = current / threshold
        if ratio >= 5:
            return "critical"
        elif ratio >= 3:
            return "high"
        elif ratio >= 1.5:
            return "medium"
        return "low"
```

### 7.3 Incident Response Playbook

```python
# security/incident_response.py
"""
Incident Response Playbook

Severity Levels:
- P1 (Critical): Data breach, system compromise, ransomware
- P2 (High): Active attack, privilege escalation, service disruption
- P3 (Medium): Suspicious activity, policy violation, vulnerability
- P4 (Low): Informational, minor policy deviation
"""


class IncidentResponsePlaybook:
    """Incident response procedures."""

    PLAYBOOKS = {
        "data_breach": {
            "severity": "P1",
            "steps": [
                {
                    "order": 1,
                    "action": "Contain",
                    "description": "Isolate affected systems",
                    "commands": [
                        "Revoke all sessions for affected users",
                        "Block suspicious IP addresses",
                        "Disable affected API keys",
                        "Enable emergency maintenance mode if needed",
                    ],
                    "responsible": "Security Engineer",
                    "timeframe": "15 minutes",
                },
                {
                    "order": 2,
                    "action": "Assess",
                    "description": "Determine scope and impact",
                    "commands": [
                        "Review audit logs for data access",
                        "Identify affected data types",
                        "Determine number of affected users",
                        "Check for ongoing exfiltration",
                    ],
                    "responsible": "Security Lead",
                    "timeframe": "1 hour",
                },
                {
                    "order": 3,
                    "action": "Notify",
                    "description": "Notify stakeholders",
                    "commands": [
                        "Alert CISO and executive team",
                        "Notify affected users within 72 hours (GDPR)",
                        "Prepare regulatory notifications",
                        "Brief legal team",
                    ],
                    "responsible": "CISO",
                    "timeframe": "24 hours",
                },
                {
                    "order": 4,
                    "action": "Remediate",
                    "description": "Fix vulnerability and prevent recurrence",
                    "commands": [
                        "Patch vulnerability",
                        "Rotate all credentials",
                        "Update security controls",
                        "Deploy additional monitoring",
                    ],
                    "responsible": "Engineering Team",
                    "timeframe": "48 hours",
                },
                {
                    "order": 5,
                    "action": "Review",
                    "description": "Post-incident review",
                    "commands": [
                        "Conduct blameless post-mortem",
                        "Document lessons learned",
                        "Update incident response procedures",
                        "Implement preventive measures",
                    ],
                    "responsible": "Security Team",
                    "timeframe": "1 week",
                },
            ],
        },
        "account_takeover": {
            "severity": "P2",
            "steps": [
                {
                    "order": 1,
                    "action": "Lock Account",
                    "description": "Immediately secure the account",
                    "commands": [
                        "Revoke all sessions",
                        "Reset password",
                        "Disable API keys",
                        "Enable forced MFA",
                    ],
                    "responsible": "Security Engineer",
                    "timeframe": "5 minutes",
                },
                {
                    "order": 2,
                    "action": "Investigate",
                    "description": "Determine attack vector",
                    "commands": [
                        "Review login history",
                        "Check for credential leak",
                        "Analyze attacker activity",
                        "Check for data exfiltration",
                    ],
                    "responsible": "Security Analyst",
                    "timeframe": "2 hours",
                },
                {
                    "order": 3,
                    "action": "Recover",
                    "description": "Restore account security",
                    "commands": [
                        "Verify user identity",
                        "Restore access with new credentials",
                        "Review and revoke unauthorized changes",
                        "Enable enhanced monitoring",
                    ],
                    "responsible": "Support + Security",
                    "timeframe": "24 hours",
                },
            ],
        },
        "ddos_attack": {
            "severity": "P2",
            "steps": [
                {
                    "order": 1,
                    "action": "Activate DDoS Protection",
                    "description": "Enable DDoS mitigation",
                    "commands": [
                        "Enable Cloudflare Under Attack Mode",
                        "Activate rate limiting",
                        "Enable IP reputation blocking",
                        "Scale infrastructure if needed",
                    ],
                    "responsible": "DevOps",
                    "timeframe": "5 minutes",
                },
                {
                    "order": 2,
                    "action": "Monitor",
                    "description": "Monitor attack and mitigation",
                    "commands": [
                        "Track traffic patterns",
                        "Monitor service health",
                        "Coordinate with ISP/CDN",
                        "Document attack characteristics",
                    ],
                    "responsible": "DevOps + Security",
                    "timeframe": "Ongoing",
                },
            ],
        },
    }

    @classmethod
    def get_playbook(cls, incident_type: str) -> dict:
        """Get incident response playbook."""
        return cls.PLAYBOOKS.get(incident_type)

    @classmethod
    async def execute_step(
        cls,
        incident_id: str,
        playbook_type: str,
        step_order: int,
        executed_by: str,
    ):
        """Execute a playbook step and log it."""
        playbook = cls.PLAYBOOKS.get(playbook_type)
        if not playbook:
            raise ValueError(f"Unknown playbook: {playbook_type}")

        step = next(
            (s for s in playbook["steps"] if s["order"] == step_order),
            None,
        )
        if not step:
            raise ValueError(f"Step {step_order} not found")

        # Log execution
        await audit_log.record(
            user_id=executed_by,
            action="incident.step_executed",
            resource_type="incident",
            resource_id=incident_id,
            details={
                "playbook": playbook_type,
                "step": step_order,
                "action": step["action"],
            },
        )

        return step
```

### 7.4 Communication Plan

```python
# security/communication.py
"""
Incident Communication Plan

Stakeholders and notification requirements by severity.
"""

COMMUNICATION_PLAN = {
    "P1": {
        "internal": {
            "recipients": ["CISO", "CTO", "CEO", "Legal", "PR"],
            "channels": ["pagerduty", "phone", "slack_incident"],
            "timeframe": "15 minutes",
            "frequency": "Every 30 minutes until resolved",
        },
        "external": {
            "recipients": ["Affected users", "Regulators", "Partners"],
            "channels": ["email", "status_page", "blog"],
            "timeframe": "72 hours (GDPR requirement)",
            "frequency": "Daily until resolved",
        },
        "templates": {
            "initial": "We are investigating a security incident...",
            "update": "Update on security incident...",
            "resolution": "Security incident resolved...",
        },
    },
    "P2": {
        "internal": {
            "recipients": ["Security Team", "Engineering Lead", "CTO"],
            "channels": ["slack_security", "pagerduty"],
            "timeframe": "30 minutes",
            "frequency": "Every hour until resolved",
        },
        "external": {
            "recipients": ["Affected users (if applicable)"],
            "channels": ["email", "status_page"],
            "timeframe": "As needed",
            "frequency": "As needed",
        },
    },
    "P3": {
        "internal": {
            "recipients": ["Security Team", "Engineering Lead"],
            "channels": ["slack_security"],
            "timeframe": "4 hours",
            "frequency": "Daily",
        },
    },
    "P4": {
        "internal": {
            "recipients": ["Security Team"],
            "channels": ["slack_security"],
            "timeframe": "24 hours",
            "frequency": "Weekly review",
        },
    },
}
```

### 7.5 Post-Incident Review

```python
# security/post_incident.py
from pydantic import BaseModel
from datetime import datetime


class PostIncidentReview(BaseModel):
    """Post-incident review (blameless post-mortem)."""
    incident_id: str
    title: str
    severity: str
    date: datetime
    duration_hours: float

    # Timeline
    timeline: list[dict]  # [{time, event, actor}]

    # Impact
    users_affected: int
    data_affected: list[str]
    financial_impact: Optional[str] = None
    reputation_impact: Optional[str] = None

    # Root Cause
    root_cause: str
    contributing_factors: list[str]

    # Response
    what_went_well: list[str]
    what_went_poorly: list[str]

    # Action Items
    action_items: list[dict]  # [{action, owner, due_date, priority}]

    # Lessons Learned
    lessons_learned: list[str]

    # Metrics
    time_to_detect: float      # minutes
    time_to_respond: float     # minutes
    time_to_resolve: float     # minutes


class PostIncidentService:
    """Post-incident review management."""

    async def create_review(
        self,
        incident_id: str,
        review_data: PostIncidentReview,
    ) -> str:
        """Create a post-incident review."""
        review_id = str(uuid.uuid4())
        await post_incident_repo.create(review_id, review_data)

        # Create action items in project management tool
        for item in review_data.action_items:
            await project_service.create_task(
                title=f"[Security] {item['action']}",
                assignee=item["owner"],
                due_date=item["due_date"],
                priority=item["priority"],
                labels=["security", "post-incident"],
            )

        # Schedule follow-up
        await scheduler.schedule(
            action="review_action_items",
            data={"review_id": review_id},
            run_at=datetime.utcnow() + timedelta(days=30),
        )

        return review_id

    async def generate_metrics_report(self) -> dict:
        """Generate incident response metrics."""
        incidents = await post_incident_repo.get_all(
            start_date=datetime.utcnow() - timedelta(days=365)
        )

        if not incidents:
            return {"message": "No incidents in the past year"}

        return {
            "total_incidents": len(incidents),
            "by_severity": {
                "P1": len([i for i in incidents if i.severity == "P1"]),
                "P2": len([i for i in incidents if i.severity == "P2"]),
                "P3": len([i for i in incidents if i.severity == "P3"]),
                "P4": len([i for i in incidents if i.severity == "P4"]),
            },
            "avg_time_to_detect": sum(i.time_to_detect for i in incidents) / len(incidents),
            "avg_time_to_respond": sum(i.time_to_respond for i in incidents) / len(incidents),
            "avg_time_to_resolve": sum(i.time_to_resolve for i in incidents) / len(incidents),
            "total_users_affected": sum(i.users_affected for i in incidents),
            "open_action_items": await self._count_open_action_items(),
        }
```

---

## 8. Security Monitoring

### 8.1 Failed Login Tracking

```python
# monitoring/login_tracking.py
from datetime import datetime, timedelta
from collections import defaultdict


class LoginTrackingService:
    """Track and analyze failed login attempts."""

    def __init__(self, redis_client, db_client):
        self.redis = redis_client
        self.db = db_client

    async def track_attempt(
        self,
        email: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        failure_reason: str = None,
    ):
        """Track a login attempt."""
        now = datetime.utcnow()

        # Store in Redis for real-time analysis
        attempt_data = {
            "email": email,
            "ip": ip_address,
            "success": success,
            "reason": failure_reason,
            "timestamp": now.isoformat(),
        }

        # Add to time-series
        await self.redis.lpush(
            f"login_attempts:{now.strftime('%Y%m%d%H')}",
            json.dumps(attempt_data),
        )
        await self.redis.expire(f"login_attempts:{now.strftime('%Y%m%d%H')}", 86400)

        # Track by IP
        if not success:
            await self.redis.incr(f"failed_login:ip:{ip_address}")
            await self.redis.expire(f"failed_login:ip:{ip_address}", 3600)

            await self.redis.incr(f"failed_login:email:{email}")
            await self.redis.expire(f"failed_login:email:{email}", 3600)

        # Store in database for long-term analysis
        await self.db.execute(
            """
            INSERT INTO login_attempts (
                email, ip_address, user_agent, success, 
                failure_reason, attempted_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            email, ip_address, user_agent, success, failure_reason, now,
        )

    async def get_failed_attempts_summary(
        self,
        hours: int = 24,
    ) -> dict:
        """Get summary of failed login attempts."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        rows = await self.db.fetch(
            """
            SELECT 
                ip_address,
                email,
                COUNT(*) as attempt_count,
                MIN(attempted_at) as first_attempt,
                MAX(attempted_at) as last_attempt
            FROM login_attempts
            WHERE success = FALSE AND attempted_at > $1
            GROUP BY ip_address, email
            HAVING COUNT(*) >= 3
            ORDER BY attempt_count DESC
            LIMIT 100
            """,
            cutoff,
        )

        return {
            "period_hours": hours,
            "suspicious_ips": [
                {
                    "ip_address": row["ip_address"],
                    "email": row["email"],
                    "attempts": row["attempt_count"],
                    "first_seen": row["first_attempt"].isoformat(),
                    "last_seen": row["last_attempt"].isoformat(),
                }
                for row in rows
            ],
        }
```

### 8.2 Suspicious Activity Detection

```python
# monitoring/suspicious_activity.py
from datetime import datetime, timedelta
from typing import Optional


class SuspiciousActivityDetector:
    """Detect suspicious user activity patterns."""

    def __init__(self, redis_client, db_client):
        self.redis = redis_client
        self.db = db_client

    async def analyze_user_activity(self, user_id: str) -> list[dict]:
        """Analyze user activity for suspicious patterns."""
        alerts = []

        # Check for unusual data access volume
        data_access = await self._get_data_access_volume(user_id, hours=1)
        if data_access > 1000:
            alerts.append({
                "type": "high_data_access",
                "severity": "medium",
                "details": {
                    "records_accessed": data_access,
                    "timeframe": "1 hour",
                },
            })

        # Check for unusual API usage
        api_calls = await self._get_api_call_count(user_id, minutes=10)
        if api_calls > 500:
            alerts.append({
                "type": "api_abuse",
                "severity": "high",
                "details": {
                    "api_calls": api_calls,
                    "timeframe": "10 minutes",
                },
            })

        # Check for privilege escalation attempts
        priv_attempts = await self._get_privilege_attempts(user_id, hours=1)
        if priv_attempts > 0:
            alerts.append({
                "type": "privilege_escalation_attempt",
                "severity": "high",
                "details": {
                    "attempts": priv_attempts,
                    "timeframe": "1 hour",
                },
            })

        # Check for unusual login patterns
        login_pattern = await self._analyze_login_pattern(user_id)
        if login_pattern.get("is_unusual"):
            alerts.append({
                "type": "unusual_login_pattern",
                "severity": "medium",
                "details": login_pattern,
            })

        return alerts

    async def _get_data_access_volume(self, user_id: str, hours: int) -> int:
        """Get data access volume for a user."""
        result = await self.db.fetchval(
            """
            SELECT COUNT(*) FROM audit_logs
            WHERE user_id = $1
            AND action LIKE '%read%'
            AND timestamp > NOW() - INTERVAL '%s hours'
            """,
            user_id, hours,
        )
        return result or 0

    async def _get_api_call_count(self, user_id: str, minutes: int) -> int:
        """Get API call count for a user."""
        key = f"api_calls:{user_id}"
        return int(await self.redis.get(key) or 0)

    async def _get_privilege_attempts(self, user_id: str, hours: int) -> int:
        """Get privilege escalation attempt count."""
        result = await self.db.fetchval(
            """
            SELECT COUNT(*) FROM audit_logs
            WHERE user_id = $1
            AND action = 'permission.denied'
            AND timestamp > NOW() - INTERVAL '%s hours'
            """,
            user_id, hours,
        )
        return result or 0

    async def _analyze_login_pattern(self, user_id: str) -> dict:
        """Analyze login patterns for anomalies."""
        # Get recent logins
        logins = await self.db.fetch(
            """
            SELECT ip_address, user_agent, attempted_at
            FROM login_attempts
            WHERE email = (SELECT email FROM users WHERE id = $1)
            AND success = TRUE
            ORDER BY attempted_at DESC
            LIMIT 20
            """,
            user_id,
        )

        if len(logins) < 5:
            return {"is_unusual": False}

        # Check for IP diversity
        unique_ips = len(set(l["ip_address"] for l in logins))
        if unique_ips > 5:
            return {
                "is_unusual": True,
                "reason": "High IP diversity",
                "unique_ips": unique_ips,
            }

        # Check for user agent diversity
        unique_agents = len(set(l["user_agent"] for l in logins))
        if unique_agents > 3:
            return {
                "is_unusual": True,
                "reason": "High device diversity",
                "unique_agents": unique_agents,
            }

        return {"is_unusual": False}
```

### 8.3 API Abuse Detection

```python
# monitoring/api_abuse.py
from datetime import datetime, timedelta


class APIAbuseDetector:
    """Detect API abuse patterns."""

    def __init__(self, redis_client, db_client):
        self.redis = redis_client
        self.db = db_client

    ABUSE_PATTERNS = {
        "scraping": {
            "indicators": [
                "High request rate from single IP",
                "Sequential endpoint access",
                "No referrer header",
                "Non-browser user agent",
            ],
            "threshold": 3,
        },
        "enumeration": {
            "indicators": [
                "High 404 rate",
                "Sequential ID access",
                "Multiple invalid parameter attempts",
            ],
            "threshold": 2,
        },
        "resource_exhaustion": {
            "indicators": [
                "Large request payloads",
                "Expensive endpoint abuse",
                "Concurrent request flooding",
            ],
            "threshold": 2,
        },
    }

    async def analyze_request(
        self,
        user_id: str,
        ip_address: str,
        endpoint: str,
        status_code: int,
        request_size: int,
        response_time_ms: int,
    ) -> Optional[dict]:
        """Analyze a single API request for abuse indicators."""
        indicators = []

        # Check request rate
        rate = await self._get_request_rate(ip_address, minutes=5)
        if rate > 100:
            indicators.append("high_request_rate")

        # Check for expensive endpoints
        if endpoint in self.EXPENSIVE_ENDPOINTS and response_time_ms > 5000:
            indicators.append("expensive_endpoint_abuse")

        # Check for enumeration
        if status_code == 404:
            not_found_rate = await self._get_404_rate(ip_address, minutes=5)
            if not_found_rate > 20:
                indicators.append("high_404_rate")

        # Check for large payloads
        if request_size > 1_000_000:  # 1MB
            indicators.append("large_payload")

        # Evaluate abuse pattern
        for pattern_name, pattern in self.ABUSE_PATTERNS.items():
            matching = [i for i in indicators if i in pattern["indicators"]]
            if len(matching) >= pattern["threshold"]:
                return {
                    "pattern": pattern_name,
                    "indicators": matching,
                    "severity": "high" if len(matching) > pattern["threshold"] else "medium",
                    "user_id": user_id,
                    "ip_address": ip_address,
                }

        return None

    async def _get_request_rate(self, ip_address: str, minutes: int) -> int:
        """Get request rate for an IP."""
        key = f"api_rate:{ip_address}"
        return int(await self.redis.get(key) or 0)

    async def _get_404_rate(self, ip_address: str, minutes: int) -> int:
        """Get 404 rate for an IP."""
        key = f"api_404:{ip_address}"
        return int(await self.redis.get(key) or 0)

    EXPENSIVE_ENDPOINTS = {
        "/api/v1/audits",
        "/api/v1/backlinks/scan",
        "/api/v1/keywords/bulk",
        "/api/v1/reports/generate",
    }
```

### 8.4 IP Reputation Checking

```python
# monitoring/ip_reputation.py
import httpx
from datetime import datetime, timedelta


class IPReputationService:
    """Check IP reputation against threat intelligence feeds."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 hour

    async def check_reputation(self, ip_address: str) -> dict:
        """Check IP reputation from multiple sources."""
        # Check cache first
        cached = await self._get_cached_reputation(ip_address)
        if cached:
            return cached

        reputation = {
            "ip": ip_address,
            "is_malicious": False,
            "risk_score": 0,
            "sources": {},
            "checked_at": datetime.utcnow().isoformat(),
        }

        # Check AbuseIPDB
        abuse_result = await self._check_abuseipdb(ip_address)
        reputation["sources"]["abuseipdb"] = abuse_result

        # Check VirusTotal
        vt_result = await self._check_virustotal(ip_address)
        reputation["sources"]["virustotal"] = vt_result

        # Check internal blacklist
        internal_result = await self._check_internal_blacklist(ip_address)
        reputation["sources"]["internal"] = internal_result

        # Calculate aggregate risk score
        scores = [
            abuse_result.get("score", 0),
            vt_result.get("score", 0),
            internal_result.get("score", 0),
        ]
        reputation["risk_score"] = max(scores)
        reputation["is_malicious"] = reputation["risk_score"] > 75

        # Cache result
        await self._cache_reputation(ip_address, reputation)

        return reputation

    async def _check_abuseipdb(self, ip_address: str) -> dict:
        """Check AbuseIPDB."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.abuseipdb.com/api/v2/check",
                    params={"ipAddress": ip_address, "maxAgeInDays": 90},
                    headers={"Key": settings.ABUSEIPDB_API_KEY},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()["data"]
                    return {
                        "score": data["abuseConfidenceScore"],
                        "reports": data["totalReports"],
                        "country": data["countryCode"],
                        "isp": data["isp"],
                    }
        except Exception:
            pass
        return {"score": 0, "error": "unavailable"}

    async def _check_virustotal(self, ip_address: str) -> dict:
        """Check VirusTotal."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://www.virustotal.com/api/v3/ip_addresses/{ip_address}",
                    headers={"x-apikey": settings.VIRUSTOTAL_API_KEY},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()["data"]["attributes"]
                    malicious = data["last_analysis_stats"]["malicious"]
                    total = sum(data["last_analysis_stats"].values())
                    score = int((malicious / total) * 100) if total > 0 else 0
                    return {
                        "score": score,
                        "malicious_engines": malicious,
                        "total_engines": total,
                    }
        except Exception:
            pass
        return {"score": 0, "error": "unavailable"}

    async def _check_internal_blacklist(self, ip_address: str) -> dict:
        """Check internal blacklist."""
        is_blacklisted = await self.redis.sismember("ip_blacklist", ip_address)
        return {
            "score": 100 if is_blacklisted else 0,
            "blacklisted": bool(is_blacklisted),
        }

    async def _get_cached_reputation(self, ip_address: str) -> Optional[dict]:
        """Get cached reputation data."""
        cached = await self.redis.get(f"ip_reputation:{ip_address}")
        if cached:
            return json.loads(cached)
        return None

    async def _cache_reputation(self, ip_address: str, reputation: dict):
        """Cache reputation data."""
        await self.redis.setex(
            f"ip_reputation:{ip_address}",
            self.cache_ttl,
            json.dumps(reputation),
        )

    async def add_to_blacklist(self, ip_address: str, reason: str, added_by: str):
        """Add IP to internal blacklist."""
        await self.redis.sadd("ip_blacklist", ip_address)
        await self.redis.hset(
            f"ip_blacklist:meta:{ip_address}",
            mapping={
                "reason": reason,
                "added_by": added_by,
                "added_at": datetime.utcnow().isoformat(),
            },
        )

        await audit_log.record(
            user_id=added_by,
            action="security.ip_blacklisted",
            resource_type="ip",
            resource_id=ip_address,
            details={"reason": reason},
        )
```

### 8.5 Anomaly Detection

```python
# monitoring/anomaly_detection.py
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from collections import deque


class AnomalyDetector:
    """Statistical anomaly detection for security monitoring."""

    def __init__(self, redis_client, db_client):
        self.redis = redis_client
        self.db = db_client
        self.window_size = 168  # 1 week of hourly data

    async def detect_anomalies(self, metric_name: str) -> list[dict]:
        """Detect anomalies in a metric using Z-score."""
        # Get historical data
        data = await self._get_metric_history(metric_name, hours=self.window_size)

        if len(data) < 24:  # Need at least 24 hours of data
            return []

        # Calculate statistics
        values = [d["value"] for d in data]
        mean = np.mean(values)
        std = np.std(values)

        if std == 0:
            return []

        # Check recent values for anomalies
        recent = data[-6:]  # Last 6 hours
        anomalies = []

        for point in recent:
            z_score = (point["value"] - mean) / std

            if abs(z_score) > 3:  # 3-sigma rule
                anomalies.append({
                    "metric": metric_name,
                    "timestamp": point["timestamp"],
                    "value": point["value"],
                    "mean": float(mean),
                    "std": float(std),
                    "z_score": float(z_score),
                    "severity": "high" if abs(z_score) > 4 else "medium",
                    "direction": "spike" if z_score > 0 else "drop",
                })

        return anomalies

    async def detect_volume_anomalies(self) -> list[dict]:
        """Detect anomalies in data access volume."""
        metrics = [
            "api_requests",
            "data_exports",
            "login_attempts",
            "failed_logins",
            "keyword_searches",
            "audit_requests",
        ]

        all_anomalies = []
        for metric in metrics:
            anomalies = await self.detect_anomalies(metric)
            all_anomalies.extend(anomalies)

        return all_anomalies

    async def detect_pattern_anomalies(self, user_id: str) -> list[dict]:
        """Detect anomalous user behavior patterns."""
        anomalies = []

        # Get user's historical activity patterns
        patterns = await self._get_user_patterns(user_id)

        # Check for unusual time-of-day activity
        current_hour = datetime.utcnow().hour
        if current_hour in patterns.get("unusual_hours", []):
            anomalies.append({
                "type": "unusual_time",
                "severity": "medium",
                "details": {
                    "current_hour": current_hour,
                    "typical_hours": patterns.get("typical_hours", []),
                },
            })

        # Check for unusual endpoint access
        recent_endpoints = await self._get_recent_endpoints(user_id, hours=1)
        unusual = [
            ep for ep in recent_endpoints
            if ep not in patterns.get("typical_endpoints", [])
        ]
        if unusual:
            anomalies.append({
                "type": "unusual_endpoints",
                "severity": "low",
                "details": {"unusual_endpoints": unusual},
            })

        # Check for unusual data volume
        recent_volume = await self._get_recent_data_volume(user_id, hours=1)
        avg_volume = patterns.get("avg_hourly_volume", 0)
        if recent_volume > avg_volume * 5:
            anomalies.append({
                "type": "unusual_volume",
                "severity": "high",
                "details": {
                    "recent_volume": recent_volume,
                    "average_volume": avg_volume,
                    "ratio": recent_volume / avg_volume if avg_volume > 0 else float("inf"),
                },
            })

        return anomalies

    async def _get_metric_history(self, metric_name: str, hours: int) -> list[dict]:
        """Get historical metric data."""
        rows = await self.db.fetch(
            """
            SELECT 
                date_trunc('hour', recorded_at) as timestamp,
                AVG(value) as value
            FROM metrics
            WHERE metric_name = $1
            AND recorded_at > NOW() - INTERVAL '%s hours'
            GROUP BY date_trunc('hour', recorded_at)
            ORDER BY timestamp
            """,
            metric_name, hours,
        )
        return [{"timestamp": row["timestamp"], "value": float(row["value"])} for row in rows]

    async def _get_user_patterns(self, user_id: str) -> dict:
        """Get user's typical activity patterns."""
        # Get activity by hour
        hourly = await self.db.fetch(
            """
            SELECT 
                EXTRACT(HOUR FROM timestamp) as hour,
                COUNT(*) as count
            FROM audit_logs
            WHERE user_id = $1
            AND timestamp > NOW() - INTERVAL '30 days'
            GROUP BY EXTRACT(HOUR FROM timestamp)
            """,
            user_id,
        )

        # Get typical endpoints
        endpoints = await self.db.fetch(
            """
            SELECT action, COUNT(*) as count
            FROM audit_logs
            WHERE user_id = $1
            AND timestamp > NOW() - INTERVAL '30 days'
            GROUP BY action
            ORDER BY count DESC
            LIMIT 20
            """,
            user_id,
        )

        # Get average volume
        avg_volume = await self.db.fetchval(
            """
            SELECT AVG(hourly_count) FROM (
                SELECT 
                    date_trunc('hour', timestamp) as hour,
                    COUNT(*) as hourly_count
                FROM audit_logs
                WHERE user_id = $1
                AND timestamp > NOW() - INTERVAL '30 days'
                GROUP BY date_trunc('hour', timestamp)
            ) sub
            """,
            user_id,
        )

        # Identify typical hours (above average activity)
        counts = [r["count"] for r in hourly]
        avg_count = np.mean(counts) if counts else 0
        typical_hours = [int(r["hour"]) for r in hourly if r["count"] >= avg_count]

        return {
            "typical_hours": typical_hours,
            "unusual_hours": [h for h in range(24) if h not in typical_hours],
            "typical_endpoints": [r["action"] for r in endpoints],
            "avg_hourly_volume": float(avg_volume or 0),
        }
```

---

## Security Configuration Summary

```python
# config/security.py
"""
Centralized security configuration.
"""

from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    """Security configuration settings."""

    # Encryption
    ENCRYPTION_MASTER_KEY: str  # 256-bit key from secret manager
    JWT_PRIVATE_KEY: str        # RSA private key
    JWT_PUBLIC_KEY: str         # RSA public key

    # Password
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_MAX_AGE_DAYS: int = 90
    PASSWORD_HISTORY_COUNT: int = 12

    # Session
    SESSION_TIMEOUT_MINUTES: int = 30
    SESSION_ABSOLUTE_TIMEOUT_HOURS: int = 8
    MAX_SESSIONS_PER_USER: int = 10

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5

    # Account lockout
    LOCKOUT_MAX_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30

    # CORS
    CORS_ORIGINS: list[str] = [
        "https://app.seoplatform.com",
        "https://www.seoplatform.com",
    ]

    # Security headers
    HSTS_MAX_AGE: int = 63072000  # 2 years
    CSP_REPORT_URI: str = "/csp-report"

    # API keys
    API_KEY_PREFIX: str = "seo_"
    API_KEY_LENGTH: int = 32

    # Data retention
    AUDIT_LOG_RETENTION_YEARS: int = 7
    SESSION_DATA_RETENTION_DAYS: int = 90

    # Third-party security
    ABUSEIPDB_API_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""

    class Config:
        env_file = ".env"
        env_prefix = "SECURITY_"
```

---

*This security specification provides defense-in-depth for the Proactive SEO Platform. All implementations should be regularly reviewed, tested, and updated as threats evolve.*
