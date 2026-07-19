# SEO Platform — Complete API Specification v1

> **Version:** 1.0.0  
> **Base URL:** `https://api.seoplatform.com/api/v1`  
> **Protocol:** HTTPS only  
> **Content-Type:** `application/json`  
> **Date:** 2026-07-19

---

## Table of Contents

1. [Overview & Cross-Cutting Concerns](#1-overview--cross-cutting-concerns)
2. [Authentication & Authorization](#2-authentication--authorization)
3. [Request & Response Conventions](#3-request--response-conventions)
4. [Error Handling (RFC 7807)](#4-error-handling-rfc-7807)
5. [Rate Limiting](#5-rate-limiting)
6. [Pagination, Filtering & Sorting](#6-pagination-filtering--sorting)
7. [Webhooks](#7-webhooks)
8. [Real-time (SSE)](#8-real-time-sse)
9. [Auth & Users](#9-auth--users)
10. [Organizations](#10-organizations)
11. [Projects](#11-projects)
12. [Agents](#12-agents)
13. [Crawler Agent](#13-crawler-agent)
14. [Content Agent](#14-content-agent)
15. [Technical Agent](#15-technical-agent)
16. [Rank Agent](#16-rank-agent)
17. [Backlink & Outreach Agent](#17-backlink--outreach-agent)
18. [Campaigns](#18-campaigns)
19. [Integrations](#19-integrations)
20. [Reports](#20-reports)
21. [Webhooks Management](#21-webhooks-management)
22. [Real-time Streams](#22-real-time-streams)
23. [Appendix: Data Types & Enums](#23-appendix-data-types--enums)

---

## 1. Overview & Cross-Cutting Concerns

### 1.1 API Versioning

All endpoints are prefixed with `/api/v1`. Future versions will use `/api/v2`, etc. Clients may also send:

```
Accept: application/vnd.seoplatform.v1+json
```

If no version is specified in the Accept header, the URL prefix takes precedence. Deprecated versions will return a `Sunset` header with the deprecation date.

### 1.2 Common Request Headers

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes (except auth endpoints) | `Bearer <access_token>` |
| `Content-Type` | Yes (for bodies) | `application/json` |
| `Accept` | No | `application/json` (default) |
| `X-Request-Id` | No | Client-generated UUID for tracing. Server generates one if absent. |
| `X-Idempotency-Key` | No | UUID for idempotent POST/PATCH. Valid 24 hours. |
| `Accept-Language` | No | Preferred response language (e.g., `en`, `de`, `ja`). |

### 1.3 Common Response Headers

| Header | Description |
|---|---|
| `X-Request-Id` | Echoed or server-generated request ID |
| `X-RateLimit-Limit` | Max requests per window |
| `X-RateLimit-Remaining` | Remaining requests in current window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |
| `X-Total-Count` | Total items for list endpoints (when available) |
| `Sunset` | Deprecation date for versioned endpoints |

---

## 2. Authentication & Authorization

### 2.1 OAuth 2.0 + JWT

The platform supports:

- **Resource Owner Password Grant** (first-party apps)
- **Authorization Code + PKCE** (third-party apps)
- **Client Credentials** (service-to-service)

All flows yield a JWT access token (RS256-signed) and a refresh token.

**Access Token Payload:**

```json
{
  "sub": "usr_2xKp9mLqR3",
  "email": "user@example.com",
  "org_id": "org_8nQw4vBxT1",
  "org_role": "admin",
  "permissions": [
    "projects:read",
    "projects:write",
    "agents:trigger",
    "reports:generate"
  ],
  "iat": 1752960000,
  "exp": 1752963600,
  "iss": "https://auth.seoplatform.com",
  "aud": "https://api.seoplatform.com"
}
```

**Token Lifetimes:**
- Access token: 1 hour
- Refresh token: 30 days (rotate on use)
- ID token (OIDC): 1 hour

### 2.2 Scopes

| Scope | Description |
|---|---|
| `openid` | Standard OIDC |
| `profile` | User profile access |
| `email` | Email access |
| `org:read` | Organization read |
| `org:write` | Organization write |
| `projects:read` | Projects read |
| `projects:write` | Projects write |
| `agents:read` | Agent status/config read |
| `agents:trigger` | Trigger agent runs |
| `agents:configure` | Modify agent configuration |
| `reports:read` | Read reports |
| `reports:generate` | Generate reports |
| `campaigns:manage` | Manage outreach campaigns |
| `integrations:manage` | Manage third-party integrations |
| `admin` | Full administrative access |

### 2.3 Role-Based Access Control

| Role | Permissions |
|---|---|
| `owner` | All permissions, billing, delete org |
| `admin` | All except delete org, manage members |
| `manager` | Projects CRUD, agents, reports, campaigns |
| `analyst` | Read all, trigger agents, generate reports |
| `viewer` | Read-only access |
| `billing` | Billing and subscription management |

---

## 3. Request & Response Conventions

### 3.1 JSON Envelope

All responses use a consistent envelope:

**Single Resource:**

```json
{
  "data": { ... },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-07-19T12:00:00Z"
  }
}
```

**Collection (Paginated):**

```json
{
  "data": [ ... ],
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-07-19T12:00:00Z"
  },
  "pagination": {
    "cursor": "eyJpZCI6MTAwfQ==",
    "has_more": true,
    "total_count": 1542
  }
}
```

### 3.2 Field Selection

Use `fields` query parameter to select specific fields:

```
GET /api/v1/projects?fields=id,name,status,created_at
```

Nested fields use dot notation:

```
GET /api/v1/projects?fields=id,name,settings.crawl_frequency
```

### 3.3 Sorting

```
GET /api/v1/projects?sort=created_at:desc
GET /api/v1/projects?sort=name:asc,updated_at:desc
```

---

## 4. Error Handling (RFC 7807)

All errors follow [RFC 7807 Problem Details](https://tools.ietf.org/html/rfc7807):

```json
{
  "type": "https://api.seoplatform.com/errors/validation",
  "title": "Validation Error",
  "status": 422,
  "detail": "The request body contains invalid fields.",
  "instance": "/api/v1/projects",
  "request_id": "req_abc123",
  "errors": [
    {
      "field": "name",
      "code": "REQUIRED",
      "message": "Project name is required."
    },
    {
      "field": "url",
      "code": "INVALID_FORMAT",
      "message": "Must be a valid URL."
    }
  ]
}
```

### Standard Error Codes

| HTTP Status | Type Suffix | Title |
|---|---|---|
| 400 | `/bad-request` | Bad Request |
| 401 | `/unauthorized` | Unauthorized |
| 403 | `/forbidden` | Forbidden |
| 404 | `/not-found` | Not Found |
| 409 | `/conflict` | Conflict |
| 422 | `/validation` | Validation Error |
| 429 | `/rate-limited` | Too Many Requests |
| 500 | `/internal` | Internal Server Error |
| 502 | `/bad-gateway` | Bad Gateway |
| 503 | `/service-unavailable` | Service Unavailable |

### 429 Rate Limit Response

```json
{
  "type": "https://api.seoplatform.com/errors/rate-limited",
  "title": "Too Many Requests",
  "status": 429,
  "detail": "Rate limit exceeded. Retry after 32 seconds.",
  "retry_after": 32
}
```

Headers:
```
Retry-After: 32
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1752960032
```

---

## 5. Rate Limiting

### 5.1 Tiers

| Plan | Requests/min | Requests/hour | Burst |
|---|---|---|---|
| Free | 60 | 1,000 | 10 |
| Starter | 120 | 5,000 | 20 |
| Professional | 300 | 20,000 | 50 |
| Enterprise | 1,000 | 100,000 | 200 |
| Custom | Negotiable | Negotiable | Negotiable |

### 5.2 Per-Endpoint Limits

| Endpoint Category | Limit (per min) |
|---|---|
| Auth endpoints | 20 (login), 5 (register) |
| Agent triggers | 30 |
| Report generation | 10 |
| Bulk imports | 5 |
| Read endpoints | Tier default |
| Write endpoints | Tier default / 2 |

### 5.3 Rate Limit Headers

Every response includes:

```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 287
X-RateLimit-Reset: 1752960060
```

---

## 6. Pagination, Filtering & Sorting

### 6.1 Cursor-Based Pagination

All list endpoints use cursor-based pagination:

```
GET /api/v1/projects?limit=20&cursor=eyJpZCI6MTAwfQ==
```

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Items per page (max 100) |
| `cursor` | string | — | Opaque cursor from previous response |

**Response:**

```json
{
  "data": [...],
  "pagination": {
    "cursor": "eyJpZCI6MTIwfQ==",
    "has_more": true,
    "total_count": 542
  }
}
```

### 6.2 Filtering

Use `filter` query parameter with dot-notation:

```
GET /api/v1/projects?filter[status]=active&filter[created_at][gte]=2026-01-01
```

**Supported operators:**

| Operator | Description | Example |
|---|---|---|
| `eq` | Equals (default) | `filter[status]=active` |
| `neq` | Not equals | `filter[status][neq]=archived` |
| `gt` / `gte` | Greater than (or equal) | `filter[score][gte]=80` |
| `lt` / `lte` | Less than (or equal) | `filter[score][lte]=50` |
| `in` | In list | `filter[status][in]=active,paused` |
| `nin` | Not in list | `filter[type][nin]=test,demo` |
| `like` | Pattern match | `filter[name][like]=*competitor*` |
| `between` | Range | `filter[date][between]=2026-01-01,2026-06-30` |
| `is_null` | Is null | `filter[deleted_at][is_null]=true` |

### 6.3 Sorting

```
GET /api/v1/projects?sort=created_at:desc,name:asc
```

---

## 7. Webhooks

### 7.1 Event Types

| Event | Description |
|---|---|
| `agent.run.started` | Agent run began |
| `agent.run.completed` | Agent run finished |
| `agent.run.failed` | Agent run failed |
| `project.health.changed` | Project health score changed |
| `keyword.rank.changed` | Keyword rank changed significantly |
| `issue.detected` | New SEO issue detected |
| `issue.resolved` | Issue resolved |
| `campaign.status.changed` | Campaign status updated |
| `campaign.message.replied` | Outreach reply received |
| `report.generated` | Report generation completed |
| `integration.disconnected` | Integration lost connection |

### 7.2 Webhook Payload

```json
{
  "id": "evt_3xKp9mLqR3",
  "type": "agent.run.completed",
  "created_at": "2026-07-19T12:00:00Z",
  "data": { ... },
  "metadata": {
    "org_id": "org_8nQw4vBxT1",
    "project_id": "prj_5tYu2wErT8"
  }
}
```

### 7.3 Delivery & Retry

- Webhooks are delivered via HTTPS POST
- Payload signed with HMAC-SHA256 (`X-Webhook-Signature` header)
- Retries: 5 attempts with exponential backoff (1min, 5min, 30min, 2hr, 24hr)
- Timeout: 30 seconds per delivery
- Failed deliveries logged and available via API

**Signature Verification:**

```
X-Webhook-Signature: sha256=<hex-encoded-hmac>
X-Webhook-Timestamp: 1752960000
```

Client should verify:
```python
import hmac, hashlib
expected = hmac.new(
    secret.encode(),
    f"{timestamp}.{body}".encode(),
    hashlib.sha256
).hexdigest()
assert hmac.compare_digest(f"sha256={expected}", signature)
```

---

## 8. Real-time (SSE)

Server-Sent Events for real-time updates:

```
GET /api/v1/stream/agents
Authorization: Bearer <token>
Accept: text/event-stream
```

**SSE Event Format:**

```
event: agent.run.progress
id: evt_abc123
data: {"agent_id":"agt_crawler","run_id":"run_xyz","progress":45,"message":"Crawled 450/1000 pages"}

event: agent.run.completed
id: evt_def456
data: {"agent_id":"agt_crawler","run_id":"run_xyz","status":"completed","summary":{"pages_crawled":1000,"issues_found":23}}
```

**Connection Management:**
- Heartbeat every 15 seconds (`:heartbeat`)
- Client should reconnect with `Last-Event-ID` header
- Max connection duration: 24 hours (reconnect after)

---

## 9. Auth & Users

---

### 9.1 POST /api/v1/auth/register

Register a new user account.

**Auth:** None  
**Rate Limit:** 5/min per IP

**Request Body:**

```json
{
  "email": "newuser@example.com",
  "password": "SecureP@ssw0rd!",
  "first_name": "Jane",
  "last_name": "Doe",
  "organization_name": "Acme Corp",
  "accept_terms": true,
  "marketing_opt_in": false,
  "referral_code": "REF123"
}
```

**Request Schema:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `email` | string | Yes | Valid email, max 255 chars |
| `password` | string | Yes | Min 12 chars, 1 upper, 1 lower, 1 digit, 1 special |
| `first_name` | string | Yes | 1-100 chars |
| `last_name` | string | Yes | 1-100 chars |
| `organization_name` | string | No | 1-200 chars. Creates org if provided. |
| `accept_terms` | boolean | Yes | Must be `true` |
| `marketing_opt_in` | boolean | No | Default `false` |
| `referral_code` | string | No | 6-20 alphanumeric chars |

**Response (201 Created):**

```json
{
  "data": {
    "id": "usr_2xKp9mLqR3",
    "email": "newuser@example.com",
    "first_name": "Jane",
    "last_name": "Doe",
    "email_verified": false,
    "organization": {
      "id": "org_8nQw4vBxT1",
      "name": "Acme Corp",
      "role": "owner"
    },
    "created_at": "2026-07-19T12:00:00Z"
  },
  "meta": {
    "request_id": "req_abc123"
  }
}
```

**Error Responses:**

| Status | Type | Condition |
|---|---|---|
| 409 | `/errors/conflict` | Email already registered |
| 422 | `/errors/validation` | Invalid input |

**Example cURL:**

```bash
curl -X POST https://api.seoplatform.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "SecureP@ssw0rd!",
    "first_name": "Jane",
    "last_name": "Doe",
    "organization_name": "Acme Corp",
    "accept_terms": true
  }'
```

---

### 9.2 POST /api/v1/auth/login

Authenticate and receive tokens.

**Auth:** None  
**Rate Limit:** 20/min per IP

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "SecureP@ssw0rd!",
  "mfa_code": "123456",
  "remember_me": true
}
```

**Request Schema:**

| Field | Type | Required | Description |
|---|---|---|---|
| `email` | string | Yes | User email |
| `password` | string | Yes | User password |
| `mfa_code` | string | No | TOTP code (required if MFA enabled) |
| `remember_me` | boolean | No | Extended refresh token (90 days) |

**Response (200 OK):**

```json
{
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIs...",
    "refresh_token": "rt_7yHn3mKp9vBxT2wE...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": "openid profile email projects:read",
    "user": {
      "id": "usr_2xKp9mLqR3",
      "email": "user@example.com",
      "first_name": "Jane",
      "last_name": "Doe",
      "avatar_url": "https://cdn.seoplatform.com/avatars/usr_2xKp9mLqR3.jpg",
      "organization": {
        "id": "org_8nQw4vBxT1",
        "name": "Acme Corp",
        "role": "admin"
      },
      "mfa_enabled": true,
      "preferences": {
        "language": "en",
        "timezone": "America/New_York",
        "theme": "dark"
      }
    },
    "mfa_required": false
  },
  "meta": {
    "request_id": "req_abc123"
  }
}
```

**If MFA Required (200 OK):**

```json
{
  "data": {
    "mfa_required": true,
    "mfa_challenge_token": "mfa_ch_4tRw8yUp3x",
    "mfa_methods": ["totp", "sms", "email"]
  }
}
```

**Error Responses:**

| Status | Type | Condition |
|---|---|---|
| 401 | `/errors/unauthorized` | Invalid credentials |
| 423 | `/errors/locked` | Account locked (too many attempts) |
| 403 | `/errors/forbidden` | Account suspended |

**Example cURL:**

```bash
curl -X POST https://api.seoplatform.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecureP@ssw0rd!",
    "remember_me": true
  }'
```

---

### 9.3 POST /api/v1/auth/refresh

Refresh an expired access token.

**Auth:** Refresh token  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "refresh_token": "rt_7yHn3mKp9vBxT2wE..."
}
```

**Response (200 OK):**

```json
{
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIs...",
    "refresh_token": "rt_new_token_here...",
    "token_type": "Bearer",
    "expires_in": 3600
  }
}
```

**Error Responses:**

| Status | Type | Condition |
|---|---|---|
| 401 | `/errors/unauthorized` | Invalid/expired refresh token |
| 401 | `/errors/token-revoked` | Token was revoked (reuse detection) |

---

### 9.4 POST /api/v1/auth/forgot-password

Initiate password reset.

**Auth:** None  
**Rate Limit:** 3/min per email, 10/min per IP

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "message": "If an account exists with this email, a reset link has been sent."
  }
}
```

> Always returns 202 to prevent email enumeration.

---

### 9.5 POST /api/v1/auth/reset-password

Complete password reset with token.

**Auth:** None  
**Rate Limit:** 5/min per IP

**Request Body:**

```json
{
  "token": "rst_4tRw8yUp3xBn5mKq...",
  "new_password": "NewSecureP@ssw0rd!"
}
```

**Response (200 OK):**

```json
{
  "data": {
    "message": "Password reset successfully. All existing sessions have been invalidated.",
    "sessions_invalidated": 3
  }
}
```

**Error Responses:**

| Status | Type | Condition |
|---|---|---|
| 400 | `/errors/bad-request` | Invalid/expired token |
| 422 | `/errors/validation` | Password doesn't meet requirements |

---

### 9.6 GET /api/v1/users/me

Get current user profile.

**Auth:** Bearer token (any authenticated user)  
**Rate Limit:** 120/min

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `fields` | string | Comma-separated field list |

**Response (200 OK):**

```json
{
  "data": {
    "id": "usr_2xKp9mLqR3",
    "email": "user@example.com",
    "first_name": "Jane",
    "last_name": "Doe",
    "avatar_url": "https://cdn.seoplatform.com/avatars/usr_2xKp9mLqR3.jpg",
    "email_verified": true,
    "mfa_enabled": true,
    "organization": {
      "id": "org_8nQw4vBxT1",
      "name": "Acme Corp",
      "role": "admin",
      "plan": "professional"
    },
    "preferences": {
      "language": "en",
      "timezone": "America/New_York",
      "theme": "dark",
      "notifications": {
        "email": true,
        "browser": true,
        "slack": false
      }
    },
    "usage": {
      "projects": 12,
      "projects_limit": 50,
      "api_calls_today": 1247,
      "api_calls_limit": 20000
    },
    "created_at": "2025-01-15T10:30:00Z",
    "last_login_at": "2026-07-19T08:15:00Z"
  }
}
```

---

### 9.7 PUT /api/v1/users/me

Update current user profile.

**Auth:** Bearer token  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "avatar_url": "https://example.com/avatar.jpg",
  "preferences": {
    "language": "en",
    "timezone": "Europe/London",
    "theme": "light",
    "notifications": {
      "email": true,
      "slack": true
    }
  }
}
```

**Response (200 OK):** Returns full updated user object (same as GET /users/me).

---

### 9.8 GET /api/v1/users

List all users in the organization (admin only).

**Auth:** Bearer token (`admin` role)  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max items (1-100) |
| `cursor` | string | — | Pagination cursor |
| `fields` | string | all | Field selection |
| `sort` | string | `created_at:desc` | Sort field and direction |
| `filter[role]` | string | — | Filter by role |
| `filter[status]` | string | — | `active`, `suspended`, `invited` |
| `filter[q]` | string | — | Search by name/email |

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "usr_2xKp9mLqR3",
      "email": "user@example.com",
      "first_name": "Jane",
      "last_name": "Doe",
      "role": "admin",
      "status": "active",
      "last_login_at": "2026-07-19T08:15:00Z",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MTAwfQ==",
    "has_more": true,
    "total_count": 45
  }
}
```

---

### 9.9 POST /api/v1/users

Create a new user (admin only, sends invite email).

**Auth:** Bearer token (`admin` role)  
**Rate Limit:** 20/min

**Request Body:**

```json
{
  "email": "newuser@example.com",
  "first_name": "Bob",
  "last_name": "Smith",
  "role": "analyst",
  "projects": ["prj_5tYu2wErT8", "prj_9kLm3nPqR7"],
  "send_invite": true
}
```

**Response (201 Created):**

```json
{
  "data": {
    "id": "usr_7bNm4vCxW2",
    "email": "newuser@example.com",
    "first_name": "Bob",
    "last_name": "Smith",
    "role": "analyst",
    "status": "invited",
    "created_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 9.10 GET /api/v1/users/{id}

Get a specific user (admin only).

**Auth:** Bearer token (`admin` role)  
**Rate Limit:** 120/min

**Response (200 OK):** Full user object.

**Error Responses:**

| Status | Type | Condition |
|---|---|---|
| 404 | `/errors/not-found` | User not found in organization |

---

### 9.11 PUT /api/v1/users/{id}

Update a specific user (admin only).

**Auth:** Bearer token (`admin` role)  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "first_name": "Robert",
  "role": "manager",
  "status": "active",
  "projects": ["prj_5tYu2wErT8"]
}
```

**Response (200 OK):** Updated user object.

---

### 9.12 DELETE /api/v1/users/{id}

Deactivate a user (admin only). Does not delete — sets status to `deactivated`.

**Auth:** Bearer token (`admin` role)  
**Rate Limit:** 10/min

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `transfer_to` | string | User ID to transfer ownership of resources |

**Response (200 OK):**

```json
{
  "data": {
    "id": "usr_7bNm4vCxW2",
    "status": "deactivated",
    "resources_transferred_to": "usr_2xKp9mLqR3",
    "deactivated_at": "2026-07-19T12:00:00Z"
  }
}
```

---

## 10. Organizations

---

### 10.1 GET /api/v1/organizations

List organizations the current user belongs to.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "org_8nQw4vBxT1",
      "name": "Acme Corp",
      "slug": "acme-corp",
      "role": "admin",
      "plan": "professional",
      "member_count": 25,
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

---

### 10.2 POST /api/v1/organizations

Create a new organization.

**Auth:** Bearer token  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "name": "New Agency",
  "slug": "new-agency",
  "billing_email": "billing@agency.com",
  "industry": "marketing_agency",
  "size": "11-50",
  "website": "https://agency.com"
}
```

**Request Schema:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `name` | string | Yes | 1-200 chars |
| `slug` | string | No | 3-50 chars, lowercase, hyphens. Auto-generated if omitted. |
| `billing_email` | string | Yes | Valid email |
| `industry` | string | No | Enum: `marketing_agency`, `ecommerce`, `saas`, `media`, `enterprise`, `other` |
| `size` | string | No | Enum: `1-10`, `11-50`, `51-200`, `201-1000`, `1000+` |
| `website` | string | No | Valid URL |

**Response (201 Created):**

```json
{
  "data": {
    "id": "org_3kLm9nPqR7",
    "name": "New Agency",
    "slug": "new-agency",
    "role": "owner",
    "plan": "free",
    "billing_email": "billing@agency.com",
    "settings": {
      "default_crawl_frequency": "weekly",
      "timezone": "UTC",
      "branding": {
        "logo_url": null,
        "primary_color": "#1a73e8"
      }
    },
    "created_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 10.3 GET /api/v1/organizations/{id}

Get organization details.

**Auth:** Bearer token (member of org)  
**Rate Limit:** 120/min

**Response (200 OK):**

```json
{
  "data": {
    "id": "org_8nQw4vBxT1",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "role": "admin",
    "plan": "professional",
    "billing_email": "billing@acme.com",
    "industry": "saas",
    "size": "51-200",
    "website": "https://acme.com",
    "member_count": 25,
    "project_count": 12,
    "settings": {
      "default_crawl_frequency": "weekly",
      "timezone": "America/New_York",
      "branding": {
        "logo_url": "https://cdn.seoplatform.com/logos/org_8nQw4vBxT1.png",
        "primary_color": "#ff6600"
      },
      "notifications": {
        "slack_webhook": "https://hooks.slack.com/services/xxx",
        "default_email_digest": "weekly"
      }
    },
    "usage": {
      "projects": 12,
      "projects_limit": 50,
      "pages_crawled_this_month": 45000,
      "pages_crawl_limit": 500000,
      "api_calls_today": 8420,
      "api_calls_limit": 100000
    },
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2026-07-10T14:22:00Z"
  }
}
```

---

### 10.4 PUT /api/v1/organizations/{id}

Update organization settings.

**Auth:** Bearer token (`admin`/`owner` role)  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "name": "Acme Corporation",
  "settings": {
    "default_crawl_frequency": "daily",
    "timezone": "America/Chicago",
    "notifications": {
      "slack_webhook": "https://hooks.slack.com/services/new_xxx"
    }
  }
}
```

**Response (200 OK):** Updated organization object.

---

### 10.5 DELETE /api/v1/organizations/{id}

Delete organization (owner only). Requires confirmation.

**Auth:** Bearer token (`owner` role)  
**Rate Limit:** 1/min

**Request Body:**

```json
{
  "confirmation": "DELETE acme-corp",
  "transfer_projects_to": "org_other_org_id"
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "id": "org_8nQw4vBxT1",
    "status": "deletion_scheduled",
    "deletion_date": "2026-08-19T12:00:00Z",
    "message": "Organization scheduled for deletion in 30 days. Contact support to cancel."
  }
}
```

---

### 10.6 GET /api/v1/organizations/{id}/members

List organization members.

**Auth:** Bearer token (member of org)  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max items |
| `cursor` | string | — | Pagination cursor |
| `filter[role]` | string | — | Filter by role |
| `filter[status]` | string | — | `active`, `invited`, `suspended` |
| `filter[q]` | string | — | Search name/email |
| `sort` | string | `name:asc` | Sort field |

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "usr_2xKp9mLqR3",
      "email": "jane@acme.com",
      "first_name": "Jane",
      "last_name": "Doe",
      "role": "admin",
      "status": "active",
      "avatar_url": "https://cdn.seoplatform.com/avatars/usr_2xKp9mLqR3.jpg",
      "last_active_at": "2026-07-19T08:15:00Z",
      "joined_at": "2025-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MjB9",
    "has_more": true,
    "total_count": 25
  }
}
```

---

### 10.7 POST /api/v1/organizations/{id}/invite

Invite a new member to the organization.

**Auth:** Bearer token (`admin`/`owner` role)  
**Rate Limit:** 20/min

**Request Body:**

```json
{
  "email": "newmember@acme.com",
  "role": "analyst",
  "projects": ["prj_5tYu2wErT8"],
  "message": "Welcome to the SEO team!",
  "expires_in_days": 7
}
```

**Response (201 Created):**

```json
{
  "data": {
    "id": "inv_4tRw8yUp3x",
    "email": "newmember@acme.com",
    "role": "analyst",
    "status": "pending",
    "expires_at": "2026-07-26T12:00:00Z",
    "invited_by": {
      "id": "usr_2xKp9mLqR3",
      "name": "Jane Doe"
    },
    "created_at": "2026-07-19T12:00:00Z"
  }
}
```

**Error Responses:**

| Status | Type | Condition |
|---|---|---|
| 409 | `/errors/conflict` | User already a member |
| 422 | `/errors/validation` | Member limit reached for plan |

---

## 11. Projects

---

### 11.1 GET /api/v1/projects

List projects in the organization.

**Auth:** Bearer token  
**Rate Limit:** 120/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max items |
| `cursor` | string | — | Pagination cursor |
| `fields` | string | all | Field selection |
| `sort` | string | `created_at:desc` | Sort |
| `filter[status]` | string | — | `active`, `paused`, `archived` |
| `filter[q]` | string | — | Search name/domain |

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "prj_5tYu2wErT8",
      "name": "Main Website",
      "domain": "acme.com",
      "url": "https://www.acme.com",
      "status": "active",
      "health_score": 87,
      "health_trend": "improving",
      "pages_count": 1247,
      "keywords_tracked": 350,
      "open_issues": 12,
      "last_crawl_at": "2026-07-18T06:00:00Z",
      "created_at": "2025-03-10T14:00:00Z",
      "updated_at": "2026-07-18T06:30:00Z"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MjB9",
    "has_more": false,
    "total_count": 12
  }
}
```

---

### 11.2 POST /api/v1/projects

Create a new project.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "name": "Main Website",
  "url": "https://www.acme.com",
  "domain": "acme.com",
  "description": "Primary corporate website",
  "settings": {
    "crawl_frequency": "weekly",
    "max_pages": 10000,
    "respect_robots_txt": true,
    "crawl_javascript": true,
    "user_agent": "SEOPlatformBot/1.0",
    "include_subdomains": false,
    "excluded_paths": ["/admin/*", "/api/*"],
    "target_countries": ["US", "GB", "DE"],
    "target_languages": ["en", "de"],
    "competitors": [
      "https://competitor1.com",
      "https://competitor2.com"
    ]
  },
  "tags": ["corporate", "main", "priority"]
}
```

**Request Schema:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `name` | string | Yes | 1-200 chars |
| `url` | string | Yes | Valid URL |
| `domain` | string | Yes | Valid domain |
| `description` | string | No | Max 1000 chars |
| `settings` | object | No | Project settings |
| `tags` | array | No | Max 20 tags, 1-50 chars each |

**Response (201 Created):**

```json
{
  "data": {
    "id": "prj_9kLm3nPqR7",
    "name": "Main Website",
    "domain": "acme.com",
    "url": "https://www.acme.com",
    "status": "active",
    "health_score": null,
    "settings": {
      "crawl_frequency": "weekly",
      "max_pages": 10000,
      "respect_robots_txt": true,
      "crawl_javascript": true,
      "include_subdomains": false,
      "excluded_paths": ["/admin/*", "/api/*"],
      "target_countries": ["US", "GB", "DE"],
      "target_languages": ["en", "de"],
      "competitors": [
        "https://competitor1.com",
        "https://competitor2.com"
      ]
    },
    "tags": ["corporate", "main", "priority"],
    "created_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 11.3 GET /api/v1/projects/{id}

Get project details.

**Auth:** Bearer token  
**Rate Limit:** 120/min

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `fields` | string | Field selection |

**Response (200 OK):** Full project object with settings and metadata.

---

### 11.4 PUT /api/v1/projects/{id}

Update project.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 30/min

**Request Body:** Partial update — only include fields to change.

```json
{
  "name": "Updated Name",
  "settings": {
    "crawl_frequency": "daily",
    "max_pages": 20000
  }
}
```

**Response (200 OK):** Updated project object.

---

### 11.5 DELETE /api/v1/projects/{id}

Delete project (soft delete, recoverable for 30 days).

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 5/min

**Response (200 OK):**

```json
{
  "data": {
    "id": "prj_5tYu2wErT8",
    "status": "deleted",
    "recoverable_until": "2026-08-19T12:00:00Z"
  }
}
```

---

### 11.6 GET /api/v1/projects/{id}/dashboard

Get project dashboard summary with key metrics.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `period` | string | `30d` | `7d`, `30d`, `90d`, `1y`, `custom` |
| `from` | string | — | Start date (ISO 8601, for custom period) |
| `to` | string | — | End date (ISO 8601, for custom period) |

**Response (200 OK):**

```json
{
  "data": {
    "project": {
      "id": "prj_5tYu2wErT8",
      "name": "Main Website",
      "domain": "acme.com"
    },
    "period": "30d",
    "health_score": {
      "current": 87,
      "previous": 82,
      "change": 5,
      "breakdown": {
        "technical": 92,
        "content": 85,
        "authority": 78,
        "performance": 89
      }
    },
    "traffic": {
      "organic_sessions": 145000,
      "organic_sessions_change": 12.5,
      "organic_users": 98000,
      "organic_users_change": 10.2,
      "bounce_rate": 42.3,
      "avg_session_duration": 185
    },
    "rankings": {
      "total_keywords": 350,
      "top_3": 28,
      "top_10": 67,
      "top_20": 112,
      "improved": 45,
      "declined": 12,
      "new": 8,
      "avg_position": 18.4,
      "visibility_score": 72.3
    },
    "issues": {
      "total": 47,
      "critical": 3,
      "high": 12,
      "medium": 18,
      "low": 14,
      "resolved_this_period": 23
    },
    "content": {
      "total_pages": 1247,
      "indexed_pages": 1180,
      "pages_with_issues": 89,
      "avg_content_score": 74.5,
      "new_pages": 12,
      "updated_pages": 45
    },
    "backlinks": {
      "total": 3420,
      "new": 45,
      "lost": 12,
      "referring_domains": 890,
      "domain_authority": 62
    },
    "agents": {
      "last_run": {
        "agent": "crawler",
        "status": "completed",
        "completed_at": "2026-07-18T06:30:00Z"
      },
      "active_runs": 0,
      "scheduled_runs_today": 3
    },
    "trends": {
      "health_score": [
        {"date": "2026-06-19", "value": 82},
        {"date": "2026-06-26", "value": 83},
        {"date": "2026-07-03", "value": 85},
        {"date": "2026-07-10", "value": 84},
        {"date": "2026-07-17", "value": 87}
      ],
      "organic_traffic": [
        {"date": "2026-06-19", "value": 128000},
        {"date": "2026-06-26", "value": 132000},
        {"date": "2026-07-03", "value": 138000},
        {"date": "2026-07-10", "value": 141000},
        {"date": "2026-07-17", "value": 145000}
      ]
    }
  }
}
```

---

### 11.7 GET /api/v1/projects/{id}/health-score

Get detailed health score breakdown.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `period` | string | `30d` | Time period for comparison |

**Response (200 OK):**

```json
{
  "data": {
    "overall_score": 87,
    "overall_grade": "B+",
    "previous_score": 82,
    "change": 5,
    "breakdown": {
      "technical": {
        "score": 92,
        "grade": "A",
        "weight": 0.30,
        "factors": [
          {"name": "Core Web Vitals", "score": 95, "status": "good"},
          {"name": "Mobile Usability", "score": 98, "status": "good"},
          {"name": "HTTPS", "score": 100, "status": "good"},
          {"name": "Structured Data", "score": 78, "status": "needs_improvement"},
          {"name": "Crawlability", "score": 90, "status": "good"}
        ]
      },
      "content": {
        "score": 85,
        "grade": "B",
        "weight": 0.25,
        "factors": [
          {"name": "Title Tags", "score": 90, "status": "good"},
          {"name": "Meta Descriptions", "score": 82, "status": "good"},
          {"name": "Heading Structure", "score": 88, "status": "good"},
          {"name": "Content Quality", "score": 76, "status": "needs_improvement"},
          {"name": "Internal Linking", "score": 85, "status": "good"}
        ]
      },
      "authority": {
        "score": 78,
        "grade": "C+",
        "weight": 0.25,
        "factors": [
          {"name": "Domain Authority", "score": 62, "status": "needs_improvement"},
          {"name": "Backlink Quality", "score": 75, "status": "good"},
          {"name": "Referring Domains", "score": 80, "status": "good"},
          {"name": "Toxic Links", "score": 95, "status": "good"}
        ]
      },
      "performance": {
        "score": 89,
        "grade": "B+",
        "weight": 0.20,
        "factors": [
          {"name": "Page Speed", "score": 88, "status": "good"},
          {"name": "LCP", "score": 85, "status": "good"},
          {"name": "FID", "score": 92, "status": "good"},
          {"name": "CLS", "score": 90, "status": "good"}
        ]
      }
    },
    "recommendations": [
      {
        "priority": "high",
        "category": "technical",
        "action": "Fix 3 critical structured data errors on product pages",
        "impact": "+3 points estimated"
      },
      {
        "priority": "medium",
        "category": "content",
        "action": "Improve thin content on 15 blog posts (under 500 words)",
        "impact": "+2 points estimated"
      }
    ],
    "calculated_at": "2026-07-18T06:30:00Z"
  }
}
```

---

## 12. Agents

---

### 12.1 GET /api/v1/agents

List all available agents and their status.

**Auth:** Bearer token  
**Rate Limit:** 120/min

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "agt_crawler",
      "name": "Crawler Agent",
      "description": "Website crawling and technical SEO analysis",
      "type": "crawler",
      "status": "active",
      "enabled": true,
      "last_run": {
        "id": "run_abc123",
        "status": "completed",
        "started_at": "2026-07-18T06:00:00Z",
        "completed_at": "2026-07-18T06:30:00Z",
        "duration_seconds": 1800
      },
      "next_scheduled_run": "2026-07-25T06:00:00Z",
      "schedule": {
        "frequency": "weekly",
        "day": "monday",
        "time": "06:00",
        "timezone": "America/New_York"
      },
      "capabilities": [
        "full_site_crawl",
        "page_analysis",
        "issue_detection",
        "sitemap_generation"
      ]
    },
    {
      "id": "agt_content",
      "name": "Content Agent",
      "description": "Content optimization and generation",
      "type": "content",
      "status": "active",
      "enabled": true,
      "capabilities": [
        "content_audit",
        "meta_optimization",
        "geo_check",
        "keyword_gap",
        "brief_generation",
        "draft_generation"
      ]
    },
    {
      "id": "agt_technical",
      "name": "Technical Agent",
      "description": "Technical SEO auditing and self-healing",
      "type": "technical",
      "status": "active",
      "enabled": true,
      "capabilities": [
        "technical_audit",
        "schema_generation",
        "self_healing",
        "multi_engine_optimization"
      ]
    },
    {
      "id": "agt_rank",
      "name": "Rank Agent",
      "description": "Keyword tracking and SERP analysis",
      "type": "rank",
      "status": "active",
      "enabled": true,
      "capabilities": [
        "keyword_tracking",
        "serp_analysis",
        "competitor_tracking",
        "rank_monitoring"
      ]
    },
    {
      "id": "agt_backlink",
      "name": "Backlink & Outreach Agent",
      "description": "Link building and outreach automation",
      "type": "backlink",
      "status": "active",
      "enabled": true,
      "capabilities": [
        "haro_parsing",
        "broken_link_building",
        "guest_post_outreach",
        "unlinked_mention_reclamation",
        "backlink_monitoring"
      ]
    }
  ]
}
```

---

### 12.2 GET /api/v1/agents/{id}/runs

List agent run history.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max items |
| `cursor` | string | — | Pagination cursor |
| `filter[status]` | string | — | `running`, `completed`, `failed`, `cancelled` |
| `filter[project_id]` | string | — | Filter by project |
| `sort` | string | `started_at:desc` | Sort |

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "run_abc123",
      "agent_id": "agt_crawler",
      "project_id": "prj_5tYu2wErT8",
      "status": "completed",
      "trigger": "scheduled",
      "started_at": "2026-07-18T06:00:00Z",
      "completed_at": "2026-07-18T06:30:00Z",
      "duration_seconds": 1800,
      "progress": 100,
      "summary": {
        "pages_crawled": 1247,
        "issues_found": 47,
        "new_issues": 5,
        "resolved_issues": 0
      },
      "error": null
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MjB9",
    "has_more": true,
    "total_count": 156
  }
}
```

---

### 12.3 POST /api/v1/agents/{id}/trigger

Manually trigger an agent run.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "priority": "normal",
  "config_override": {
    "max_pages": 500,
    "depth": 3
  },
  "callback_url": "https://webhook.site/abc123"
}
```

**Request Schema:**

| Field | Type | Required | Description |
|---|---|---|---|
| `project_id` | string | Yes | Target project |
| `priority` | string | No | `low`, `normal`, `high` (default: `normal`) |
| `config_override` | object | No | Override agent config for this run |
| `callback_url` | string | No | Webhook URL for completion notification |

**Response (202 Accepted):**

```json
{
  "data": {
    "id": "run_def456",
    "agent_id": "agt_crawler",
    "project_id": "prj_5tYu2wErT8",
    "status": "queued",
    "priority": "normal",
    "estimated_duration_seconds": 1800,
    "queued_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 12.4 GET /api/v1/agents/{id}/config

Get agent configuration.

**Auth:** Bearer token  
**Rate Limit:** 120/min

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `project_id` | string | Get project-specific config (defaults to org-level) |

**Response (200 OK):**

```json
{
  "data": {
    "agent_id": "agt_crawler",
    "project_id": "prj_5tYu2wErT8",
    "config": {
      "max_pages_per_crawl": 10000,
      "max_depth": 10,
      "crawl_rate": 10,
      "respect_robots_txt": true,
      "crawl_javascript": true,
      "javascript_wait_ms": 3000,
      "user_agent": "SEOPlatformBot/1.0",
      "timeout_ms": 30000,
      "retry_failed": true,
      "max_retries": 3,
      "excluded_patterns": ["/admin/*", "/api/*", "*.pdf"],
      "included_patterns": [],
      "custom_headers": {},
      "cookies": []
    },
    "updated_at": "2026-07-10T14:22:00Z",
    "updated_by": "usr_2xKp9mLqR3"
  }
}
```

---

### 12.5 PUT /api/v1/agents/{id}/config

Update agent configuration.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "config": {
    "max_pages_per_crawl": 20000,
    "crawl_rate": 20,
    "crawl_javascript": true
  }
}
```

**Response (200 OK):** Updated config object.

---

### 12.6 GET /api/v1/agents/{id}/schedules

List agent schedules.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "sch_abc123",
      "agent_id": "agt_crawler",
      "project_id": "prj_5tYu2wErT8",
      "frequency": "weekly",
      "day_of_week": "monday",
      "time": "06:00",
      "timezone": "America/New_York",
      "enabled": true,
      "last_run_at": "2026-07-14T06:00:00Z",
      "next_run_at": "2026-07-21T06:00:00Z",
      "created_at": "2025-03-15T10:00:00Z"
    }
  ]
}
```

---

### 12.7 POST /api/v1/agents/{id}/schedules

Create an agent schedule.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "frequency": "weekly",
  "day_of_week": "wednesday",
  "time": "02:00",
  "timezone": "America/New_York",
  "enabled": true,
  "config_override": {
    "max_pages": 5000
  }
}
```

**Request Schema:**

| Field | Type | Required | Description |
|---|---|---|---|
| `project_id` | string | Yes | Target project |
| `frequency` | string | Yes | `daily`, `weekly`, `biweekly`, `monthly` |
| `day_of_week` | string | Conditional | Required for weekly/biweekly. `monday`-`sunday` |
| `day_of_month` | integer | Conditional | Required for monthly. 1-28 |
| `time` | string | Yes | HH:MM (24h format) |
| `timezone` | string | No | IANA timezone (default: org timezone) |
| `enabled` | boolean | No | Default: true |
| `config_override` | object | No | Override agent config for scheduled runs |

**Response (201 Created):**

```json
{
  "data": {
    "id": "sch_def456",
    "agent_id": "agt_crawler",
    "project_id": "prj_5tYu2wErT8",
    "frequency": "weekly",
    "day_of_week": "wednesday",
    "time": "02:00",
    "timezone": "America/New_York",
    "enabled": true,
    "next_run_at": "2026-07-23T02:00:00Z",
    "created_at": "2026-07-19T12:00:00Z"
  }
}
```

---

## 13. Crawler Agent

---

### 13.1 POST /api/v1/agents/crawler/scan

Initiate a full site crawl.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "url": "https://www.acme.com",
  "scope": "domain",
  "max_pages": 10000,
  "max_depth": 10,
  "crawl_javascript": true,
  "follow_links": true,
  "check_external_links": false,
  "include_screenshots": false,
  "custom_checks": [
    {
      "type": "http_status",
      "expected": 200
    },
    {
      "type": "title_tag",
      "required": true,
      "max_length": 60
    }
  ]
}
```

**Request Schema:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `project_id` | string | Yes | — | Target project |
| `url` | string | No | Project URL | Starting URL |
| `scope` | string | No | `domain` | `domain`, `subdomain`, `path`, `page` |
| `max_pages` | integer | No | Project setting | Max pages to crawl |
| `max_depth` | integer | No | 10 | Max link depth |
| `crawl_javascript` | boolean | No | true | Execute JavaScript |
| `follow_links` | boolean | No | true | Follow internal links |
| `check_external_links` | boolean | No | false | Validate external links |
| `include_screenshots` | boolean | No | false | Capture page screenshots |
| `custom_checks` | array | No | [] | Custom validation rules |
| `callback_url` | string | No | — | Webhook on completion |

**Response (202 Accepted):**

```json
{
  "data": {
    "run_id": "run_ghi789",
    "agent": "crawler",
    "project_id": "prj_5tYu2wErT8",
    "status": "started",
    "scope": "domain",
    "max_pages": 10000,
    "estimated_duration_seconds": 3600,
    "started_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 13.2 GET /api/v1/projects/{id}/pages

List crawled pages for a project.

**Auth:** Bearer token  
**Rate Limit:** 120/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max items |
| `cursor` | string | — | Pagination cursor |
| `fields` | string | all | Field selection |
| `sort` | string | `url:asc` | Sort field |
| `filter[status_code]` | integer | — | HTTP status code |
| `filter[has_issues]` | boolean | — | Pages with/without issues |
| `filter[content_type]` | string | — | `html`, `image`, `pdf`, etc. |
| `filter[depth]` | integer | — | Crawl depth |
| `filter[q]` | string | — | Search URL/title |

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "pg_abc123",
      "url": "https://www.acme.com/products/widget",
      "status_code": 200,
      "content_type": "text/html",
      "title": "Widget Pro | Acme Corp",
      "meta_description": "The best widget for enterprise teams.",
      "h1": "Widget Pro",
      "word_count": 1850,
      "crawl_depth": 2,
      "load_time_ms": 1200,
      "content_score": 82,
      "issues_count": 2,
      "internal_links": 15,
      "external_links": 3,
      "images": 8,
      "images_without_alt": 1,
      "canonical_url": "https://www.acme.com/products/widget",
      "robots": "index, follow",
      "last_crawled_at": "2026-07-18T06:15:00Z",
      "first_seen_at": "2025-03-15T10:00:00Z"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MjB9",
    "has_more": true,
    "total_count": 1247
  }
}
```

---

### 13.3 GET /api/v1/projects/{id}/pages/{page_id}

Get detailed page analysis.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Response (200 OK):**

```json
{
  "data": {
    "id": "pg_abc123",
    "url": "https://www.acme.com/products/widget",
    "project_id": "prj_5tYu2wErT8",
    "status_code": 200,
    "content_type": "text/html",
    "redirect_url": null,
    "title": {
      "value": "Widget Pro | Acme Corp",
      "length": 24,
      "score": 90
    },
    "meta_description": {
      "value": "The best widget for enterprise teams.",
      "length": 36,
      "score": 85
    },
    "headings": {
      "h1": ["Widget Pro"],
      "h2": ["Features", "Pricing", "Testimonials", "FAQ"],
      "h3": ["Real-time Analytics", "Team Collaboration", "Enterprise Security"]
    },
    "content": {
      "word_count": 1850,
      "readability_score": 72,
      "reading_level": "grade_8",
      "language": "en",
      "keyword_density": {
        "widget": 2.3,
        "enterprise": 1.8,
        "analytics": 1.5
      }
    },
    "links": {
      "internal": 15,
      "external": 3,
      "nofollow": 2,
      "broken": 0,
      "details": [
        {
          "url": "/pricing",
          "text": "View Pricing",
          "type": "internal",
          "follow": true,
          "status_code": 200
        }
      ]
    },
    "images": {
      "total": 8,
      "with_alt": 7,
      "without_alt": 1,
      "oversized": 2,
      "details": [
        {
          "src": "/images/widget-hero.jpg",
          "alt": "Widget Pro Dashboard",
          "width": 1920,
          "height": 1080,
          "size_kb": 450,
          "lazy_loaded": true
        }
      ]
    },
    "technical": {
      "canonical_url": "https://www.acme.com/products/widget",
      "robots": "index, follow",
      "open_graph": {
        "title": "Widget Pro | Acme Corp",
        "description": "The best widget for enterprise teams.",
        "image": "https://www.acme.com/images/og-widget.jpg",
        "type": "product"
      },
      "twitter_card": {
        "card": "summary_large_image",
        "title": "Widget Pro | Acme Corp"
      },
      "structured_data": [
        {
          "type": "Product",
          "valid": true,
          "warnings": 0,
          "errors": 0
        }
      ],
      "http_headers": {
        "x-robots-tag": null,
        "content-security-policy": "default-src 'self'",
        "strict-transport-security": "max-age=31536000"
      }
    },
    "performance": {
      "load_time_ms": 1200,
      "ttfb_ms": 180,
      "dom_content_loaded_ms": 800,
      "page_size_kb": 320,
      "requests": 24,
      "core_web_vitals": {
        "lcp": {"value": 2100, "rating": "good"},
        "fid": {"value": 45, "rating": "good"},
        "cls": {"value": 0.05, "rating": "good"},
        "inp": {"value": 120, "rating": "good"}
      }
    },
    "issues": [
      {
        "id": "iss_001",
        "severity": "medium",
        "category": "images",
        "title": "Image missing alt text",
        "description": "1 image is missing alt attribute",
        "affected_element": "/images/icon-arrow.svg",
        "recommendation": "Add descriptive alt text to all images"
      }
    ],
    "history": [
      {
        "crawled_at": "2026-07-18T06:15:00Z",
        "status_code": 200,
        "content_score": 82,
        "issues_count": 2
      },
      {
        "crawled_at": "2026-07-11T06:00:00Z",
        "status_code": 200,
        "content_score": 78,
        "issues_count": 4
      }
    ],
    "last_crawled_at": "2026-07-18T06:15:00Z",
    "first_seen_at": "2025-03-15T10:00:00Z"
  }
}
```

---

### 13.4 POST /api/v1/projects/{id}/pages/{page_id}/re-crawl

Re-crawl a specific page.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "crawl_javascript": true,
  "include_screenshot": true,
  "priority": "high"
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "run_id": "run_jkl012",
    "page_id": "pg_abc123",
    "url": "https://www.acme.com/products/widget",
    "status": "queued",
    "estimated_completion_seconds": 30,
    "queued_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 13.5 GET /api/v1/projects/{id}/issues

List SEO issues for a project.

**Auth:** Bearer token  
**Rate Limit:** 120/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max items |
| `cursor` | string | — | Pagination cursor |
| `filter[severity]` | string | — | `critical`, `high`, `medium`, `low` |
| `filter[category]` | string | — | `technical`, `content`, `performance`, `links`, `images` |
| `filter[status]` | string | — | `open`, `resolved`, `ignored` |
| `filter[page_id]` | string | — | Filter by page |
| `sort` | string | `severity:desc` | Sort field |

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "iss_abc123",
      "project_id": "prj_5tYu2wErT8",
      "page_id": "pg_xyz789",
      "page_url": "https://www.acme.com/about",
      "severity": "critical",
      "category": "technical",
      "title": "Missing title tag",
      "description": "The page has no <title> tag, which is essential for SEO.",
      "affected_element": "<head>",
      "recommendation": "Add a descriptive <title> tag between 30-60 characters.",
      "impact_score": 95,
      "status": "open",
      "first_detected_at": "2026-07-18T06:00:00Z",
      "last_seen_at": "2026-07-18T06:00:00Z",
      "auto_fixable": true,
      "fix_suggestion": "<title>About Acme Corp | Industry Leader in Widgets</title>"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MjB9",
    "has_more": true,
    "total_count": 47
  }
}
```

---

### 13.6 POST /api/v1/projects/{id}/issues/{id}/resolve

Resolve or dismiss an issue.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 60/min

**Request Body:**

```json
{
  "status": "resolved",
  "resolution_note": "Fixed by adding title tag to template.",
  "apply_auto_fix": false
}
```

**Request Schema:**

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | string | Yes | `resolved`, `ignored` |
| `resolution_note` | string | No | Note about the resolution |
| `apply_auto_fix` | boolean | No | Apply suggested auto-fix (if available) |

**Response (200 OK):**

```json
{
  "data": {
    "id": "iss_abc123",
    "status": "resolved",
    "resolution_note": "Fixed by adding title tag to template.",
    "resolved_by": "usr_2xKp9mLqR3",
    "resolved_at": "2026-07-19T12:00:00Z",
    "auto_fix_applied": false
  }
}
```

---

## 14. Content Agent

---

### 14.1 POST /api/v1/agents/content/audit

Audit content quality and SEO optimization.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "page_ids": ["pg_abc123", "pg_def456"],
  "target_keyword": "enterprise widget solution",
  "secondary_keywords": ["business widget", "widget software", "widget platform"],
  "analyze_competitors": true,
  "competitor_urls": [
    "https://competitor1.com/widgets",
    "https://competitor2.com/solutions"
  ],
  "checks": [
    "keyword_density",
    "readability",
    "content_gaps",
    "heading_structure",
    "meta_optimization",
    "internal_linking",
    "content_freshness"
  ]
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "audit_id": "aud_abc123",
    "status": "processing",
    "pages_queued": 2,
    "estimated_completion_seconds": 120,
    "started_at": "2026-07-19T12:00:00Z"
  }
}
```

**Completed Result (via GET /api/v1/agents/content/audit/{audit_id} or webhook):**

```json
{
  "data": {
    "audit_id": "aud_abc123",
    "status": "completed",
    "results": [
      {
        "page_id": "pg_abc123",
        "url": "https://www.acme.com/products/widget",
        "overall_score": 78,
        "target_keyword": "enterprise widget solution",
        "keyword_analysis": {
          "density": 1.8,
          "optimal_range": "1-3%",
          "in_title": true,
          "in_h1": true,
          "in_meta_description": true,
          "in_first_paragraph": true,
          "in_headings": 3,
          "in_alt_text": 1,
          "prominence_score": 85
        },
        "readability": {
          "score": 72,
          "reading_level": "Grade 8",
          "avg_sentence_length": 18,
          "flesch_kincaid": 65,
          "suggestions": ["Break up long paragraph in section 3"]
        },
        "content_gaps": [
          {
            "topic": "pricing comparison",
            "competitor_coverage": 3,
            "recommendation": "Add pricing comparison section"
          },
          {
            "topic": "integration capabilities",
            "competitor_coverage": 2,
            "recommendation": "Detail API and integration options"
          }
        ],
        "heading_structure": {
          "score": 88,
          "h1_count": 1,
          "h2_count": 5,
          "h3_count": 8,
          "issues": []
        },
        "meta_optimization": {
          "title_score": 90,
          "description_score": 85,
          "title_suggestion": "Enterprise Widget Solution | Acme Corp",
          "description_suggestion": "Discover Acme's enterprise widget solution. Real-time analytics, team collaboration, and enterprise security. Request a demo today."
        },
        "internal_linking": {
          "score": 75,
          "internal_links": 15,
          "suggested_links": [
            {
              "anchor": "widget pricing",
              "target_url": "/pricing",
              "context": "Consider linking from the pricing mention in paragraph 3"
            }
          ]
        }
      }
    ],
    "completed_at": "2026-07-19T12:02:00Z"
  }
}
```

---

### 14.2 POST /api/v1/agents/content/optimize-meta

Generate optimized meta titles and descriptions.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "page_id": "pg_abc123",
  "target_keyword": "enterprise widget solution",
  "brand_name": "Acme Corp",
  "tone": "professional",
  "generate_variants": 5,
  "include_cta": true
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "page_id": "pg_abc123",
    "target_keyword": "enterprise widget solution",
    "variants": [
      {
        "id": 1,
        "title": "Enterprise Widget Solution | Acme Corp",
        "title_length": 38,
        "description": "Discover Acme's enterprise widget solution with real-time analytics and team collaboration. Request a free demo today.",
        "description_length": 118,
        "score": 92,
        "keyword_in_title": true,
        "keyword_in_description": true,
        "has_cta": true
      },
      {
        "id": 2,
        "title": "Best Enterprise Widget Solution for Teams | Acme",
        "title_length": 48,
        "description": "Transform your workflow with Acme's enterprise widget solution. Built for teams of 10-10,000. Start your free trial.",
        "description_length": 115,
        "score": 88,
        "keyword_in_title": true,
        "keyword_in_description": true,
        "has_cta": true
      }
    ],
    "recommendation": 1
  }
}
```

---

### 14.3 POST /api/v1/agents/content/geo-check

Check content for Geo-SEO optimization (local/international).

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 20/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "page_id": "pg_abc123",
  "target_location": {
    "country": "US",
    "state": "CA",
    "city": "San Francisco"
  },
  "target_language": "en",
  "check_hreflang": true,
  "check_local_signals": true
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "page_id": "pg_abc123",
    "geo_score": 72,
    "target_location": {
      "country": "US",
      "state": "CA",
      "city": "San Francisco"
    },
    "hreflang": {
      "present": false,
      "recommendation": "Add hreflang tags for en-US, en-GB, de-DE",
      "suggested_tags": [
        "<link rel=\"alternate\" hreflang=\"en-US\" href=\"https://www.acme.com/products/widget\" />",
        "<link rel=\"alternate\" hreflang=\"en-GB\" href=\"https://www.acme.com/en-gb/products/widget\" />"
      ]
    },
    "local_signals": {
      "local_keywords_found": ["San Francisco", "Bay Area"],
      "local_schema_missing": true,
      "google_my_business_linked": false,
      "nap_consistency": "unknown",
      "recommendations": [
        "Add LocalBusiness schema markup",
        "Include local phone number and address",
        "Link to Google Business Profile"
      ]
    },
    "content_localization": {
      "currency": "USD",
      "date_format": "MM/DD/YYYY",
      "units": "imperial",
      "cultural_references": "appropriate"
    }
  }
}
```

---

### 14.4 POST /api/v1/agents/content/keyword-gap

Analyze keyword gaps vs. competitors.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "competitor_urls": [
    "https://competitor1.com",
    "https://competitor2.com"
  ],
  "country": "US",
  "language": "en",
  "min_search_volume": 100,
  "max_results": 50
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "project_id": "prj_5tYu2wErT8",
    "country": "US",
    "summary": {
      "total_gaps_found": 34,
      "high_opportunity": 8,
      "medium_opportunity": 15,
      "low_opportunity": 11,
      "estimated_traffic_gain": 12500
    },
    "keywords": [
      {
        "keyword": "widget automation tool",
        "search_volume": 2400,
        "keyword_difficulty": 45,
        "cpc": 8.50,
        "opportunity_score": 92,
        "your_position": null,
        "competitors": [
          {
            "domain": "competitor1.com",
            "position": 3,
            "url": "https://competitor1.com/automation"
          },
          {
            "domain": "competitor2.com",
            "position": 7,
            "url": "https://competitor2.com/tools"
          }
        ],
        "intent": "commercial",
        "suggested_content_type": "landing_page"
      }
    ]
  }
}
```

---

### 14.5 POST /api/v1/agents/content/generate-brief

Generate a content brief for a target keyword.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "target_keyword": "enterprise widget solution",
  "content_type": "blog_post",
  "target_audience": "IT managers and CTOs",
  "tone": "professional",
  "word_count_target": 2000,
  "include_competitor_analysis": true,
  "max_competitors": 5
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "brief_id": "brf_abc123",
    "target_keyword": "enterprise widget solution",
    "title_suggestions": [
      "The Complete Guide to Enterprise Widget Solutions in 2026",
      "How to Choose the Right Enterprise Widget Solution for Your Team"
    ],
    "meta_description": "Discover the best enterprise widget solutions. Compare features, pricing, and use cases to find the perfect fit for your organization.",
    "target_word_count": 2000,
    "target_reading_level": "Grade 10",
    "outline": [
      {
        "heading": "What is an Enterprise Widget Solution?",
        "type": "h2",
        "suggested_words": 300,
        "key_points": ["Definition", "Key characteristics", "Why enterprises need them"]
      },
      {
        "heading": "Key Features to Look For",
        "type": "h2",
        "suggested_words": 400,
        "key_points": ["Scalability", "Security", "Integration capabilities", "Analytics"]
      },
      {
        "heading": "Top Enterprise Widget Solutions Compared",
        "type": "h2",
        "suggested_words": 500,
        "key_points": ["Feature comparison table", "Pricing overview", "Pros and cons"]
      },
      {
        "heading": "How to Choose the Right Solution",
        "type": "h2",
        "suggested_words": 400,
        "key_points": ["Assess your needs", "Budget considerations", "Implementation timeline"]
      },
      {
        "heading": "Implementation Best Practices",
        "type": "h2",
        "suggested_words": 300,
        "key_points": ["Planning", "Team training", "Measuring success"]
      }
    ],
    "required_keywords": ["enterprise widget", "widget solution", "business widget software"],
    "secondary_keywords": ["widget platform", "widget tool", "widget analytics"],
    "questions_to_answer": [
      "What makes a widget solution enterprise-grade?",
      "How much does an enterprise widget solution cost?",
      "What integrations should an enterprise widget solution support?"
    ],
    "competitor_insights": [
      {
        "url": "https://competitor1.com/guide",
        "word_count": 2500,
        "top_headings": ["Features", "Pricing", "Comparison"],
        "content_gaps": ["Implementation timeline", "ROI calculator"]
      }
    ],
    "internal_links_to_include": [
      {"anchor": "widget features", "url": "/features"},
      {"anchor": "pricing plans", "url": "/pricing"}
    ],
    "external_sources_suggested": [
      "Gartner Market Guide for Widget Solutions",
      "Forrester Wave: Widget Platforms Q1 2026"
    ]
  }
}
```

---

### 14.6 POST /api/v1/agents/content/generate-draft

Generate a content draft based on a brief.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "brief_id": "brf_abc123",
  "target_keyword": "enterprise widget solution",
  "content_type": "blog_post",
  "word_count_target": 2000,
  "tone": "professional",
  "include_images": true,
  "include_schema": true,
  "custom_instructions": "Include a comparison table. End with a CTA for demo."
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "draft_id": "dft_abc123",
    "status": "completed",
    "title": "The Complete Guide to Enterprise Widget Solutions in 2026",
    "meta_title": "Enterprise Widget Solutions Guide 2026 | Acme Corp",
    "meta_description": "Discover the best enterprise widget solutions. Compare features, pricing, and use cases. Expert guide by Acme Corp.",
    "word_count": 2150,
    "reading_level": "Grade 9",
    "content_score": 85,
    "html_content": "<article>...</article>",
    "markdown_content": "# The Complete Guide...",
    "structured_data": {
      "@type": "Article",
      "headline": "The Complete Guide to Enterprise Widget Solutions in 2026",
      "author": "Acme Corp",
      "datePublished": "2026-07-19"
    },
    "seo_checklist": {
      "keyword_in_title": true,
      "keyword_in_first_paragraph": true,
      "keyword_in_h2": true,
      "keyword_density_ok": true,
      "meta_description_optimized": true,
      "internal_links_added": 3,
      "external_links_added": 2,
      "images_suggested": 4,
      "readability_ok": true
    },
    "suggested_images": [
      {
        "position": "after_h2_1",
        "description": "Infographic showing key features of enterprise widget solutions",
        "alt_text": "Enterprise widget solution features infographic"
      }
    ],
    "ai_detection_score": 12,
    "uniqueness_score": 95
  }
}
```

---

## 15. Technical Agent

---

### 15.1 POST /api/v1/agents/technical/audit

Run a comprehensive technical SEO audit.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "scope": "full",
  "checks": [
    "core_web_vitals",
    "mobile_usability",
    "crawlability",
    "indexability",
    "structured_data",
    "security",
    "internationalization",
    "javascript_rendering",
    "page_experience"
  ],
  "urls": [],
  "compare_engines": ["google", "bing"]
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "audit_id": "taud_abc123",
    "project_id": "prj_5tYu2wErT8",
    "status": "completed",
    "overall_score": 92,
    "overall_grade": "A",
    "summary": {
      "total_checks": 156,
      "passed": 142,
      "warnings": 10,
      "errors": 4,
      "critical": 0
    },
    "categories": {
      "core_web_vitals": {
        "score": 95,
        "status": "pass",
        "findings": [
          {
            "metric": "LCP",
            "value": "2.1s",
            "threshold": "2.5s",
            "status": "good",
            "affected_pages": 5
          },
          {
            "metric": "CLS",
            "value": "0.08",
            "threshold": "0.1",
            "status": "good",
            "affected_pages": 12
          }
        ]
      },
      "mobile_usability": {
        "score": 98,
        "status": "pass",
        "findings": []
      },
      "crawlability": {
        "score": 88,
        "status": "warning",
        "findings": [
          {
            "type": "orphan_pages",
            "severity": "medium",
            "count": 15,
            "description": "15 pages are not linked from any other page",
            "affected_urls": ["https://www.acme.com/old-page-1", "..."]
          }
        ]
      },
      "structured_data": {
        "score": 78,
        "status": "warning",
        "findings": [
          {
            "type": "missing_schema",
            "severity": "medium",
            "count": 23,
            "schema_type": "Product",
            "description": "23 product pages missing Product schema"
          }
        ]
      }
    },
    "recommendations": [
      {
        "priority": 1,
        "category": "structured_data",
        "action": "Add Product schema to all product pages",
        "impact": "high",
        "effort": "medium",
        "affected_pages": 23
      }
    ],
    "completed_at": "2026-07-19T12:10:00Z"
  }
}
```

---

### 15.2 POST /api/v1/agents/technical/schema

Generate or validate structured data schema.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "page_id": "pg_abc123",
  "schema_types": ["Product", "FAQ", "BreadcrumbList"],
  "validate_existing": true,
  "generate_missing": true,
  "context": {
    "product_name": "Widget Pro",
    "product_price": 99.99,
    "product_currency": "USD",
    "product_rating": 4.5,
    "product_review_count": 128
  }
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "page_id": "pg_abc123",
    "existing_schemas": [
      {
        "type": "Organization",
        "valid": true,
        "warnings": 0,
        "errors": 0,
        "markup": {"@type": "Organization", "...": "..."}
      }
    ],
    "generated_schemas": [
      {
        "type": "Product",
        "valid": true,
        "warnings": 0,
        "errors": 0,
        "markup": {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Widget Pro",
          "description": "Enterprise widget solution",
          "offers": {
            "@type": "Offer",
            "price": "99.99",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          },
          "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.5",
            "reviewCount": "128"
          }
        },
        "implementation": "<script type=\"application/ld+json\">\n{...}\n</script>"
      },
      {
        "type": "BreadcrumbList",
        "valid": true,
        "markup": {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.acme.com"},
            {"@type": "ListItem", "position": 2, "name": "Products", "item": "https://www.acme.com/products"},
            {"@type": "ListItem", "position": 3, "name": "Widget Pro"}
          ]
        }
      }
    ],
    "rich_results_eligible": ["Product", "BreadcrumbList"],
    "google_test_url": "https://search.google.com/test/rich-results?url=https://www.acme.com/products/widget"
  }
}
```

---

### 15.3 POST /api/v1/agents/technical/self-heal

Auto-fix detected technical issues.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "issue_ids": ["iss_001", "iss_002", "iss_003"],
  "auto_fix_all": false,
  "dry_run": true,
  "integration_id": "int_wordpress_001"
}
```

**Request Schema:**

| Field | Type | Required | Description |
|---|---|---|---|
| `project_id` | string | Yes | Target project |
| `issue_ids` | array | No | Specific issues to fix |
| `auto_fix_all` | boolean | No | Fix all auto-fixable issues |
| `dry_run` | boolean | No | Preview changes without applying (default: true) |
| `integration_id` | string | No | CMS integration for applying fixes |

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "heal_id": "heal_abc123",
    "dry_run": true,
    "project_id": "prj_5tYu2wErT8",
    "total_issues": 3,
    "fixable": 2,
    "not_fixable": 1,
    "not_fixable_reasons": [
      {
        "issue_id": "iss_003",
        "reason": "Requires manual code changes in custom template"
      }
    ],
    "proposed_fixes": [
      {
        "issue_id": "iss_001",
        "page_url": "https://www.acme.com/about",
        "fix_type": "add_title_tag",
        "current_value": null,
        "proposed_value": "<title>About Acme Corp | Industry Leader in Widgets</title>",
        "confidence": 0.95,
        "impact": "high"
      },
      {
        "issue_id": "iss_002",
        "page_url": "https://www.acme.com/team",
        "fix_type": "add_meta_description",
        "current_value": null,
        "proposed_value": "<meta name=\"description\" content=\"Meet the Acme Corp team. Over 50 years of innovation in widget technology.\">",
        "confidence": 0.90,
        "impact": "medium"
      }
    ],
    "apply_command": "POST /api/v1/agents/technical/self-heal with dry_run=false"
  }
}
```

---

### 15.4 POST /api/v1/agents/technical/multi-engine

Optimize for multiple search engines (Google, Bing, Yandex, Naver).

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "engines": ["google", "bing", "yandex"],
  "page_ids": ["pg_abc123"],
  "checks": [
    "ranking_factors",
    "schema_support",
    "webmaster_guidelines",
    "crawl_preferences"
  ]
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "analysis_id": "mea_abc123",
    "project_id": "prj_5tYu2wErT8",
    "engines_analyzed": ["google", "bing", "yandex"],
    "results": {
      "google": {
        "score": 92,
        "indexed_pages": 1180,
        "issues": 5,
        "recommendations": ["Improve Core Web Vitals on 3 pages"]
      },
      "bing": {
        "score": 85,
        "indexed_pages": 1050,
        "issues": 12,
        "recommendations": [
          "Submit sitemap to Bing Webmaster Tools",
          "Add Bing-specific meta tags"
        ]
      },
      "yandex": {
        "score": 68,
        "indexed_pages": 420,
        "issues": 25,
        "recommendations": [
          "Register in Yandex Webmaster",
          "Add Yandex.Turbo pages",
          "Implement Yandex-specific structured data"
        ]
      }
    },
    "cross_engine_insights": [
      {
        "insight": "Bing gives more weight to social signals",
        "action": "Increase social sharing buttons and Open Graph tags"
      },
      {
        "insight": "Yandex requires explicit region targeting",
        "action": "Add region meta tag for yandex:region"
      }
    ],
    "completed_at": "2026-07-19T12:15:00Z"
  }
}
```

