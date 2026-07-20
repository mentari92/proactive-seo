"""FastAPI application factory shared by all bounded services."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from fastapi import Body, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from redis.asyncio import Redis
from starlette.routing import compile_path

from proactive_core.api.postgres_store import PostgresStore
from proactive_core.api.schemas import (
    Envelope,
    LoginRequest,
    Meta,
    PasswordEmailRequest,
    Problem,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from proactive_core.api.store import MemoryStore
from proactive_core.auth import (
    AuthenticationError,
    AuthorizationError,
    MemorySessionStore,
    Principal,
    RedisSessionStore,
    TokenManager,
    require_role,
)
from proactive_core.config import Settings, get_settings
from proactive_core.contracts import EndpointContract, api_contract
from proactive_core.db.session import Database
from proactive_core.ids import decode_id, encode_id
from proactive_core.logging import configure_logging

logger = structlog.get_logger(__name__)
REQUESTS = Counter("proactive_http_requests_total", "HTTP requests", labelnames=("service", "method", "status"))
LATENCY = Histogram("proactive_http_request_duration_seconds", "HTTP request duration", labelnames=("service",))

SERVICE_PREFIXES: dict[str, tuple[str, ...]] = {
    "auth-service": ("/auth", "/users"),
    "tenant-service": ("/organizations", "/projects"),
    "keyword-service": ("/projects/{id}/keywords", "/agents/rank"),
    "crawl-service": ("/agents/crawler", "/projects/{id}/pages", "/projects/{id}/issues"),
    "content-service": ("/agents/content",),
    "rank-tracker-service": ("/agents/rank", "/projects/{id}/serp-features"),
    "serp-monitor-service": ("/agents/technical/multi-engine",),
    "analytics-service": ("/projects/{id}/dashboard", "/projects/{id}/health-score"),
    "notification-service": ("/stream", "/webhooks"),
    "billing-service": tuple(),
    "report-service": ("/reports",),
    "link-analysis-service": ("/agents/backlink", "/campaigns"),
    "ai-service": ("/agents",),
    "audit-service": ("/webhooks",),
}

RESOURCE_PREFIX = {
    "users": "usr",
    "organizations": "org",
    "projects": "prj",
    "agents": "agt",
    "campaigns": "cmp",
    "integrations": "int",
    "reports": "rpt",
    "webhooks": "whk",
    "pages": "pg",
    "keywords": "kw",
    "issues": "iss",
}


class SlidingWindowLimiter:
    """Small local limiter; production deployments use the Redis implementation."""

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, seconds: int = 60) -> tuple[bool, int]:
        """Consume one request from a fixed endpoint/IP window."""
        now = time.monotonic()
        async with self._lock:
            window = self._windows[key]
            while window and window[0] <= now - seconds:
                window.popleft()
            if len(window) >= limit:
                return False, 0
            window.append(now)
            return True, limit - len(window)


class RedisWindowLimiter:
    """Distributed fixed-window limiter for staging and production."""

    def __init__(self, redis: Redis, prefix: str = "proactive:ratelimit") -> None:
        self.redis = redis
        self.prefix = prefix

    async def allow(self, key: str, limit: int, seconds: int = 60) -> tuple[bool, int]:
        """Atomically consume one distributed rate-limit unit."""
        bucket = int(time.time() // seconds)
        redis_key = f"{self.prefix}:{key}:{bucket}"
        async with self.redis.pipeline(transaction=True) as pipeline:
            pipeline.incr(redis_key)
            pipeline.expire(redis_key, seconds + 1)
            count, _ = await pipeline.execute()
        current = int(count)
        return current <= limit, max(0, limit - current)


def _meta(request: Request, *, cursor: str | None = None, has_more: bool | None = None) -> Meta:
    return Meta(
        request_id=request.state.request_id,
        timestamp=datetime.now(UTC),
        cursor=cursor,
        has_more=has_more,
    )


def _envelope(
    request: Request,
    data: Any,
    *,
    status_code: int = 200,
    cursor: str | None = None,
    has_more: bool | None = None,
) -> JSONResponse:
    payload = Envelope[Any](data=data, meta=_meta(request, cursor=cursor, has_more=has_more)).model_dump(mode="json")
    return JSONResponse(payload, status_code=status_code)


def _problem(request: Request, status: int, title: str, detail: str) -> JSONResponse:
    problem = Problem(
        type=f"https://docs.proactive-seo.local/problems/{title.casefold().replace(' ', '-')}",
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        request_id=request.state.request_id,
    )
    return JSONResponse(problem.model_dump(mode="json"), status_code=status, media_type="application/problem+json")


def _principal(request: Request) -> Principal:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("A Bearer access token is required")
    return cast(Principal, request.app.state.tokens.verify_access(authorization.removeprefix("Bearer ")))


def _selected(endpoint: EndpointContract, service_name: str) -> bool:
    if service_name in {"all", "api"}:
        return True
    return any(endpoint.path.startswith(prefix) for prefix in SERVICE_PREFIXES.get(service_name, ()))


def _full_path(endpoint: EndpointContract) -> str:
    if endpoint.authorization == "internal":
        return endpoint.path
    return f"/api/v1{endpoint.path}"


def _resource_for(path: str) -> str:
    parts = [part for part in path.split("/") if part and not part.startswith("{")]
    if not parts:
        return "operations"
    if parts[0] == "agents" and len(parts) > 1:
        return "agent_runs"
    return parts[0]


def _command_path(endpoint: EndpointContract) -> bool:
    markers = (
        "/agents/",
        "/trigger",
        "/re-crawl",
        "/generate",
        "/messages/send",
        "/follow-up",
        "/test",
    )
    return endpoint.method == "POST" and any(marker in endpoint.path for marker in markers)


def _agent_task_for(path: str) -> str:
    """Route async API operations to the canonical per-agent queue."""
    mappings = (
        (("crawler", "re-crawl"), "crawl"),
        (("content",), "content"),
        (("technical",), "technical"),
        (("rank", "keywords/import"), "rank"),
        (("backlink", "campaigns"), "outreach"),
        (("competitor",), "competitor"),
        (("self-heal", "messages/send"), "executor"),
    )
    for markers, task in mappings:
        if any(marker in path for marker in markers):
            return f"proactive.agent.{task}"
    return "proactive.agent.decision"


def _status_for(endpoint: EndpointContract) -> int:
    if endpoint.method == "DELETE":
        return 204
    if _command_path(endpoint):
        return 202
    if endpoint.method == "POST":
        return 201
    return 200


async def _request_values(request: Request, body: dict[str, Any] | None) -> dict[str, Any]:
    values = dict(body or {})
    values.update(request.path_params)
    return values


async def _verify_webhook(request: Request, body: dict[str, Any] | None) -> bool:
    timestamp = request.headers.get("x-webhook-timestamp", "")
    signature = request.headers.get("x-webhook-signature", "")
    try:
        timestamp_value = int(timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - timestamp_value) > 300:
        return False
    configured = request.app.state.settings.webhook_signing_secret
    secret = configured.get_secret_value() if configured else "local-webhook-secret"
    canonical = json.dumps(body or {}, separators=(",", ":"), sort_keys=True)
    digest = hmac.new(secret.encode(), f"{timestamp}.{canonical}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.removeprefix("sha256="), digest):
        return False
    replay_key = hashlib.sha256(f"{timestamp}.{signature}".encode()).hexdigest()
    if request.app.state.redis is not None:
        accepted = await request.app.state.redis.set(
            f"proactive:webhook-replay:{replay_key}",
            "1",
            ex=300,
            nx=True,
        )
        return bool(accepted)
    now = time.time()
    replay_cache: dict[str, float] = request.app.state.webhook_replays
    expired = [key for key, expires_at in replay_cache.items() if expires_at <= now]
    for key in expired:
        replay_cache.pop(key, None)
    if replay_key in replay_cache:
        return False
    replay_cache[replay_key] = now + 300
    return True


def _cursor_for(item_id: str) -> str:
    return base64.urlsafe_b64encode(item_id.encode()).rstrip(b"=").decode()


def _decode_cursor(cursor: str) -> str:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True).decode()
        if not decoded:
            raise ValueError("Cursor is empty")
        return decoded
    except Exception as exc:
        raise ValueError("Cursor is invalid") from exc


def _select_page(request: Request, items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None, bool]:
    """Apply stable UUID-ID pagination, equality filters, and sparse fieldsets."""
    reserved = {"limit", "cursor", "fields", "sort"}
    for key, value in request.query_params.items():
        if key not in reserved:
            items = [item for item in items if str(item.get(key, "")) == value]
    items = sorted(items, key=lambda item: str(item.get("id", "")))
    cursor_value = request.query_params.get("cursor")
    if cursor_value:
        after = _decode_cursor(cursor_value)
        items = [item for item in items if str(item.get("id", "")) > after]
    limit = min(max(int(request.query_params.get("limit", "50")), 1), 100)
    has_more = len(items) > limit
    page = items[:limit]
    fields = {field for field in request.query_params.get("fields", "").split(",") if field}
    if fields:
        fields.add("id")
        page = [{key: value for key, value in item.items() if key in fields} for item in page]
    next_cursor = _cursor_for(str(page[-1]["id"])) if has_more and page else None
    return page, next_cursor, has_more


async def _idempotency_get(request: Request, key: str, org_id: str, operation: str) -> dict[str, Any] | None:
    digest = hashlib.sha256(f"{org_id}:{operation}:{key}".encode()).hexdigest()
    if request.app.state.redis is not None:
        raw = await request.app.state.redis.get(f"proactive:idempotency:{digest}")
        return cast(dict[str, Any], json.loads(raw)) if raw else None
    return cast(dict[str, Any] | None, request.app.state.idempotency.get(digest))


async def _idempotency_put(
    request: Request,
    key: str,
    org_id: str,
    operation: str,
    value: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    digest = hashlib.sha256(f"{org_id}:{operation}:{key}".encode()).hexdigest()
    if request.app.state.redis is not None:
        redis_key = f"proactive:idempotency:{digest}"
        inserted = await request.app.state.redis.set(redis_key, json.dumps(value), ex=86_400, nx=True)
        if not inserted:
            raw = await request.app.state.redis.get(redis_key)
            if raw:
                return cast(dict[str, Any], json.loads(raw)), False
        return value, bool(inserted)
    existing = request.app.state.idempotency.get(digest)
    if existing is not None:
        return cast(dict[str, Any], existing), False
    request.app.state.idempotency[digest] = value
    return value, True


def _generic_handler(endpoint: EndpointContract) -> Any:
    async def operation(request: Request, body: dict[str, Any] | None = Body(default=None)) -> Response:
        principal = _principal(request) if endpoint.authorization not in {"none", "internal"} else None
        if principal is not None:
            require_role(principal, endpoint.authorization)
            org_id = encode_id(principal.org_id, "org")
        else:
            org_id = "internal"
        values = await _request_values(request, body)
        resource = _resource_for(endpoint.path)
        store: MemoryStore = request.app.state.store

        if endpoint.authorization == "internal":
            if not await _verify_webhook(request, body):
                return _problem(request, 401, "Invalid webhook", "A signed webhook is required")
            return _envelope(request, {"accepted": True, "provider": resource}, status_code=202)

        item_id = next(
            (value for key, value in request.path_params.items() if key in {"id", "page_id", "keyword_id", "issue_id"}),
            None,
        )
        if endpoint.method == "GET":
            if item_id is None:
                items = await store.list(resource, org_id)
                try:
                    page, cursor, has_more = _select_page(request, items)
                except (ValueError, UnicodeError):
                    return _problem(request, 400, "Invalid cursor", "The pagination cursor is malformed")
                return _envelope(request, page, cursor=cursor, has_more=has_more)
            item = await store.get(resource, item_id, org_id)
            if item is None:
                return _problem(request, 404, "Not found", "The requested tenant resource was not found")
            return _envelope(request, item)

        if endpoint.method == "DELETE":
            if item_id is None or not await store.delete(resource, item_id, org_id):
                return _problem(request, 404, "Not found", "The requested tenant resource was not found")
            return Response(status_code=204)

        if endpoint.method in {"PUT", "PATCH"} and item_id is not None:
            updated = await store.update(resource, item_id, org_id, values)
            if updated is None:
                return _problem(request, 404, "Not found", "The requested tenant resource was not found")
            return _envelope(request, updated)

        if _command_path(endpoint):
            idempotency_key = request.headers.get("idempotency-key") or values.get("idempotency_key")
            operation_name = f"{endpoint.method} {endpoint.path}"
            if idempotency_key:
                cached = await _idempotency_get(request, str(idempotency_key), org_id, operation_name)
                if cached is not None:
                    return _envelope(request, cached, status_code=202)
            task_uuid = uuid.uuid4()
            run_uuid = uuid.uuid4()
            task = {
                "task_id": encode_id(task_uuid, "tsk"),
                "run_id": encode_id(run_uuid, "run"),
                "status": "queued",
                "operation": operation_name,
                "approval_required": any(
                    value in endpoint.path for value in ("outreach", "pitch", "request", "self-heal", "send")
                ),
            }
            dispatch_task = True
            if idempotency_key:
                task, dispatch_task = await _idempotency_put(
                    request,
                    str(idempotency_key),
                    org_id,
                    operation_name,
                    task,
                )
            if dispatch_task and request.app.state.settings.task_dispatch_enabled and principal is not None:
                from proactive_core.celery_app import celery_app

                project_value = request.path_params.get("id")
                try:
                    project_id = decode_id(project_value, "prj") if project_value else uuid.uuid4()
                except ValueError:
                    project_id = uuid.uuid4()
                celery_app.send_task(
                    _agent_task_for(endpoint.path),
                    args=[
                        values,
                        {
                            "org_id": str(principal.org_id),
                            "project_id": str(project_id),
                            "run_id": str(run_uuid),
                            "correlation_id": str(run_uuid),
                            "trace_id": request.state.request_id,
                            "requested_by": str(principal.user_id),
                            "dry_run": not request.app.state.settings.live_actions_enabled,
                        },
                    ],
                    task_id=str(task_uuid),
                )
            return _envelope(request, task, status_code=202)

        prefix = RESOURCE_PREFIX.get(resource, "tsk")
        created = await store.create(resource, org_id, prefix, values)
        return _envelope(request, created, status_code=_status_for(endpoint))

    operation_slug = endpoint.path.strip("/").replace("/", "_")
    operation_slug = operation_slug.replace("{", "").replace("}", "").replace("-", "_")
    operation.__name__ = f"{endpoint.method.lower()}_{operation_slug}"
    operation.__doc__ = f"Implement `{endpoint.method} {endpoint.path}` from the stable v1 contract."
    return operation


def create_app(service_name: str = "all", settings: Settings | None = None) -> FastAPI:
    """Create an independently deployable service or the local aggregate API."""
    configure_logging()
    runtime = settings or get_settings().model_copy(update={"service_name": service_name})

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """Close database and Redis pools when the service stops."""
        yield
        if application.state.database is not None:
            await application.state.database.close()
        if application.state.redis is not None:
            await application.state.redis.aclose()

    app = FastAPI(
        title=f"ProActive SEO — {service_name}",
        version="1.0.0",
        docs_url="/docs" if runtime.env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = runtime
    if runtime.env in {"staging", "production"}:
        app.state.redis = Redis.from_url(runtime.redis_url, decode_responses=True)
        app.state.database = Database(runtime.database_url, echo=runtime.debug)
        app.state.store = PostgresStore(app.state.database, app.state.redis)
        app.state.tokens = TokenManager(runtime, RedisSessionStore(app.state.redis))
        app.state.limiter = RedisWindowLimiter(app.state.redis)
    else:
        app.state.redis = None
        app.state.database = None
        app.state.store = MemoryStore()
        app.state.tokens = TokenManager(runtime, MemorySessionStore())
        app.state.limiter = SlidingWindowLimiter()
    app.state.idempotency = {}
    app.state.webhook_replays = {}
    app.state.rate_contracts = [
        (
            compile_path(_full_path(endpoint))[0],
            endpoint.method,
            int(endpoint.rate_limit.split("/", 1)[0].split(" ", 1)[0]),
        )
        for endpoint in api_contract()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Response:
        request.state.request_id = request.headers.get("x-request-id") or secrets.token_hex(16)
        start = time.monotonic()
        response: Response
        limit = next(
            (
                configured
                for regex, method, configured in app.state.rate_contracts
                if method == request.method and regex.match(request.url.path)
            ),
            120,
        )
        allowed, remaining = await app.state.limiter.allow(
            f"{request.client.host if request.client else 'unknown'}:{request.url.path}", limit
        )
        if not allowed:
            response = _problem(request, 429, "Rate limit exceeded", "Retry after the current window")
            response.headers["Retry-After"] = "60"
            return response
        try:
            response = cast(Response, await call_next(request))
        finally:
            LATENCY.labels(service=service_name).observe(time.monotonic() - start)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        REQUESTS.labels(service=service_name, method=request.method, status=response.status_code).inc()
        return response

    @app.exception_handler(AuthenticationError)
    async def authentication_error(request: Request, exc: AuthenticationError) -> JSONResponse:
        return _problem(request, 401, "Authentication failed", str(exc))

    @app.exception_handler(AuthorizationError)
    async def authorization_error(request: Request, exc: AuthorizationError) -> JSONResponse:
        return _problem(request, 403, "Forbidden", str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        problem = _problem(request, 422, "Validation failed", "The request did not satisfy the schema")
        payload = Problem.model_validate_json(bytes(problem.body))
        payload.errors = [dict(item) for item in exc.errors()]
        return JSONResponse(payload.model_dump(mode="json"), status_code=422, media_type="application/problem+json")

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    @app.get("/health/ready", include_in_schema=False)
    async def ready() -> dict[str, str]:
        return {"status": "ready", "service": service_name}

    @app.get("/health/startup", include_in_schema=False)
    async def startup() -> dict[str, str]:
        return {"status": "started", "service": service_name}

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    contracts = tuple(item for item in api_contract() if _selected(item, service_name))
    contract_keys = {(item.method, item.path): item for item in contracts}

    if ("POST", "/auth/register") in contract_keys:

        @app.post("/api/v1/auth/register", status_code=201, response_model=Envelope[dict[str, Any]])
        async def register(request: Request, body: RegisterRequest) -> JSONResponse:
            try:
                organization, user = await app.state.store.register(
                    email=str(body.email),
                    password=body.password,
                    name=body.name,
                    organization_name=body.organization_name,
                )
            except ValueError as exc:
                return _problem(request, 409, "Account conflict", str(exc))
            user_uuid, org_uuid = app.state.store.token_identity(user)
            token_pair = await app.state.tokens.issue(user_id=user_uuid, org_id=org_uuid, role="owner")
            return _envelope(
                request,
                {"user": user, "organization": organization, "tokens": token_pair.model_dump()},
                status_code=201,
            )

    if ("POST", "/auth/login") in contract_keys:

        @app.post("/api/v1/auth/login", response_model=Envelope[dict[str, Any]])
        async def login(request: Request, body: LoginRequest) -> JSONResponse:
            user = await app.state.store.authenticate(str(body.email), body.password)
            if user is None:
                raise AuthenticationError("Email or password is incorrect")
            user_uuid, org_uuid = app.state.store.token_identity(user)
            token_pair = await app.state.tokens.issue(user_id=user_uuid, org_id=org_uuid, role=user["role"])
            public_user = app.state.store.public_user(user)
            return _envelope(request, {"user": public_user, "tokens": token_pair.model_dump()})

    if ("POST", "/auth/refresh") in contract_keys:

        @app.post("/api/v1/auth/refresh", response_model=Envelope[dict[str, Any]])
        async def refresh(request: Request, body: RefreshRequest) -> JSONResponse:
            pair = await app.state.tokens.rotate(body.refresh_token)
            return _envelope(request, pair.model_dump())

    if ("POST", "/auth/forgot-password") in contract_keys:

        @app.post("/api/v1/auth/forgot-password", response_model=Envelope[dict[str, bool]])
        async def forgot_password(request: Request, body: PasswordEmailRequest) -> JSONResponse:
            return _envelope(request, {"accepted": True})

    if ("POST", "/auth/reset-password") in contract_keys:

        @app.post("/api/v1/auth/reset-password", response_model=Envelope[dict[str, bool]])
        async def reset_password(request: Request, body: ResetPasswordRequest) -> JSONResponse:
            return _envelope(request, {"updated": True})

    concrete = {
        ("POST", "/auth/register"),
        ("POST", "/auth/login"),
        ("POST", "/auth/refresh"),
        ("POST", "/auth/forgot-password"),
        ("POST", "/auth/reset-password"),
    }
    for endpoint in sorted(contracts, key=lambda item: (item.path.count("{"), -len(item.path))):
        if (endpoint.method, endpoint.path) in concrete:
            continue
        if endpoint.path.startswith("/stream/"):

            async def stream(request: Request) -> StreamingResponse:
                _principal(request)

                async def events() -> AsyncIterator[str]:
                    last_id = request.headers.get("last-event-id", "0")
                    yield f'id: {last_id}\nevent: connected\ndata: {{"status":"connected"}}\n\n'
                    while True:
                        await asyncio.sleep(15)
                        yield ":heartbeat\n\n"

                return StreamingResponse(events(), media_type="text/event-stream")

            stream.__name__ = f"stream_{endpoint.path.rsplit('/', 1)[-1]}"
            app.add_api_route(_full_path(endpoint), stream, methods=[endpoint.method], status_code=200)
            continue
        app.add_api_route(
            _full_path(endpoint),
            _generic_handler(endpoint),
            methods=[endpoint.method],
            status_code=_status_for(endpoint),
            response_model=None if endpoint.method == "DELETE" else Envelope[Any],
            responses={401: {"model": Problem}, 403: {"model": Problem}, 404: {"model": Problem}},
        )
    return app


app = create_app()
