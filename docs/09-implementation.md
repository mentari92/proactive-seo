# ProActive SEO Implementation Guide

## Contract authority

The executable source of truth is split between `contracts/api-v1.yaml` and
`contracts/platform.yaml`. The former contains all 97 external operations. The latter contains all
37 application tables, eight agents, 13 execution providers, status enums, and the OpenAI role
router. `contracts/reconciliation.md` explains every blueprint conflict resolved during the build.

## Services

Fourteen FastAPI services share the `proactive_core` package but are independently deployable. The
local `api` process is an aggregate contract host for frontend development and contract testing;
production ingress routes resource groups to their owning services.

Every service exposes `/health`, `/health/ready`, `/health/startup`, and `/metrics`. Public JSON uses
the documented envelope, RFC 7807 failures, request IDs, cursor metadata, typed opaque IDs, and role
checks. Asynchronous operations return an agent run and task identifier with HTTP 202.

## Data and tenancy

PostgreSQL 16 is authoritative. The first migration creates the two application schemas and exactly
37 logical tables. It intentionally keeps the eight future high-volume tables unpartitioned until
their foreign-key-safe archival migrations are activated. Row-level security is forced on tenant
tables. Application transactions set `app.current_org_id` and `app.current_user_id` with transaction-
local configuration. Permissions isolate through the owning role because that table has no direct
organization column.

Redis uses separate key prefixes for sessions, rate limits, cache, Celery, and the versioned agent
event stream. Production should assign separate ElastiCache logical clusters when workload isolation
requires independent eviction and availability policies.

## Identity and side-effect safety

Passwords use Argon2id. Access tokens are RS256 and expire after 15 minutes. Seven-day refresh tokens
rotate once inside a server-side family; reuse revokes the whole family. Local/test signing keys are
ephemeral. Staging and production refuse to start without explicit key material.

Email sending, CMS publication, and automatic page changes require both an environment-level live
action switch and a per-action approval. CI has no live credentials and uses provider fakes.

## Agent execution

Celery uses Redis as broker/result backend with one queue per agent. Redis Streams carries UUIDv7,
versioned event envelopes. Agent code is deterministic before an LLM is introduced: crawling,
technical rules, dual content scoring, SERP normalization, outreach sequencing, competitor
comparison, decision scoring, and execution gates can all be tested without a provider.

OpenAI calls use the Responses API with Pydantic parsing. The role router preserves cost and latency:
Luna handles extraction, Terra routine generation, Sol high-impact reasoning, and GPT-5.3-Codex code
repair. GPT-4o is retained only as a disabled legacy configuration entry.

## Deployment

Docker Compose profiles are `core`, `agents`, `integrations`, `observability`, and `full`. The Helm
chart renders all services with non-root/read-only containers, probes, HPA, disruption budgets,
network policies, External Secrets, and a frontend ingress. ArgoCD owns desired-state synchronization.

Terraform provisions VPC networking, EKS, RDS PostgreSQL, ElastiCache Redis, KMS, S3, Secrets Manager,
and a Cloudflare custom WAF ruleset. Apply only through a reviewed environment with remote encrypted
state and workload identity.

## Release sequence

1. Run all non-live CI suites and create immutable, signed/SBOM-attached images.
2. Back up the database and run migrations in staging.
3. Run credential-gated provider smoke tests in read-only mode.
4. Deploy a 10% canary and hold until error, latency, queue, and provider-cost SLOs pass.
5. Increase to 50%, then 100%, repeating the SLO gate at each stage.
6. Roll back images automatically on SLO breach. Database migrations must remain backward compatible
   until the previous application version is no longer a rollback target.