---

### 15.5 GET /api/v1/projects/{id}/technical-score

Get current technical SEO score.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Response (200 OK):**

```json
{
  "data": {
    "project_id": "prj_5tYu2wErT8",
    "overall_score": 92,
    "grade": "A",
    "last_audit_at": "2026-07-18T06:00:00Z",
    "categories": {
      "core_web_vitals": {"score": 95, "status": "good"},
      "mobile_usability": {"score": 98, "status": "good"},
      "crawlability": {"score": 88, "status": "needs_improvement"},
      "indexability": {"score": 94, "status": "good"},
      "structured_data": {"score": 78, "status": "needs_improvement"},
      "security": {"score": 100, "status": "good"},
      "internationalization": {"score": 65, "status": "needs_improvement"},
      "javascript_rendering": {"score": 90, "status": "good"},
      "page_experience": {"score": 91, "status": "good"}
    },
    "trend": [
      {"date": "2026-06-19", "score": 85},
      {"date": "2026-06-26", "score": 87},
      {"date": "2026-07-03", "score": 89},
      {"date": "2026-07-10", "score": 90},
      {"date": "2026-07-17", "score": 92}
    ],
    "open_critical_issues": 0,
    "open_high_issues": 3
  }
}
```

---

## 16. Rank Agent

---

### 16.1 POST /api/v1/agents/rank/track

Add keywords to tracking or trigger a rank check.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "keywords": [
    {
      "keyword": "enterprise widget solution",
      "country": "US",
      "language": "en",
      "device": "desktop",
      "location": "New York"
    },
    {
      "keyword": "best widget software",
      "country": "US",
      "language": "en",
      "device": "mobile"
    }
  ],
  "track_competitors": true,
  "frequency": "daily"
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "tracking_id": "trk_abc123",
    "project_id": "prj_5tYu2wErT8",
    "keywords_queued": 2,
    "estimated_completion_seconds": 60,
    "status": "processing"
  }
}
```

---

### 16.2 GET /api/v1/projects/{id}/keywords

List tracked keywords with current rankings.

**Auth:** Bearer token  
**Rate Limit:** 120/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max items |
| `cursor` | string | — | Pagination cursor |
| `fields` | string | all | Field selection |
| `sort` | string | `position:asc` | Sort field |
| `filter[position_range]` | string | — | e.g., `1-10`, `11-20`, `21-50` |
| `filter[country]` | string | — | Filter by country |
| `filter[device]` | string | — | `desktop`, `mobile` |
| `filter[trend]` | string | — | `improved`, `declined`, `stable`, `new` |
| `filter[q]` | string | — | Search keyword |
| `filter[group_id]` | string | — | Filter by keyword group |

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "kw_abc123",
      "keyword": "enterprise widget solution",
      "country": "US",
      "language": "en",
      "device": "desktop",
      "location": "New York",
      "current_position": 4,
      "previous_position": 7,
      "position_change": 3,
      "trend": "improved",
      "best_position": 3,
      "worst_position": 12,
      "search_volume": 2400,
      "keyword_difficulty": 45,
      "cpc": 8.50,
      "serp_features": ["featured_snippet", "people_also_ask"],
      "landing_page": "https://www.acme.com/products/widget",
      "competitor_positions": [
        {
          "domain": "competitor1.com",
          "position": 2,
          "url": "https://competitor1.com/widgets"
        }
      ],
      "first_tracked_at": "2025-06-01T00:00:00Z",
      "last_checked_at": "2026-07-19T06:00:00Z"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MjB9",
    "has_more": true,
    "total_count": 350
  }
}
```

---

### 16.3 GET /api/v1/projects/{id}/keywords/{keyword_id}/history

Get keyword ranking history.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `period` | string | `90d` | `30d`, `90d`, `6m`, `1y`, `all` |
| `granularity` | string | `daily` | `daily`, `weekly`, `monthly` |

**Response (200 OK):**

```json
{
  "data": {
    "keyword_id": "kw_abc123",
    "keyword": "enterprise widget solution",
    "country": "US",
    "device": "desktop",
    "history": [
      {
        "date": "2026-07-19",
        "position": 4,
        "url": "https://www.acme.com/products/widget",
        "serp_features": ["featured_snippet"]
      },
      {
        "date": "2026-07-18",
        "position": 4,
        "url": "https://www.acme.com/products/widget",
        "serp_features": ["featured_snippet"]
      },
      {
        "date": "2026-07-17",
        "position": 5,
        "url": "https://www.acme.com/products/widget",
        "serp_features": []
      },
      {
        "date": "2026-07-10",
        "position": 7,
        "url": "https://www.acme.com/products/widget",
        "serp_features": []
      }
    ],
    "statistics": {
      "avg_position": 5.2,
      "best_position": 3,
      "worst_position": 12,
      "days_tracked": 90,
      "days_improved": 32,
      "days_declined": 15,
      "days_stable": 43
    }
  }
}
```

---

### 16.4 GET /api/v1/projects/{id}/serp-features

Get SERP feature presence for tracked keywords.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `feature_type` | string | — | Filter: `featured_snippet`, `people_also_ask`, `local_pack`, `knowledge_panel`, `image_pack`, `video_carousel`, `top_stories`, `shopping_results` |
| `period` | string | `30d` | Time period |

**Response (200 OK):**

```json
{
  "data": {
    "project_id": "prj_5tYu2wErT8",
    "period": "30d",
    "summary": {
      "total_keywords": 350,
      "keywords_with_features": 78,
      "feature_coverage_pct": 22.3
    },
    "features": [
      {
        "type": "featured_snippet",
        "count": 12,
        "keywords": [
          {
            "keyword": "what is a widget solution",
            "position": 0,
            "snippet_type": "paragraph",
            "url": "https://www.acme.com/blog/what-is-widget"
          }
        ]
      },
      {
        "type": "people_also_ask",
        "count": 45,
        "keywords": [
          {
            "keyword": "enterprise widget solution",
            "questions": [
              "What is the best widget solution for enterprise?",
              "How much does a widget solution cost?",
              "What features should a widget solution have?"
            ]
          }
        ]
      },
      {
        "type": "local_pack",
        "count": 8,
        "keywords": []
      }
    ],
    "opportunities": [
      {
        "keyword": "widget solution comparison",
        "feature_type": "featured_snippet",
        "current_position": 6,
        "competitor_owns_snippet": "competitor1.com",
        "recommendation": "Restructure content with comparison table to capture snippet"
      }
    ]
  }
}
```

---

### 16.5 POST /api/v1/projects/{id}/keywords/import

Bulk import keywords for tracking.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "keywords": [
    "enterprise widget solution",
    "best widget software",
    "widget automation tool",
    "business widget platform"
  ],
  "defaults": {
    "country": "US",
    "language": "en",
    "device": "desktop",
    "frequency": "daily"
  },
  "groups": ["primary", "competitors"],
  "source": "manual"
}
```

**Request Schema:**

| Field | Type | Required | Description |
|---|---|---|---|
| `keywords` | array | Yes | List of keywords (max 1000) |
| `defaults` | object | No | Default settings for all keywords |
| `groups` | array | No | Keyword group names to assign |
| `source` | string | No | `manual`, `csv`, `gsc`, `suggestion` |

**Response (202 Accepted):**

```json
{
  "data": {
    "import_id": "imp_abc123",
    "project_id": "prj_5tYu2wErT8",
    "total_keywords": 4,
    "new_keywords": 3,
    "duplicate_keywords": 1,
    "invalid_keywords": 0,
    "status": "processing",
    "estimated_completion_seconds": 120
  }
}
```

---

## 17. Backlink & Outreach Agent

---

### 17.1 POST /api/v1/agents/backlink/haro/parse

Parse HARO (Help A Reporter Out) emails for link opportunities.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 20/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "email_source": "inbox",
  "date_range": {
    "from": "2026-07-15",
    "to": "2026-07-19"
  },
  "categories": ["business", "technology", "finance"],
  "min_domain_authority": 30,
  "auto_pitch": false,
  "expertise_topics": ["enterprise software", "SaaS", "widgets"]
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "parse_id": "haro_abc123",
    "project_id": "prj_5tYu2wErT8",
    "emails_parsed": 12,
    "opportunities_found": 8,
    "opportunities": [
      {
        "id": "opp_001",
        "source": "HARO",
        "journalist": {
          "name": "Sarah Johnson",
          "outlet": "TechCrunch",
          "domain_authority": 93,
          "email": "sarah@techcrunch.com"
        },
        "query": "Looking for enterprise software experts to comment on the future of automation",
        "deadline": "2026-07-20T17:00:00Z",
        "category": "technology",
        "relevance_score": 92,
        "keywords": ["enterprise software", "automation"],
        "status": "new"
      }
    ]
  }
}
```

---

### 17.2 POST /api/v1/agents/backlink/broken/scan

Scan for broken link building opportunities.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "target_domains": [
    "industry-blog.com",
    "tech-resource.com"
  ],
  "niche_keywords": ["widget", "enterprise software", "automation"],
  "min_domain_authority": 30,
  "max_results": 50,
  "check_content_match": true
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "scan_id": "brk_abc123",
    "project_id": "prj_5tYu2wErT8",
    "domains_scanned": 2,
    "broken_links_found": 23,
    "opportunities": [
      {
        "id": "blo_001",
        "broken_url": "https://industry-blog.com/old-widget-guide",
        "status_code": 404,
        "referring_page": "https://industry-blog.com/resources",
        "referring_page_da": 55,
        "link_anchor": "Widget Guide",
        "your_matching_content": "https://www.acme.com/blog/complete-widget-guide",
        "content_match_score": 88,
        "outreach_priority": "high"
      }
    ]
  }
}
```

---

### 17.3 POST /api/v1/agents/backlink/broken/outreach

Send outreach emails for broken link building.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "opportunity_ids": ["blo_001", "blo_002"],
  "template_id": "tpl_broken_outreach",
  "personalize": true,
  "from_name": "Jane Doe",
  "from_email": "jane@acme.com",
  "send_schedule": "immediate",
  "follow_up_days": [3, 7]
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "campaign_id": "cmp_broken_001",
    "project_id": "prj_5tYu2wErT8",
    "emails_queued": 2,
    "status": "sending",
    "sent_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 17.4 POST /api/v1/agents/backlink/guest-prospect

Find guest posting opportunities.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "niche": "enterprise software",
  "keywords": ["widget", "automation", "SaaS"],
  "min_domain_authority": 40,
  "max_results": 30,
  "exclude_already_contacted": true,
  "language": "en"
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "prospect_id": "gpr_abc123",
    "project_id": "prj_5tYu2wErT8",
    "prospects_found": 24,
    "prospects": [
      {
        "id": "prsp_001",
        "domain": "techblog.com",
        "domain_authority": 62,
        "monthly_traffic": 450000,
        "accepts_guest_posts": true,
        "guidelines_url": "https://techblog.com/write-for-us",
        "contact_email": "editor@techblog.com",
        "topics": ["technology", "software", "automation"],
        "avg_response_time_days": 3,
        "estimated_placement_value": 85,
        "status": "new"
      }
    ]
  }
}
```

---

### 17.5 POST /api/v1/agents/backlink/guest-pitch

Generate and send guest post pitches.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "prospect_ids": ["prsp_001", "prsp_002"],
  "author_name": "Jane Doe",
  "author_bio": "Jane is the VP of Product at Acme Corp with 15 years of experience in enterprise software.",
  "proposed_topics": [
    "The Future of Enterprise Automation: Trends for 2026",
    "How to Choose the Right Widget Solution for Your Business"
  ],
  "template_id": "tpl_guest_pitch",
  "personalize": true,
  "send_schedule": "immediate"
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "pitch_batch_id": "pitch_abc123",
    "pitches_sent": 2,
    "pitches_queued": 0,
    "status": "sent",
    "sent_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 17.6 POST /api/v1/agents/backlink/unlinked/scan

Find unlinked brand mentions.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "brand_names": ["Acme Corp", "Acme", "Acme Widget"],
  "min_domain_authority": 20,
  "date_range": {
    "from": "2026-01-01",
    "to": "2026-07-19"
  },
  "max_results": 50
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "scan_id": "unl_abc123",
    "project_id": "prj_5tYu2wErT8",
    "mentions_found": 18,
    "unlinked_mentions": 12,
    "opportunities": [
      {
        "id": "unlk_001",
        "page_url": "https://news-site.com/article-about-widgets",
        "page_title": "Top Widget Companies in 2026",
        "domain_authority": 72,
        "mention_text": "Acme Corp recently launched their new enterprise solution",
        "mention_context": "...companies like Acme Corp recently launched their new enterprise solution, which promises to revolutionize...",
        "suggested_link_url": "https://www.acme.com/products/widget",
        "suggested_anchor": "Acme Corp",
        "outreach_priority": "high",
        "contact_email": "editor@news-site.com"
      }
    ]
  }
}
```

---

### 17.7 POST /api/v1/agents/backlink/unlinked/request

Send link request emails for unlinked mentions.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "opportunity_ids": ["unlk_001", "unlk_002"],
  "template_id": "tpl_unlinked_request",
  "from_name": "Jane Doe",
  "from_email": "jane@acme.com",
  "personalize": true,
  "send_schedule": "immediate"
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "request_batch_id": "req_abc123",
    "emails_sent": 2,
    "status": "sent"
  }
}
```

---

### 17.8 POST /api/v1/agents/backlink/monitor

Monitor existing backlinks.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "project_id": "prj_5tYu2wErT8",
  "monitor_type": "full",
  "check_status": true,
  "check_anchor_text": true,
  "check_nofollow": true,
  "alert_on_loss": true,
  "alert_on_new": true,
  "competitor_domains": ["competitor1.com", "competitor2.com"]
}
```

**Response (202 Accepted) → Completed Result:**

```json
{
  "data": {
    "monitor_id": "mon_abc123",
    "project_id": "prj_5tYu2wErT8",
    "status": "completed",
    "summary": {
      "total_backlinks": 3420,
      "active": 3280,
      "lost": 45,
      "new": 67,
      "nofollow": 420,
      "dofollow": 2860,
      "toxic": 12,
      "referring_domains": 890
    },
    "lost_backlinks": [
      {
        "source_url": "https://old-blog.com/article",
        "target_url": "https://www.acme.com/products",
        "anchor_text": "Acme widgets",
        "domain_authority": 45,
        "first_seen": "2025-06-15T00:00:00Z",
        "last_seen": "2026-07-10T00:00:00Z",
        "reason": "page_removed"
      }
    ],
    "new_backlinks": [
      {
        "source_url": "https://new-site.com/review",
        "target_url": "https://www.acme.com/products/widget",
        "anchor_text": "Widget Pro by Acme",
        "domain_authority": 58,
        "first_seen": "2026-07-18T00:00:00Z",
        "dofollow": true
      }
    ],
    "toxic_backlinks": [
      {
        "source_url": "https://spam-site.com/links",
        "target_url": "https://www.acme.com",
        "toxic_score": 92,
        "toxic_reasons": ["spam_domain", "irrelevant_content", "link_farm"],
        "action_recommended": "disavow"
      }
    ],
    "competitor_comparison": {
      "your_domain_authority": 62,
      "competitors": [
        {"domain": "competitor1.com", "da": 68, "backlinks": 5200},
        {"domain": "competitor2.com", "da": 55, "backlinks": 2800}
      ]
    }
  }
}
```

---

## 18. Campaigns

---

### 18.1 GET /api/v1/campaigns

List outreach campaigns.

**Auth:** Bearer token  
**Rate Limit:** 120/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max items |
| `cursor` | string | — | Pagination cursor |
| `filter[status]` | string | — | `draft`, `active`, `paused`, `completed` |
| `filter[type]` | string | — | `broken_link`, `guest_post`, `unlinked_mention`, `haro` |
| `sort` | string | `created_at:desc` | Sort |

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "cmp_abc123",
      "name": "Q3 Broken Link Campaign",
      "type": "broken_link",
      "project_id": "prj_5tYu2wErT8",
      "status": "active",
      "stats": {
        "total_prospects": 50,
        "emails_sent": 45,
        "emails_opened": 28,
        "emails_replied": 12,
        "links_acquired": 5,
        "open_rate": 62.2,
        "reply_rate": 26.7,
        "conversion_rate": 11.1
      },
      "created_at": "2026-07-01T10:00:00Z",
      "updated_at": "2026-07-18T14:00:00Z"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MjB9",
    "has_more": false,
    "total_count": 5
  }
}
```

---

### 18.2 POST /api/v1/campaigns

Create a new outreach campaign.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "name": "Q3 Broken Link Campaign",
  "type": "broken_link",
  "project_id": "prj_5tYu2wErT8",
  "description": "Outreach for broken link building opportunities",
  "template_id": "tpl_broken_outreach",
  "from_name": "Jane Doe",
  "from_email": "jane@acme.com",
  "reply_to": "jane@acme.com",
  "schedule": {
    "send_window_start": "09:00",
    "send_window_end": "17:00",
    "timezone": "America/New_York",
    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "throttle_per_day": 10
  },
  "follow_up": {
    "enabled": true,
    "max_follow_ups": 2,
    "follow_up_days": [3, 7],
    "stop_on_reply": true,
    "stop_on_link": true
  },
  "tags": ["q3", "broken-link", "priority"]
}
```

**Response (201 Created):**

```json
{
  "data": {
    "id": "cmp_abc123",
    "name": "Q3 Broken Link Campaign",
    "type": "broken_link",
    "project_id": "prj_5tYu2wErT8",
    "status": "draft",
    "schedule": {
      "send_window_start": "09:00",
      "send_window_end": "17:00",
      "timezone": "America/New_York",
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
      "throttle_per_day": 10
    },
    "follow_up": {
      "enabled": true,
      "max_follow_ups": 2,
      "follow_up_days": [3, 7],
      "stop_on_reply": true,
      "stop_on_link": true
    },
    "tags": ["q3", "broken-link", "priority"],
    "created_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 18.3 GET /api/v1/campaigns/{id}

Get campaign details.

**Auth:** Bearer token  
**Rate Limit:** 120/min

**Response (200 OK):** Full campaign object with stats and settings.

---

### 18.4 PATCH /api/v1/campaigns/{id}

Update campaign settings.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 30/min

**Request Body:** Partial update.

```json
{
  "name": "Updated Campaign Name",
  "schedule": {
    "throttle_per_day": 15
  }
}
```

**Response (200 OK):** Updated campaign object.

---

### 18.5 PATCH /api/v1/campaigns/{id}/status

Change campaign status.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "status": "active",
  "reason": "Starting Q3 outreach"
}
```

**Response (200 OK):**

```json
{
  "data": {
    "id": "cmp_abc123",
    "status": "active",
    "previous_status": "draft",
    "changed_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 18.6 GET /api/v1/campaigns/stats

Get aggregated campaign statistics.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `period` | string | `30d` | Time period |
| `project_id` | string | — | Filter by project |
| `type` | string | — | Filter by campaign type |

**Response (200 OK):**

```json
{
  "data": {
    "period": "30d",
    "campaigns": {
      "total": 5,
      "active": 3,
      "completed": 1,
      "paused": 1
    },
    "outreach": {
      "total_prospects": 250,
      "emails_sent": 180,
      "emails_opened": 108,
      "emails_replied": 36,
      "links_acquired": 15,
      "open_rate": 60.0,
      "reply_rate": 20.0,
      "conversion_rate": 8.3
    },
    "by_type": {
      "broken_link": {
        "campaigns": 2,
        "links_acquired": 8,
        "conversion_rate": 10.5
      },
      "guest_post": {
        "campaigns": 2,
        "posts_published": 5,
        "conversion_rate": 6.2
      },
      "unlinked_mention": {
        "campaigns": 1,
        "links_acquired": 2,
        "conversion_rate": 15.4
      }
    },
    "top_campaigns": [
      {
        "id": "cmp_abc123",
        "name": "Q3 Broken Link Campaign",
        "links_acquired": 5,
        "conversion_rate": 11.1
      }
    ]
  }
}
```

---

### 18.7 GET /api/v1/campaigns/{id}/messages

List campaign messages/emails.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max items |
| `cursor` | string | — | Pagination cursor |
| `filter[status]` | string | — | `draft`, `scheduled`, `sent`, `opened`, `replied`, `bounced` |
| `sort` | string | `created_at:desc` | Sort |

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "msg_abc123",
      "campaign_id": "cmp_abc123",
      "prospect": {
        "name": "John Smith",
        "email": "john@industry-blog.com",
        "domain": "industry-blog.com",
        "domain_authority": 55
      },
      "subject": "Broken link on your resources page",
      "preview": "Hi John, I noticed a broken link on your resources page...",
      "status": "opened",
      "sent_at": "2026-07-15T09:30:00Z",
      "opened_at": "2026-07-15T11:45:00Z",
      "replied_at": null,
      "link_acquired": false,
      "follow_up_number": 0
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MjB9",
    "has_more": true,
    "total_count": 45
  }
}
```

---

### 18.8 POST /api/v1/campaigns/{id}/messages/send

Manually send a message in a campaign.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 30/min

**Request Body:**

```json
{
  "prospect_email": "john@industry-blog.com",
  "prospect_name": "John Smith",
  "subject": "Broken link on your resources page",
  "body": "Hi John,\n\nI noticed a broken link on your resources page pointing to...",
  "send_at": "2026-07-19T14:00:00Z"
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "id": "msg_def456",
    "campaign_id": "cmp_abc123",
    "status": "scheduled",
    "scheduled_at": "2026-07-19T14:00:00Z"
  }
}
```

---

### 18.9 POST /api/v1/campaigns/{id}/follow-up

Send follow-up for unreplied messages.

**Auth:** Bearer token (`manager`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "filter": {
    "status": "sent",
    "min_days_since_sent": 3,
    "max_days_since_sent": 7,
    "exclude_replied": true
  },
  "template_id": "tpl_followup_1",
  "subject": "Re: {{original_subject}}",
  "body": "Hi {{name}},\n\nJust following up on my previous email...",
  "send_schedule": "immediate"
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "follow_up_batch_id": "fu_abc123",
    "messages_queued": 15,
    "status": "processing"
  }
}
```

---

## 19. Integrations

---

### 19.1 GET /api/v1/integrations

List connected integrations.

**Auth:** Bearer token  
**Rate Limit:** 120/min

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "int_gsc_001",
      "type": "google_search_console",
      "name": "Google Search Console",
      "status": "connected",
      "connected_at": "2025-06-01T10:00:00Z",
      "last_sync_at": "2026-07-19T06:00:00Z",
      "properties": ["acme.com", "www.acme.com"],
      "config": {
        "auto_sync": true,
        "sync_frequency": "daily",
        "data_range_days": 90
      },
      "health": {
        "status": "healthy",
        "last_error": null,
        "api_quota_used_pct": 15.2
      }
    },
    {
      "id": "int_ga4_001",
      "type": "google_analytics_4",
      "name": "Google Analytics 4",
      "status": "connected",
      "connected_at": "2025-06-01T10:00:00Z",
      "properties": ["GA-12345678"],
      "health": {
        "status": "healthy"
      }
    },
    {
      "id": "int_wp_001",
      "type": "wordpress",
      "name": "WordPress (acme.com)",
      "status": "connected",
      "connected_at": "2025-08-15T14:00:00Z",
      "health": {
        "status": "degraded",
        "last_error": "Rate limited by WordPress API",
        "last_error_at": "2026-07-18T14:00:00Z"
      }
    }
  ]
}
```

---

### 19.2 POST /api/v1/integrations/gsc/connect

Connect Google Search Console.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "oauth_code": "4/0AY0e-g7...",
  "redirect_uri": "https://app.seoplatform.com/integrations/gsc/callback",
  "properties": ["acme.com", "www.acme.com"],
  "config": {
    "auto_sync": true,
    "sync_frequency": "daily",
    "data_range_days": 90
  }
}
```

**Response (201 Created):**

```json
{
  "data": {
    "id": "int_gsc_001",
    "type": "google_search_console",
    "status": "connected",
    "properties": ["acme.com", "www.acme.com"],
    "connected_at": "2026-07-19T12:00:00Z",
    "first_sync_scheduled_at": "2026-07-19T12:05:00Z"
  }
}
```

---

### 19.3 POST /api/v1/integrations/bing/connect

Connect Bing Webmaster Tools.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "api_key": "your_bing_webmaster_api_key",
  "site_url": "https://www.acme.com",
  "config": {
    "auto_sync": true,
    "sync_frequency": "daily"
  }
}
```

**Response (201 Created):** Integration object.

---

### 19.4 POST /api/v1/integrations/yandex/connect

Connect Yandex Webmaster.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "oauth_token": "yandex_oauth_token_here",
  "site_id": "12345678",
  "config": {
    "auto_sync": true,
    "sync_frequency": "daily"
  }
}
```

**Response (201 Created):** Integration object.

---

### 19.5 POST /api/v1/integrations/naver/connect

Connect Naver Webmaster Tools.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "api_key": "naver_api_key",
  "site_url": "https://www.acme.co.kr",
  "config": {
    "auto_sync": true,
    "sync_frequency": "daily"
  }
}
```

**Response (201 Created):** Integration object.

---

### 19.6 POST /api/v1/integrations/ga4/connect

Connect Google Analytics 4.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "oauth_code": "4/0AY0e-g7...",
  "redirect_uri": "https://app.seoplatform.com/integrations/ga4/callback",
  "property_id": "properties/123456789",
  "config": {
    "auto_sync": true,
    "sync_frequency": "daily",
    "import_goals": true
  }
}
```

**Response (201 Created):** Integration object.

---

### 19.7 POST /api/v1/integrations/gmail/connect

Connect Gmail for outreach.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "oauth_code": "4/0AY0e-g7...",
  "redirect_uri": "https://app.seoplatform.com/integrations/gmail/callback",
  "email": "jane@acme.com",
  "config": {
    "send_as_name": "Jane Doe",
    "signature": "Best regards,\nJane Doe\nVP of Product, Acme Corp",
    "daily_send_limit": 50,
    "track_opens": true,
    "track_clicks": true
  }
}
```

**Response (201 Created):** Integration object.

---

### 19.8 POST /api/v1/integrations/wordpress/connect

Connect WordPress site.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 5/min

**Request Body:**

```json
{
  "site_url": "https://www.acme.com",
  "auth_method": "application_password",
  "username": "admin",
  "password": "xxxx xxxx xxxx xxxx",
  "config": {
    "auto_publish": false,
    "sync_content": true,
    "sync_frequency": "hourly",
    "allowed_post_types": ["post", "page"],
    "seo_plugin": "yoast"
  }
}
```

**Response (201 Created):** Integration object.

---

### 19.9 DELETE /api/v1/integrations/{id}

Disconnect an integration.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 10/min

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `keep_data` | boolean | Keep synced data (default: false) |

**Response (200 OK):**

```json
{
  "data": {
    "id": "int_gsc_001",
    "status": "disconnected",
    "disconnected_at": "2026-07-19T12:00:00Z",
    "data_retained": false
  }
}
```

---

### 19.10 GET /api/v1/integrations/{id}/status

Get integration health status.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Response (200 OK):**

```json
{
  "data": {
    "id": "int_gsc_001",
    "type": "google_search_console",
    "status": "connected",
    "health": {
      "status": "healthy",
      "last_sync_at": "2026-07-19T06:00:00Z",
      "last_error": null,
      "api_quota": {
        "used": 152,
        "limit": 1000,
        "reset_at": "2026-07-20T00:00:00Z"
      },
      "data_freshness": "2 hours",
      "records_synced": 45000
    },
    "permissions": [
      "read_search_analytics",
      "read_sitemaps",
      "read_url_inspection"
    ]
  }
}
```

---

### 19.11 POST /api/v1/integrations/{id}/test

Test integration connection.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 10/min

**Response (200 OK):**

```json
{
  "data": {
    "id": "int_gsc_001",
    "test_result": "success",
    "tests": [
      {"name": "authentication", "status": "pass", "duration_ms": 230},
      {"name": "api_access", "status": "pass", "duration_ms": 150},
      {"name": "data_fetch", "status": "pass", "duration_ms": 890, "records": 100}
    ],
    "tested_at": "2026-07-19T12:00:00Z"
  }
}
```

---

## 20. Reports

---

### 20.1 GET /api/v1/reports

List generated reports.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max items |
| `cursor` | string | — | Pagination cursor |
| `filter[type]` | string | — | `seo_audit`, `ranking`, `backlink`, `content`, `campaign`, `executive` |
| `filter[project_id]` | string | — | Filter by project |
| `filter[status]` | string | — | `generating`, `ready`, `failed` |
| `sort` | string | `created_at:desc` | Sort |

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "rpt_abc123",
      "type": "seo_audit",
      "name": "Monthly SEO Audit - July 2026",
      "project_id": "prj_5tYu2wErT8",
      "project_name": "Main Website",
      "status": "ready",
      "period": {
        "from": "2026-06-01",
        "to": "2026-06-30"
      },
      "format": "pdf",
      "file_size_bytes": 2450000,
      "generated_at": "2026-07-01T06:00:00Z",
      "expires_at": "2026-10-01T06:00:00Z",
      "created_by": "usr_2xKp9mLqR3"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MjB9",
    "has_more": true,
    "total_count": 24
  }
}
```

---

### 20.2 POST /api/v1/reports/generate

Generate a new report.

**Auth:** Bearer token (`analyst`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "type": "seo_audit",
  "name": "Monthly SEO Audit - July 2026",
  "project_id": "prj_5tYu2wErT8",
  "period": {
    "from": "2026-07-01",
    "to": "2026-07-19"
  },
  "format": "pdf",
  "sections": [
    "executive_summary",
    "health_score",
    "rankings",
    "traffic",
    "technical_issues",
    "content_analysis",
    "backlinks",
    "recommendations"
  ],
  "compare_with_previous_period": true,
  "include_charts": true,
  "branding": {
    "logo_url": "https://cdn.seoplatform.com/logos/org_8nQw4vBxT1.png",
    "primary_color": "#ff6600",
    "company_name": "Acme Corp"
  },
  "delivery": {
    "email_recipients": ["ceo@acme.com", "marketing@acme.com"],
    "slack_webhook": true,
    "schedule": null
  }
}
```

**Response (202 Accepted):**

```json
{
  "data": {
    "id": "rpt_def456",
    "type": "seo_audit",
    "status": "generating",
    "estimated_completion_seconds": 120,
    "queued_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 20.3 GET /api/v1/reports/{id}

Get report details and metadata.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Response (200 OK):**

```json
{
  "data": {
    "id": "rpt_abc123",
    "type": "seo_audit",
    "name": "Monthly SEO Audit - July 2026",
    "project_id": "prj_5tYu2wErT8",
    "status": "ready",
    "period": {
      "from": "2026-06-01",
      "to": "2026-06-30"
    },
    "format": "pdf",
    "file_size_bytes": 2450000,
    "sections_included": [
      "executive_summary",
      "health_score",
      "rankings",
      "traffic",
      "technical_issues",
      "content_analysis",
      "backlinks",
      "recommendations"
    ],
    "summary": {
      "health_score": 87,
      "health_score_change": 5,
      "organic_traffic": 145000,
      "traffic_change_pct": 12.5,
      "keywords_in_top_10": 67,
      "new_backlinks": 45,
      "issues_resolved": 23,
      "critical_issues_remaining": 3
    },
    "download_url": "https://api.seoplatform.com/api/v1/reports/rpt_abc123/download",
    "download_expires_at": "2026-07-20T12:00:00Z",
    "generated_at": "2026-07-01T06:00:00Z",
    "expires_at": "2026-10-01T06:00:00Z",
    "created_by": {
      "id": "usr_2xKp9mLqR3",
      "name": "Jane Doe"
    }
  }
}
```

---

### 20.4 GET /api/v1/reports/{id}/download

Download report file.

**Auth:** Bearer token  
**Rate Limit:** 30/min

**Response (302 Found):** Redirect to signed download URL.

Or with `Accept: application/json`:

```json
{
  "data": {
    "download_url": "https://cdn.seoplatform.com/reports/rpt_abc123.pdf?signed=...",
    "expires_at": "2026-07-20T12:00:00Z",
    "file_size_bytes": 2450000,
    "content_type": "application/pdf"
  }
}
```

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `format` | string | original | Override: `pdf`, `xlsx`, `csv`, `html` |

---

### 20.5 GET /api/v1/reports/summary

Get aggregated report summary across projects.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `period` | string | `30d` | Time period |
| `project_ids` | string | — | Comma-separated project IDs |

**Response (200 OK):**

```json
{
  "data": {
    "period": "30d",
    "projects_included": 12,
    "overall_health_score": 84,
    "health_score_change": 3,
    "total_organic_traffic": 1250000,
    "traffic_change_pct": 8.5,
    "total_keywords_tracked": 4200,
    "keywords_in_top_10": 890,
    "total_backlinks": 42000,
    "new_backlinks": 580,
    "total_pages": 15000,
    "total_issues": 420,
    "critical_issues": 12,
    "top_performing_projects": [
      {
        "project_id": "prj_5tYu2wErT8",
        "name": "Main Website",
        "health_score": 87,
        "traffic": 145000,
        "traffic_change": 12.5
      }
    ],
    "needs_attention": [
      {
        "project_id": "prj_9kLm3nPqR7",
        "name": "Blog",
        "reason": "Critical issues increased by 200%",
        "critical_issues": 6
      }
    ]
  }
}
```

---

### 20.6 GET /api/v1/reports/campaign-insights

Get campaign performance insights.

**Auth:** Bearer token  
**Rate Limit:** 60/min

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `period` | string | `30d` | Time period |
| `campaign_type` | string | — | Filter by campaign type |

**Response (200 OK):**

```json
{
  "data": {
    "period": "30d",
    "campaigns": {
      "total": 5,
      "active": 3
    },
    "outreach_metrics": {
      "total_prospects": 250,
      "emails_sent": 180,
      "open_rate": 60.0,
      "reply_rate": 20.0,
      "conversion_rate": 8.3,
      "links_acquired": 15,
      "estimated_link_value": 45000
    },
    "roi": {
      "time_saved_hours": 120,
      "estimated_cost_savings": 6000,
      "links_per_hour": 0.125,
      "avg_da_acquired": 52
    },
    "top_templates": [
      {
        "template_id": "tpl_broken_outreach",
        "name": "Broken Link Outreach",
        "uses": 45,
        "open_rate": 65,
        "reply_rate": 25
      }
    ],
    "best_performing_campaign": {
      "id": "cmp_abc123",
      "name": "Q3 Broken Link Campaign",
      "links_acquired": 5,
      "conversion_rate": 11.1
    }
  }
}
```

---

## 21. Webhooks Management

---

### 21.1 GET /api/v1/webhooks

List registered webhooks.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 60/min

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "whk_abc123",
      "url": "https://client.example.com/webhooks/seo",
      "events": [
        "agent.run.completed",
        "keyword.rank.changed",
        "issue.detected"
      ],
      "status": "active",
      "secret": "whsec_••••••••••••",
      "created_at": "2025-06-01T10:00:00Z",
      "last_triggered_at": "2026-07-19T06:30:00Z",
      "last_response_code": 200,
      "failure_count": 0
    }
  ]
}
```

---

### 21.2 POST /api/v1/webhooks

Register a new webhook.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 10/min

**Request Body:**

```json
{
  "url": "https://client.example.com/webhooks/seo",
  "events": [
    "agent.run.completed",
    "agent.run.failed",
    "keyword.rank.changed",
    "issue.detected"
  ],
  "description": "Production webhook for SEO events",
  "active": true
}
```

**Response (201 Created):**

```json
{
  "data": {
    "id": "whk_def456",
    "url": "https://client.example.com/webhooks/seo",
    "events": [
      "agent.run.completed",
      "agent.run.failed",
      "keyword.rank.changed",
      "issue.detected"
    ],
    "status": "active",
    "secret": "whsec_abc123def456ghi789jkl012mno345",
    "description": "Production webhook for SEO events",
    "created_at": "2026-07-19T12:00:00Z"
  }
}
```

> **Important:** The `secret` is only shown once at creation time. Store it securely.

---

### 21.3 DELETE /api/v1/webhooks/{id}

Delete a webhook.

**Auth:** Bearer token (`admin`+ role)  
**Rate Limit:** 10/min

**Response (200 OK):**

```json
{
  "data": {
    "id": "whk_abc123",
    "deleted": true,
    "deleted_at": "2026-07-19T12:00:00Z"
  }
}
```

---

### 21.4 POST /webhooks/gsc

Incoming webhook from Google Search Console.

**Auth:** GSC verification (internal)  
**Rate Limit:** 100/min

**Request Body:** GSC push notification payload.

**Response (200 OK):**

```json
{
  "received": true
}
```

---

### 21.5 POST /webhooks/bing

Incoming webhook from Bing Webmaster Tools.

**Auth:** Bing verification (internal)  
**Rate Limit:** 100/min

**Response (200 OK):**

```json
{
  "received": true
}
```

---

### 21.6 POST /webhooks/gmail

Incoming webhook from Gmail (for reply tracking).

**Auth:** Google push notification verification  
**Rate Limit:** 100/min

**Request Body:** Gmail push notification.

**Response (200 OK):**

```json
{
  "received": true
}
```

---

## 22. Real-time Streams

---

### 22.1 GET /api/v1/stream/agents

Subscribe to agent run events via SSE.

**Auth:** Bearer token  
**Rate Limit:** 5 concurrent connections

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `agent_ids` | string | Comma-separated agent IDs to filter |
| `project_ids` | string | Comma-separated project IDs to filter |

**SSE Events:**

```
event: agent.run.started
id: evt_001
data: {"run_id":"run_abc","agent_id":"agt_crawler","project_id":"prj_xyz","started_at":"2026-07-19T12:00:00Z"}

event: agent.run.progress
id: evt_002
data: {"run_id":"run_abc","agent_id":"agt_crawler","progress":45,"message":"Crawled 450/1000 pages","pages_crawled":450,"issues_found":12}

event: agent.run.completed
id: evt_003
data: {"run_id":"run_abc","agent_id":"agt_crawler","status":"completed","duration_seconds":1800,"summary":{"pages_crawled":1000,"issues_found":47}}

event: agent.run.failed
id: evt_004
data: {"run_id":"run_abc","agent_id":"agt_crawler","status":"failed","error":{"code":"TIMEOUT","message":"Crawl timed out after 3600 seconds"}}

:heartbeat
```

**Connection:**

```bash
curl -N -H "Authorization: Bearer eyJhbG..." \
  -H "Accept: text/event-stream" \
  "https://api.seoplatform.com/api/v1/stream/agents?agent_ids=agt_crawler,agt_content"
```

---

### 22.2 GET /api/v1/stream/notifications

Subscribe to user notifications via SSE.

**Auth:** Bearer token  
**Rate Limit:** 3 concurrent connections

**SSE Events:**

```
event: notification
id: notif_001
data: {"type":"info","title":"Report Ready","message":"Your SEO audit report for Main Website is ready to download.","action_url":"/reports/rpt_abc123","created_at":"2026-07-19T12:00:00Z"}

event: notification
id: notif_002
data: {"type":"alert","title":"Critical Issue Detected","message":"3 critical SEO issues found on Main Website.","action_url":"/projects/prj_5tYu2wErT8/issues","severity":"critical","created_at":"2026-07-19T12:00:00Z"}

event: notification
id: notif_003
data: {"type":"success","title":"Keyword Improved","message":"'enterprise widget solution' moved from #7 to #4.","project_id":"prj_5tYu2wErT8","created_at":"2026-07-19T12:00:00Z"}

:heartbeat
```

**Connection:**

```bash
curl -N -H "Authorization: Bearer eyJhbG..." \
  -H "Accept: text/event-stream" \
  "https://api.seoplatform.com/api/v1/stream/notifications"
```

---

## 23. Appendix: Data Types & Enums

### 23.1 Common Enums

| Enum | Values |
|---|---|
| `ProjectStatus` | `active`, `paused`, `archived`, `deleted` |
| `AgentStatus` | `active`, `paused`, `disabled`, `error` |
| `RunStatus` | `queued`, `running`, `completed`, `failed`, `cancelled` |
| `IssueSeverity` | `critical`, `high`, `medium`, `low`, `info` |
| `IssueStatus` | `open`, `resolved`, `ignored` |
| `CampaignStatus` | `draft`, `active`, `paused`, `completed`, `archived` |
| `IntegrationStatus` | `connected`, `disconnected`, `error`, `expired` |
| `UserRole` | `owner`, `admin`, `manager`, `analyst`, `viewer`, `billing` |
| `UserStatus` | `active`, `invited`, `suspended`, `deactivated` |
| `ReportType` | `seo_audit`, `ranking`, `backlink`, `content`, `campaign`, `executive`, `custom` |
| `ReportFormat` | `pdf`, `xlsx`, `csv`, `html` |
| `Frequency` | `daily`, `weekly`, `biweekly`, `monthly` |
| `Device` | `desktop`, `mobile`, `tablet` |
| `CampaignType` | `broken_link`, `guest_post`, `unlinked_mention`, `haro` |

### 23.2 ID Format

All entity IDs follow the pattern `{prefix}_{random}`:

| Entity | Prefix | Example |
|---|---|---|
| User | `usr` | `usr_2xKp9mLqR3` |
| Organization | `org` | `org_8nQw4vBxT1` |
| Project | `prj` | `prj_5tYu2wErT8` |
| Agent | `agt` | `agt_crawler` |
| Run | `run` | `run_abc123` |
| Issue | `iss` | `iss_abc123` |
| Page | `pg` | `pg_abc123` |
| Keyword | `kw` | `kw_abc123` |
| Campaign | `cmp` | `cmp_abc123` |
| Message | `msg` | `msg_abc123` |
| Integration | `int` | `int_gsc_001` |
| Report | `rpt` | `rpt_abc123` |
| Webhook | `whk` | `whk_abc123` |
| Invite | `inv` | `inv_abc123` |
| Schedule | `sch` | `sch_abc123` |

### 23.3 Timestamp Format

All timestamps are in ISO 8601 format with UTC timezone:

```
2026-07-19T12:00:00Z
```

### 23.4 Currency

All monetary values use ISO 4217 currency codes and are represented as strings with 2 decimal places:

```json
{
  "price": "99.99",
  "currency": "USD"
}
```

---

## Endpoint Summary

| # | Method | Path | Auth | Rate Limit |
|---|---|---|---|---|
| 1 | POST | /api/v1/auth/register | None | 5/min |
| 2 | POST | /api/v1/auth/login | None | 20/min |
| 3 | POST | /api/v1/auth/refresh | Refresh token | 30/min |
| 4 | POST | /api/v1/auth/forgot-password | None | 3/min |
| 5 | POST | /api/v1/auth/reset-password | None | 5/min |
| 6 | GET | /api/v1/users/me | Bearer | 120/min |
| 7 | PUT | /api/v1/users/me | Bearer | 30/min |
| 8 | GET | /api/v1/users | Admin | 60/min |
| 9 | POST | /api/v1/users | Admin | 20/min |
| 10 | GET | /api/v1/users/{id} | Admin | 120/min |
| 11 | PUT | /api/v1/users/{id} | Admin | 30/min |
| 12 | DELETE | /api/v1/users/{id} | Admin | 10/min |
| 13 | GET | /api/v1/organizations | Bearer | 60/min |
| 14 | POST | /api/v1/organizations | Bearer | 5/min |
| 15 | GET | /api/v1/organizations/{id} | Bearer | 120/min |
| 16 | PUT | /api/v1/organizations/{id} | Admin | 30/min |
| 17 | DELETE | /api/v1/organizations/{id} | Owner | 1/min |
| 18 | GET | /api/v1/organizations/{id}/members | Bearer | 60/min |
| 19 | POST | /api/v1/organizations/{id}/invite | Admin | 20/min |
| 20 | GET | /api/v1/projects | Bearer | 120/min |
| 21 | POST | /api/v1/projects | Manager+ | 10/min |
| 22 | GET | /api/v1/projects/{id} | Bearer | 120/min |
| 23 | PUT | /api/v1/projects/{id} | Manager+ | 30/min |
| 24 | DELETE | /api/v1/projects/{id} | Admin+ | 5/min |
| 25 | GET | /api/v1/projects/{id}/dashboard | Bearer | 60/min |
| 26 | GET | /api/v1/projects/{id}/health-score | Bearer | 60/min |
| 27 | GET | /api/v1/agents | Bearer | 120/min |
| 28 | GET | /api/v1/agents/{id}/runs | Bearer | 60/min |
| 29 | POST | /api/v1/agents/{id}/trigger | Analyst+ | 30/min |
| 30 | GET | /api/v1/agents/{id}/config | Bearer | 120/min |
| 31 | PUT | /api/v1/agents/{id}/config | Manager+ | 10/min |
| 32 | GET | /api/v1/agents/{id}/schedules | Bearer | 60/min |
| 33 | POST | /api/v1/agents/{id}/schedules | Manager+ | 10/min |
| 34 | POST | /api/v1/agents/crawler/scan | Analyst+ | 10/min |
| 35 | GET | /api/v1/projects/{id}/pages | Bearer | 120/min |
| 36 | GET | /api/v1/projects/{id}/pages/{page_id} | Bearer | 60/min |
| 37 | POST | /api/v1/projects/{id}/pages/{page_id}/re-crawl | Analyst+ | 30/min |
| 38 | GET | /api/v1/projects/{id}/issues | Bearer | 120/min |
| 39 | POST | /api/v1/projects/{id}/issues/{id}/resolve | Analyst+ | 60/min |
| 40 | POST | /api/v1/agents/content/audit | Analyst+ | 30/min |
| 41 | POST | /api/v1/agents/content/optimize-meta | Analyst+ | 30/min |
| 42 | POST | /api/v1/agents/content/geo-check | Analyst+ | 20/min |
| 43 | POST | /api/v1/agents/content/keyword-gap | Analyst+ | 10/min |
| 44 | POST | /api/v1/agents/content/generate-brief | Analyst+ | 10/min |
| 45 | POST | /api/v1/agents/content/generate-draft | Analyst+ | 5/min |
| 46 | POST | /api/v1/agents/technical/audit | Analyst+ | 10/min |
| 47 | POST | /api/v1/agents/technical/schema | Analyst+ | 30/min |
| 48 | POST | /api/v1/agents/technical/self-heal | Manager+ | 5/min |
| 49 | POST | /api/v1/agents/technical/multi-engine | Analyst+ | 10/min |
| 50 | GET | /api/v1/projects/{id}/technical-score | Bearer | 60/min |
| 51 | POST | /api/v1/agents/rank/track | Analyst+ | 10/min |
| 52 | GET | /api/v1/projects/{id}/keywords | Bearer | 120/min |
| 53 | GET | /api/v1/projects/{id}/keywords/{id}/history | Bearer | 60/min |
| 54 | GET | /api/v1/projects/{id}/serp-features | Bearer | 60/min |
| 55 | POST | /api/v1/projects/{id}/keywords/import | Analyst+ | 5/min |
| 56 | POST | /api/v1/agents/backlink/haro/parse | Analyst+ | 20/min |
| 57 | POST | /api/v1/agents/backlink/broken/scan | Analyst+ | 5/min |
| 58 | POST | /api/v1/agents/backlink/broken/outreach | Manager+ | 5/min |
| 59 | POST | /api/v1/agents/backlink/guest-prospect | Analyst+ | 5/min |
| 60 | POST | /api/v1/agents/backlink/guest-pitch | Manager+ | 5/min |
| 61 | POST | /api/v1/agents/backlink/unlinked/scan | Analyst+ | 5/min |
| 62 | POST | /api/v1/agents/backlink/unlinked/request | Manager+ | 5/min |
| 63 | POST | /api/v1/agents/backlink/monitor | Analyst+ | 10/min |
| 64 | GET | /api/v1/campaigns | Bearer | 120/min |
| 65 | POST | /api/v1/campaigns | Manager+ | 10/min |
| 66 | GET | /api/v1/campaigns/{id} | Bearer | 120/min |
| 67 | PATCH | /api/v1/campaigns/{id} | Manager+ | 30/min |
| 68 | PATCH | /api/v1/campaigns/{id}/status | Manager+ | 30/min |
| 69 | GET | /api/v1/campaigns/stats | Bearer | 60/min |
| 70 | GET | /api/v1/campaigns/{id}/messages | Bearer | 60/min |
| 71 | POST | /api/v1/campaigns/{id}/messages/send | Manager+ | 30/min |
| 72 | POST | /api/v1/campaigns/{id}/follow-up | Manager+ | 5/min |
| 73 | GET | /api/v1/integrations | Bearer | 120/min |
| 74 | POST | /api/v1/integrations/gsc/connect | Admin+ | 5/min |
| 75 | POST | /api/v1/integrations/bing/connect | Admin+ | 5/min |
| 76 | POST | /api/v1/integrations/yandex/connect | Admin+ | 5/min |
| 77 | POST | /api/v1/integrations/naver/connect | Admin+ | 5/min |
| 78 | POST | /api/v1/integrations/ga4/connect | Admin+ | 5/min |
| 79 | POST | /api/v1/integrations/gmail/connect | Admin+ | 5/min |
| 80 | POST | /api/v1/integrations/wordpress/connect | Admin+ | 5/min |
| 81 | DELETE | /api/v1/integrations/{id} | Admin+ | 10/min |
| 82 | GET | /api/v1/integrations/{id}/status | Bearer | 60/min |
| 83 | POST | /api/v1/integrations/{id}/test | Admin+ | 10/min |
| 84 | GET | /api/v1/reports | Bearer | 60/min |
| 85 | POST | /api/v1/reports/generate | Analyst+ | 10/min |
| 86 | GET | /api/v1/reports/{id} | Bearer | 60/min |
| 87 | GET | /api/v1/reports/{id}/download | Bearer | 30/min |
| 88 | GET | /api/v1/reports/summary | Bearer | 60/min |
| 89 | GET | /api/v1/reports/campaign-insights | Bearer | 60/min |
| 90 | GET | /api/v1/webhooks | Admin+ | 60/min |
| 91 | POST | /api/v1/webhooks | Admin+ | 10/min |
| 92 | DELETE | /api/v1/webhooks/{id} | Admin+ | 10/min |
| 93 | POST | /webhooks/gsc | Internal | 100/min |
| 94 | POST | /webhooks/bing | Internal | 100/min |
| 95 | POST | /webhooks/gmail | Internal | 100/min |
| 96 | GET | /api/v1/stream/agents | Bearer | 5 conn |
| 97 | GET | /api/v1/stream/notifications | Bearer | 3 conn |

**Total: 97 endpoints across 14 resource groups.**

---

*Document generated: 2026-07-19*  
*API Version: v1*  
*Status: Stable*
