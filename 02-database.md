# 02 — Database Schema

> Enterprise-grade PostgreSQL schema for the Proactive SEO Platform.
> Multi-tenant, partitioned, full-text-search ready, with audit trail.

---

## Table of Contents

1. [Conventions & Extensions](#conventions--extensions)
2. [Utility Functions & Triggers](#utility-functions--triggers)
3. [Core Tables](#core-tables)
4. [Agent System Tables](#agent-system-tables)
5. [SEO Data Tables](#seo-data-tables)
6. [HARO Tables](#haro-tables)
7. [Content Tables](#content-tables)
8. [Analytics Tables](#analytics-tables)
9. [Security Tables](#security-tables)
10. [Row-Level Security Policies](#row-level-security-policies)
11. [Partition Maintenance](#partition-maintenance)

---

## Conventions & Extensions

```sql
-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";       -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";         -- gen_random_uuid(), crypt(), pgp_sym_encrypt/decrypt
CREATE EXTENSION IF NOT EXISTS "pg_trgm";          -- trigram similarity search
CREATE EXTENSION IF NOT EXISTS "btree_gin";        -- GIN index on scalar types
CREATE EXTENSION IF NOT EXISTS "btree_gist";       -- GiST index on scalar types
CREATE EXTENSION IF NOT EXISTS "hstore";           -- key-value pairs
CREATE EXTENSION IF NOT EXISTS "intarray";         -- integer array operators

-- ============================================================
-- SCHEMAS
-- ============================================================
CREATE SCHEMA IF NOT EXISTS seo;
CREATE SCHEMA IF NOT EXISTS audit;
SET search_path TO seo, public;

-- ============================================================
-- CUSTOM TYPES / ENUMS
-- ============================================================

CREATE TYPE seo.org_plan AS ENUM ('free', 'starter', 'professional', 'enterprise', 'custom');
CREATE TYPE seo.user_status AS ENUM ('active', 'invited', 'suspended', 'deactivated');
CREATE TYPE seo.agent_status AS ENUM ('active', 'paused', 'disabled', 'error');
CREATE TYPE seo.agent_run_status AS ENUM ('pending', 'running', 'success', 'failed', 'cancelled', 'timeout');
CREATE TYPE seo.task_status AS ENUM ('queued', 'claimed', 'running', 'success', 'failed', 'cancelled', 'retry');
CREATE TYPE seo.crawl_status AS ENUM ('pending', 'crawling', 'completed', 'failed', 'skipped');
CREATE TYPE seo.issue_severity AS ENUM ('critical', 'high', 'medium', 'low', 'info');
CREATE TYPE seo.fix_status AS ENUM ('pending', 'applied', 'reverted', 'failed');
CREATE TYPE seo.keyword_status AS ENUM ('tracking', 'paused', 'archived');
CREATE TYPE seo.content_status AS ENUM ('draft', 'review', 'approved', 'published', 'archived');
CREATE TYPE seo.campaign_status AS ENUM ('draft', 'active', 'paused', 'completed', 'archived');
CREATE TYPE seo.contact_status AS ENUM ('identified', 'contacted', 'responded', 'accepted', 'declined', 'bounced');
CREATE TYPE seo.message_status AS ENUM ('queued', 'sent', 'delivered', 'opened', 'clicked', 'bounced', 'replied');
CREATE TYPE seo.haro_status AS ENUM ('new', 'matched', 'drafted', 'submitted', 'accepted', 'declined', 'expired');
CREATE TYPE seo.oauth_provider AS ENUM ('google', 'google_search_console', 'google_analytics', 'bing', 'bing_webmaster', 'ahrefs', 'semrush', 'moz', 'screaming_frog', 'wordpress', 'shopify');
CREATE TYPE seo.anomaly_type AS ENUM ('traffic_drop', 'traffic_spike', 'ranking_drop', 'ranking_gain', 'crawl_error_spike', 'backlink_loss', 'index_coverage_drop', 'core_web_vitals_degradation', 'custom');
CREATE TYPE seo.report_format AS ENUM ('pdf', 'html', 'csv', 'json', 'xlsx');
CREATE TYPE seo.event_severity AS ENUM ('debug', 'info', 'warning', 'error', 'critical');
```

---

## Utility Functions & Triggers

```sql
-- ============================================================
-- UPDATED_AT TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION seo.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- SOFT DELETE TRIGGER — sets deleted_at if not already set
-- ============================================================
CREATE OR REPLACE FUNCTION seo.handle_soft_delete()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.deleted_at IS NULL AND OLD.deleted_at IS NOT NULL THEN
        -- Prevent un-deletion
        NEW.deleted_at = OLD.deleted_at;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- AUDIT LOG TRIGGER — generic, fires on INSERT/UPDATE/DELETE
-- ============================================================
CREATE OR REPLACE FUNCTION audit.log_change()
RETURNS TRIGGER AS $$
DECLARE
    _org_id     UUID;
    _user_id    UUID;
    _record_id  UUID;
    _old_data   JSONB;
    _new_data   JSONB;
BEGIN
    -- Try to extract org_id and user_id from the row
    IF TG_OP = 'DELETE' THEN
        _org_id    := (ROW_TO_JSON(OLD)->>'org_id')::UUID;
        _record_id := (ROW_TO_JSON(OLD)->>'id')::UUID;
        _old_data  := ROW_TO_JSON(OLD)::JSONB;
        _new_data  := NULL;
    ELSE
        _org_id    := (ROW_TO_JSON(NEW)->>'org_id')::UUID;
        _record_id := (ROW_TO_JSON(NEW)->>'id')::UUID;
        _old_data  := CASE WHEN TG_OP = 'UPDATE' THEN ROW_TO_JSON(OLD)::JSONB ELSE NULL END;
        _new_data  := ROW_TO_JSON(NEW)::JSONB;
    END IF;

    -- Try to get current user from session variable
    BEGIN
        _user_id := current_setting('app.current_user_id', true)::UUID;
    EXCEPTION WHEN OTHERS THEN
        _user_id := NULL;
    END;

    INSERT INTO audit.audit_logs (
        org_id, user_id, table_schema, table_name, record_id,
        action, old_data, new_data, ip_address
    ) VALUES (
        _org_id, _user_id, TG_TABLE_SCHEMA, TG_TABLE_NAME, _record_id,
        TG_OP, _old_data, _new_data,
        inet(current_setting('app.client_ip', true))
    );

    IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- PARTITION HELPER — auto-create monthly partitions
-- ============================================================
CREATE OR REPLACE FUNCTION seo.create_monthly_partition(
    _parent_table TEXT,
    _start_date   DATE
)
RETURNS VOID AS $$
DECLARE
    _part_name  TEXT;
    _start      DATE;
    _end        DATE;
BEGIN
    _start := DATE_TRUNC('month', _start_date);
    _end   := _start + INTERVAL '1 month';
    _part_name := _parent_table || '_' || TO_CHAR(_start, 'YYYY_MM');

    EXECUTE FORMAT(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
        _part_name, _parent_table, _start, _end
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- CURRENT TENANT HELPERS
-- ============================================================
CREATE OR REPLACE FUNCTION seo.current_org_id()
RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.current_org_id', true), '')::UUID;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION seo.current_user_id()
RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.current_user_id', true), '')::UUID;
$$ LANGUAGE sql STABLE;
```

---

## Core Tables

### 1. organizations

Multi-tenant root entity. Every other table references `org_id`.

```sql
CREATE TABLE seo.organizations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(100) NOT NULL UNIQUE,
    plan            seo.org_plan NOT NULL DEFAULT 'free',
    settings        JSONB NOT NULL DEFAULT '{}',
        /* settings schema:
           {
             "max_projects": 5,
             "max_keywords": 1000,
             "max_pages_crawl": 10000,
             "max_agents": 3,
             "features": ["crawling", "serp_tracking", "content_gen"],
             "default_locale": "en-US",
             "timezone": "America/New_York",
             "branding": { "logo_url": "", "primary_color": "" }
           }
        */
    billing_email   VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE  seo.organizations IS 'Multi-tenant root. All data is scoped to an organization.';
COMMENT ON COLUMN seo.organizations.id IS 'Primary key, UUID v4.';
COMMENT ON COLUMN seo.organizations.name IS 'Display name of the organization.';
COMMENT ON COLUMN seo.organizations.slug IS 'URL-safe unique identifier, used in subdomains.';
COMMENT ON COLUMN seo.organizations.plan IS 'Subscription plan tier.';
COMMENT ON COLUMN seo.organizations.settings IS 'JSONB blob for org-level configuration.';
COMMENT ON COLUMN seo.organizations.stripe_customer_id IS 'Stripe billing customer ID.';
COMMENT ON COLUMN seo.organizations.deleted_at IS 'Soft-delete timestamp. Non-null means deleted.';

CREATE INDEX idx_org_slug ON seo.organizations (slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_org_plan ON seo.organizations (plan) WHERE deleted_at IS NULL;
CREATE INDEX idx_org_settings ON seo.organizations USING GIN (settings);

CREATE TRIGGER trg_org_updated_at
    BEFORE UPDATE ON seo.organizations
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_org_soft_delete
    BEFORE UPDATE ON seo.organizations
    FOR EACH ROW EXECUTE FUNCTION seo.handle_soft_delete();

CREATE TRIGGER trg_org_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.organizations
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

### 2. users

```sql
CREATE TABLE seo.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    email           VARCHAR(255) NOT NULL,
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    password_hash   VARCHAR(255),
    full_name       VARCHAR(255) NOT NULL,
    avatar_url      TEXT,
    status          seo.user_status NOT NULL DEFAULT 'invited',
    role_id         UUID REFERENCES seo.roles(id),
    last_login_at   TIMESTAMPTZ,
    last_login_ip   INET,
    mfa_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret      VARCHAR(255),         -- TOTP secret, encrypted at rest
    preferences     JSONB NOT NULL DEFAULT '{}',
        /* {
             "theme": "dark",
             "locale": "en-US",
             "notifications": { "email": true, "slack": false },
             "dashboard_layout": {}
           }
        */
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (org_id, email)
);

COMMENT ON TABLE  seo.users IS 'Users belonging to an organization. RBAC via role_id.';
COMMENT ON COLUMN seo.users.email IS 'Login email. Unique within an org.';
COMMENT ON COLUMN seo.users.password_hash IS 'bcrypt/argon2 hash. NULL for SSO-only users.';
COMMENT ON COLUMN seo.users.mfa_secret IS 'Encrypted TOTP secret for 2FA.';
COMMENT ON COLUMN seo.users.role_id IS 'FK to roles. Defines permission set.';

CREATE INDEX idx_user_org ON seo.users (org_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_user_email ON seo.users (org_id, email) WHERE deleted_at IS NULL;
CREATE INDEX idx_user_status ON seo.users (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_user_last_login ON seo.users (last_login_at DESC);

CREATE TRIGGER trg_user_updated_at
    BEFORE UPDATE ON seo.users
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_user_soft_delete
    BEFORE UPDATE ON seo.users
    FOR EACH ROW EXECUTE FUNCTION seo.handle_soft_delete();

CREATE TRIGGER trg_user_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.users
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

### 3. roles + permissions

```sql
CREATE TABLE seo.roles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    is_system       BOOLEAN NOT NULL DEFAULT FALSE,  -- system roles cannot be deleted
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (org_id, name)
);

COMMENT ON TABLE  seo.roles IS 'Named roles within an organization.';
COMMENT ON COLUMN seo.roles.is_system IS 'True for built-in roles (Owner, Admin, Viewer). Cannot be modified.';

CREATE TABLE seo.permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id         UUID NOT NULL REFERENCES seo.roles(id) ON DELETE CASCADE,
    resource        VARCHAR(100) NOT NULL,  -- e.g. 'project', 'keyword', 'agent', 'report'
    action          VARCHAR(50) NOT NULL,   -- e.g. 'read', 'write', 'delete', 'admin'
    conditions      JSONB DEFAULT '{}',     -- optional ABAC conditions
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (role_id, resource, action)
);

COMMENT ON TABLE  seo.permissions IS 'Granular permissions assigned to roles.';
COMMENT ON COLUMN seo.permissions.resource IS 'Resource type the permission applies to.';
COMMENT ON COLUMN seo.permissions.action IS 'Action allowed: read, write, delete, admin.';
COMMENT ON COLUMN seo.conditions IS 'Optional ABAC conditions as JSONB.';

CREATE INDEX idx_perm_role ON seo.permissions (role_id);
CREATE INDEX idx_perm_resource ON seo.permissions (resource, action);

CREATE TRIGGER trg_role_updated_at
    BEFORE UPDATE ON seo.roles
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_role_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.roles
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

### 4. projects

```sql
CREATE TABLE seo.projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    name            VARCHAR(255) NOT NULL,
    domain          VARCHAR(255) NOT NULL,          -- e.g. "example.com"
    url             TEXT NOT NULL,                   -- full base URL
    locale          VARCHAR(10) DEFAULT 'en-US',
    crawl_settings  JSONB NOT NULL DEFAULT '{}',
        /* {
             "max_pages": 10000,
             "crawl_depth": 5,
             "respect_robots_txt": true,
             "user_agent": "SEOBot/1.0",
             "rate_limit_rps": 2,
             "include_patterns": ["*"],
             "exclude_patterns": ["/admin/*", "/wp-admin/*"],
             "follow_nofollow": false,
             "render_javascript": true
           }
        */
    tracking_settings JSONB NOT NULL DEFAULT '{}',
        /* {
             "serp_track_daily": true,
             "serp_track_locale": "en-US",
             "serp_track_device": "desktop",
             "competitors": ["competitor1.com", "competitor2.com"]
           }
        */
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (org_id, domain)
);

COMMENT ON TABLE  seo.projects IS 'A project represents a tracked domain/website within an org.';

CREATE INDEX idx_project_org ON seo.projects (org_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_project_domain ON seo.projects (domain) WHERE deleted_at IS NULL;

CREATE TRIGGER trg_project_updated_at
    BEFORE UPDATE ON seo.projects
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_project_soft_delete
    BEFORE UPDATE ON seo.projects
    FOR EACH ROW EXECUTE FUNCTION seo.handle_soft_delete();

CREATE TRIGGER trg_project_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.projects
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

### 5. api_keys

```sql
CREATE TABLE seo.api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    user_id         UUID NOT NULL REFERENCES seo.users(id),
    name            VARCHAR(255) NOT NULL,
    key_prefix      VARCHAR(10) NOT NULL,            -- first 8 chars for identification
    key_hash        VARCHAR(255) NOT NULL,            -- SHA-256 hash of the full key
    scopes          TEXT[] NOT NULL DEFAULT '{}',     -- e.g. {'read:projects','write:agents'}
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    last_used_ip    INET,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE  seo.api_keys IS 'API keys for programmatic access. Key itself is never stored — only SHA-256 hash.';
COMMENT ON COLUMN seo.api_keys.key_prefix IS 'First N chars shown to user for identification.';
COMMENT ON COLUMN seo.api_keys.key_hash IS 'SHA-256 hash. Full key shown only once at creation.';

CREATE INDEX idx_apikey_org ON seo.api_keys (org_id) WHERE deleted_at IS NULL AND is_active;
CREATE INDEX idx_apikey_hash ON seo.api_keys (key_hash) WHERE is_active;
CREATE INDEX idx_apikey_user ON seo.api_keys (user_id) WHERE deleted_at IS NULL;

CREATE TRIGGER trg_apikey_updated_at
    BEFORE UPDATE ON seo.api_keys
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 6. oauth_connections

```sql
CREATE TABLE seo.oauth_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    user_id         UUID NOT NULL REFERENCES seo.users(id),
    provider        seo.oauth_provider NOT NULL,
    provider_account_id VARCHAR(255) NOT NULL,        -- e.g. Google account ID
    provider_account_name VARCHAR(255),               -- display name
    access_token    TEXT NOT NULL,                     -- pgp_sym_encrypt'd
    refresh_token   TEXT,                              -- pgp_sym_encrypt'd
    token_type      VARCHAR(50) DEFAULT 'Bearer',
    scopes          TEXT[],
    expires_at      TIMESTAMPTZ,
    provider_data   JSONB NOT NULL DEFAULT '{}',      -- raw provider metadata
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync_at    TIMESTAMPTZ,
    sync_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (org_id, provider, provider_account_id)
);

COMMENT ON TABLE  seo.oauth_connections IS 'OAuth tokens for external service integrations (GSC, GA4, Bing, etc.).';
COMMENT ON COLUMN seo.oauth_connections.access_token IS 'Encrypted with pgp_sym_encrypt. Decrypt in app layer.';
COMMENT ON COLUMN seo.oauth_connections.provider IS 'Which service this connection is for.';

CREATE INDEX idx_oauth_org ON seo.oauth_connections (org_id) WHERE deleted_at IS NULL AND is_active;
CREATE INDEX idx_oauth_provider ON seo.oauth_connections (provider) WHERE is_active;
CREATE INDEX idx_oauth_user ON seo.oauth_connections (user_id) WHERE deleted_at IS NULL;

CREATE TRIGGER trg_oauth_updated_at
    BEFORE UPDATE ON seo.oauth_connections
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

---

## Agent System Tables

### 7. agents

```sql
CREATE TABLE seo.agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID REFERENCES seo.projects(id),
    name            VARCHAR(255) NOT NULL,
    type            VARCHAR(100) NOT NULL,            -- 'site_audit', 'serp_tracker', 'content_generator', 'backlink_monitor', 'anomaly_detector', 'haro_monitor', 'report_generator'
    description     TEXT,
    status          seo.agent_status NOT NULL DEFAULT 'active',
    config          JSONB NOT NULL DEFAULT '{}',
        /* varies by agent type. Example for site_audit:
           {
             "schedule": "0 2 * * 0",          -- cron expression
             "max_pages": 5000,
             "check_external_links": true,
             "check_images": true,
             "lighthouse_audit": true,
             "notify_on": ["critical", "high"],
             "slack_webhook": "https://hooks.slack.com/..."
           }
        */
    schedule        VARCHAR(100),                     -- cron expression (nullable for on-demand agents)
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    run_count       INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE  seo.agents IS 'Configurable autonomous agents (site audit, SERP tracker, etc.).';
COMMENT ON COLUMN seo.agents.type IS 'Agent type determines config schema and behavior.';
COMMENT ON COLUMN seo.agents.schedule IS 'Cron expression. NULL means on-demand only.';

CREATE INDEX idx_agent_org ON seo.agents (org_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_agent_project ON seo.agents (project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_agent_status ON seo.agents (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_agent_next_run ON seo.agents (next_run_at)
    WHERE status = 'active' AND deleted_at IS NULL;

CREATE TRIGGER trg_agent_updated_at
    BEFORE UPDATE ON seo.agents
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_agent_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.agents
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

### 8. agent_runs

```sql
CREATE TABLE seo.agent_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    agent_id        UUID NOT NULL REFERENCES seo.agents(id),
    status          seo.agent_run_status NOT NULL DEFAULT 'pending',
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    duration_ms     INTEGER GENERATED ALWAYS AS (
                        EXTRACT(EPOCH FROM (finished_at - started_at)) * 1000
                    ) STORED,
    trigger         VARCHAR(50) NOT NULL DEFAULT 'scheduled',  -- 'scheduled', 'manual', 'api', 'webhook'
    config_snapshot JSONB,                        -- config at time of run (for reproducibility)
    result_summary  JSONB NOT NULL DEFAULT '{}',
        /* {
             "pages_crawled": 1500,
             "issues_found": 42,
             "critical": 3,
             "high": 12,
             "medium": 20,
             "low": 7
           }
        */
    error_message   TEXT,
    error_stack     TEXT,
    logs_url        TEXT,                         -- S3/GCS URL to full logs
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.agent_runs IS 'Execution log for agent runs. High-volume, consider partitioning.';

CREATE INDEX idx_run_agent ON seo.agent_runs (agent_id, created_at DESC);
CREATE INDEX idx_run_org ON seo.agent_runs (org_id, created_at DESC);
CREATE INDEX idx_run_status ON seo.agent_runs (status) WHERE status IN ('pending', 'running');
CREATE INDEX idx_run_started ON seo.agent_runs (started_at DESC);

CREATE TRIGGER trg_run_updated_at
    BEFORE UPDATE ON seo.agent_runs
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 9. agent_tasks

```sql
CREATE TABLE seo.agent_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    agent_id        UUID NOT NULL REFERENCES seo.agents(id),
    agent_run_id    UUID REFERENCES seo.agent_runs(id),
    task_type       VARCHAR(100) NOT NULL,            -- 'crawl_page', 'check_serp', 'generate_content', etc.
    status          seo.task_status NOT NULL DEFAULT 'queued',
    priority        SMALLINT NOT NULL DEFAULT 5,      -- 1 (highest) to 10 (lowest)
    payload         JSONB NOT NULL DEFAULT '{}',      -- task-specific input data
    result          JSONB,                            -- task output
    attempts        SMALLINT NOT NULL DEFAULT 0,
    max_attempts    SMALLINT NOT NULL DEFAULT 3,
    claimed_at      TIMESTAMPTZ,
    claimed_by      VARCHAR(255),                     -- worker ID / hostname
    scheduled_for   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.agent_tasks IS 'Work queue for agent task processing. Poll-based with SKIP LOCKED.';

CREATE INDEX idx_task_queue ON seo.agent_tasks (status, priority, scheduled_for)
    WHERE status IN ('queued', 'retry');
CREATE INDEX idx_task_agent ON seo.agent_tasks (agent_id, created_at DESC);
CREATE INDEX idx_task_run ON seo.agent_tasks (agent_run_id);
CREATE INDEX idx_task_org ON seo.agent_tasks (org_id, created_at DESC);
CREATE INDEX idx_task_claimed ON seo.agent_tasks (claimed_by, claimed_at)
    WHERE status = 'running';

CREATE TRIGGER trg_task_updated_at
    BEFORE UPDATE ON seo.agent_tasks
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 10. agent_events

```sql
CREATE TABLE seo.agent_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    agent_id        UUID NOT NULL REFERENCES seo.agents(id),
    agent_run_id    UUID REFERENCES seo.agent_runs(id),
    event_type      VARCHAR(100) NOT NULL,            -- 'started', 'progress', 'completed', 'failed', 'alert', 'notification'
    severity        seo.event_severity NOT NULL DEFAULT 'info',
    message         TEXT NOT NULL,
    data            JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

COMMENT ON TABLE  seo.agent_events IS 'Event bus log for agent lifecycle events. Partitioned by month.';

CREATE INDEX idx_event_agent ON seo.agent_events (agent_id, created_at DESC);
CREATE INDEX idx_event_org ON seo.agent_events (org_id, created_at DESC);
CREATE INDEX idx_event_type ON seo.agent_events (event_type, created_at DESC);
CREATE INDEX idx_event_severity ON seo.agent_events (severity, created_at DESC)
    WHERE severity IN ('warning', 'error', 'critical');

-- Partitions: auto-created by cron job or manual
-- SELECT seo.create_monthly_partition('seo.agent_events', '2025-01-01');
-- SELECT seo.create_monthly_partition('seo.agent_events', '2025-02-01');
-- ... etc.
```

---

## SEO Data Tables

### 11. pages

```sql
CREATE TABLE seo.pages (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    project_id      UUID NOT NULL,
    url             TEXT NOT NULL,
    url_hash        VARCHAR(64) NOT NULL,             -- SHA-256 of normalized URL for dedup
    status_code     SMALLINT,
    content_type    VARCHAR(100),
    crawl_status    seo.crawl_status NOT NULL DEFAULT 'pending',
    title           TEXT,
    meta_description TEXT,
    h1              TEXT,
    word_count      INTEGER,
    reading_time_ms INTEGER,
    http_headers    JSONB DEFAULT '{}',
    body_text       TEXT,                              -- extracted text for FTS
    body_text_tsv   TSVECTOR GENERATED ALWAYS AS (TO_TSVECTOR('english', COALESCE(body_text, ''))) STORED,
    dom_size_bytes  INTEGER,
    response_time_ms INTEGER,
    redirect_url    TEXT,
    canonical_url   TEXT,
    meta_robots     VARCHAR(255),
    hreflang        JSONB DEFAULT '[]',                -- [{lang, url}]
    structured_data JSONB DEFAULT '[]',                -- JSON-LD array
    open_graph      JSONB DEFAULT '{}',
    twitter_card    JSONB DEFAULT '{}',
    images          JSONB DEFAULT '[]',                -- [{src, alt, width, height, size}]
    links_internal  INTEGER DEFAULT 0,
    links_external  INTEGER DEFAULT 0,
    links_broken    INTEGER DEFAULT 0,
    http_version    VARCHAR(10),
    ssl_valid       BOOLEAN,
    ssl_expiry      DATE,
    lighthouse      JSONB DEFAULT '{}',                -- Lighthouse scores
    core_web_vitals JSONB DEFAULT '{}',                -- {LCP, FID, CLS, INP, TTFB}
    crawl_depth     SMALLINT,
    first_crawled_at TIMESTAMPTZ,
    last_crawled_at TIMESTAMPTZ,
    crawl_count     INTEGER NOT NULL DEFAULT 0,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    PRIMARY KEY (id, project_id, created_at)
) PARTITION BY RANGE (created_at);

COMMENT ON TABLE  seo.pages IS 'Crawled pages. Partitioned by created_at for time-series management.';
COMMENT ON COLUMN seo.pages.body_text_tsv IS 'Auto-generated tsvector for full-text search.';
COMMENT ON COLUMN seo.pages.url_hash IS 'SHA-256 of normalized URL for fast dedup lookups.';

-- Create default partition first
CREATE TABLE seo.pages_default PARTITION OF seo.pages DEFAULT;

CREATE INDEX idx_page_project ON seo.pages (project_id, url_hash);
CREATE INDEX idx_page_org ON seo.pages (org_id, created_at DESC);
CREATE INDEX idx_page_url_hash ON seo.pages (url_hash);
CREATE INDEX idx_page_status ON seo.pages (crawl_status) WHERE crawl_status != 'completed';
CREATE INDEX idx_page_status_code ON seo.pages (project_id, status_code);
CREATE INDEX idx_page_fts ON seo.pages USING GIN (body_text_tsv);
CREATE INDEX idx_page_title ON seo.pages USING GIN (title gin_trgm_ops) WHERE title IS NOT NULL;
CREATE INDEX idx_page_lighthouse ON seo.pages USING GIN (lighthouse);
CREATE INDEX idx_page_cwv ON seo.pages USING GIN (core_web_vitals);
CREATE INDEX idx_page_last_crawl ON seo.pages (project_id, last_crawled_at DESC NULLS LAST);

-- Partitions: created monthly per project via cron
```

### 12. page_issues

```sql
CREATE TABLE seo.page_issues (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID NOT NULL REFERENCES seo.projects(id),
    page_id         UUID NOT NULL,                    -- FK to pages (compound, handled at app layer)
    agent_run_id    UUID REFERENCES seo.agent_runs(id),
    issue_type      VARCHAR(100) NOT NULL,            -- 'missing_title', 'duplicate_title', 'broken_link', 'missing_alt', 'thin_content', 'missing_meta_desc', 'slow_lcp', etc.
    severity        seo.issue_severity NOT NULL,
    category        VARCHAR(50) NOT NULL,             -- 'technical', 'on_page', 'performance', 'content', 'links'
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    details         JSONB NOT NULL DEFAULT '{}',      -- issue-specific data
    recommendation  TEXT,                              -- AI-generated fix suggestion
    auto_fixable    BOOLEAN NOT NULL DEFAULT FALSE,
    auto_fix_config JSONB,                            -- parameters for auto-fix agent
    first_detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.page_issues IS 'SEO issues detected during crawls. One row per unique issue per page.';

CREATE INDEX idx_issue_project ON seo.page_issues (project_id, severity) WHERE is_active;
CREATE INDEX idx_issue_page ON seo.page_issues (page_id) WHERE is_active;
CREATE INDEX idx_issue_org ON seo.page_issues (org_id, created_at DESC);
CREATE INDEX idx_issue_type ON seo.page_issues (issue_type, severity) WHERE is_active;
CREATE INDEX idx_issue_severity ON seo.page_issues (severity) WHERE is_active;
CREATE INDEX idx_issue_auto_fix ON seo.page_issues (auto_fixable) WHERE is_active AND auto_fixable;
CREATE INDEX idx_issue_unresolved ON seo.page_issues (project_id, first_detected_at)
    WHERE resolved_at IS NULL;
CREATE INDEX idx_issue_details ON seo.page_issues USING GIN (details);

CREATE TRIGGER trg_issue_updated_at
    BEFORE UPDATE ON seo.page_issues
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_issue_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.page_issues
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

### 13. page_fixes

```sql
CREATE TABLE seo.page_fixes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID NOT NULL REFERENCES seo.projects(id),
    page_id         UUID NOT NULL,
    issue_id        UUID NOT NULL REFERENCES seo.page_issues(id),
    agent_id        UUID REFERENCES seo.agents(id),
    agent_run_id    UUID REFERENCES seo.agent_runs(id),
    fix_type        VARCHAR(100) NOT NULL,            -- 'auto', 'manual', 'suggested'
    status          seo.fix_status NOT NULL DEFAULT 'pending',
    description     TEXT NOT NULL,
    changes         JSONB NOT NULL DEFAULT '{}',      -- {before: ..., after: ...}
    diff            TEXT,                              -- unified diff of changes
    applied_at      TIMESTAMPTZ,
    applied_by      UUID REFERENCES seo.users(id),
    reverted_at     TIMESTAMPTZ,
    reverted_by     UUID REFERENCES seo.users(id),
    revert_reason   TEXT,
    result_verified BOOLEAN,
    verified_at     TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.page_fixes IS 'Auto-fix and manual fix log for detected page issues.';

CREATE INDEX idx_fix_project ON seo.page_fixes (project_id, created_at DESC);
CREATE INDEX idx_fix_issue ON seo.page_fixes (issue_id);
CREATE INDEX idx_fix_status ON seo.page_fixes (status) WHERE status IN ('pending', 'applied');
CREATE INDEX idx_fix_page ON seo.page_fixes (page_id, created_at DESC);
CREATE INDEX idx_fix_org ON seo.page_fixes (org_id, created_at DESC);

CREATE TRIGGER trg_fix_updated_at
    BEFORE UPDATE ON seo.page_fixes
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_fix_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.page_fixes
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

### 14. keywords

```sql
CREATE TABLE seo.keywords (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    project_id      UUID NOT NULL,
    keyword         VARCHAR(500) NOT NULL,
    keyword_tsv     TSVECTOR GENERATED ALWAYS AS (TO_TSVECTOR('simple', keyword)) STORED,
    status          seo.keyword_status NOT NULL DEFAULT 'tracking',
    group_name      VARCHAR(255),                     -- keyword group / tag
    search_volume   INTEGER,                          -- monthly search volume
    keyword_difficulty SMALLINT,                      -- 0-100
    cpc             NUMERIC(10,4),                    -- cost per click
    intent          VARCHAR(50),                      -- 'informational', 'navigational', 'transactional', 'commercial'
    device          VARCHAR(20) DEFAULT 'desktop',    -- 'desktop', 'mobile', 'all'
    locale          VARCHAR(10) DEFAULT 'en-US',
    current_position INTEGER,
    current_url     TEXT,
    previous_position INTEGER,
    best_position   INTEGER,
    best_position_date DATE,
    position_history JSONB DEFAULT '[]',              -- [{date, position, url}]
    serp_features   TEXT[] DEFAULT '{}',               -- features this keyword triggers
    competitor_positions JSONB DEFAULT '{}',          -- {domain: position}
    tags            TEXT[] DEFAULT '{}',
    notes           TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    first_tracked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    PRIMARY KEY (id, project_id, created_at)
) PARTITION BY RANGE (created_at);

COMMENT ON TABLE  seo.keywords IS 'Tracked keywords with ranking history. Partitioned by created_at.';
COMMENT ON COLUMN seo.keywords.keyword_tsv IS 'Auto-generated tsvector for keyword search.';

CREATE TABLE seo.keywords_default PARTITION OF seo.keywords DEFAULT;

CREATE INDEX idx_kw_project ON seo.keywords (project_id, keyword);
CREATE INDEX idx_kw_org ON seo.keywords (org_id, created_at DESC);
CREATE INDEX idx_kw_status ON seo.keywords (project_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_kw_position ON seo.keywords (project_id, current_position NULLS LAST)
    WHERE status = 'tracking' AND deleted_at IS NULL;
CREATE INDEX idx_kw_volume ON seo.keywords (project_id, search_volume DESC NULLS LAST)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_kw_fts ON seo.keywords USING GIN (keyword_tsv);
CREATE INDEX idx_kw_group ON seo.keywords (project_id, group_name) WHERE deleted_at IS NULL;
CREATE INDEX idx_kw_tags ON seo.keywords USING GIN (tags) WHERE deleted_at IS NULL;
CREATE INDEX idx_kw_intent ON seo.keywords (intent) WHERE deleted_at IS NULL;

CREATE TRIGGER trg_kw_updated_at
    BEFORE UPDATE ON seo.keywords
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 15. serp_snapshots

```sql
CREATE TABLE seo.serp_snapshots (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    project_id      UUID NOT NULL,
    keyword_id      UUID NOT NULL,
    keyword         VARCHAR(500) NOT NULL,             -- denormalized for query speed
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_engine   VARCHAR(50) NOT NULL DEFAULT 'google',  -- 'google', 'bing', 'youtube'
    device          VARCHAR(20) NOT NULL DEFAULT 'desktop',
    locale          VARCHAR(10) NOT NULL DEFAULT 'en-US',
    location        VARCHAR(255),                      -- geo-target (city/state/country)
    results         JSONB NOT NULL DEFAULT '[]',       -- full SERP results
        /* [
             {
               "position": 1,
               "url": "https://...",
               "domain": "example.com",
               "title": "...",
               "snippet": "...",
               "is_organic": true,
               "is_featured_snippet": false,
               "sitelinks": [...]
             }
           ]
        */
    our_position    INTEGER,
    our_url         TEXT,
    total_results   BIGINT,
    serp_features   TEXT[] DEFAULT '{}',               -- detected features
    raw_html        TEXT,                              -- raw SERP HTML (for debugging)
    raw_html_hash   VARCHAR(64),                       -- dedup check
    api_response    JSONB,                             -- raw API response from SERP provider
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, checked_at)
) PARTITION BY RANGE (checked_at);

COMMENT ON TABLE  seo.serp_snapshots IS 'SERP result snapshots. Partitioned monthly by checked_at.';
COMMENT ON COLUMN seo.serp_snapshots.results IS 'Full SERP results as JSONB array.';

CREATE TABLE seo.serp_snapshots_default PARTITION OF seo.serp_snapshots DEFAULT;

CREATE INDEX idx_serp_keyword ON seo.serp_snapshots (keyword_id, checked_at DESC);
CREATE INDEX idx_serp_project ON seo.serp_snapshots (project_id, checked_at DESC);
CREATE INDEX idx_serp_org ON seo.serp_snapshots (org_id, checked_at DESC);
CREATE INDEX idx_serp_position ON seo.serp_snapshots (project_id, our_position)
    WHERE our_position IS NOT NULL;
CREATE INDEX idx_serp_features ON seo.serp_snapshots USING GIN (serp_features);
CREATE INDEX idx_serp_results ON seo.serp_snapshots USING GIN (results);
CREATE INDEX idx_serp_hash ON seo.serp_snapshots (raw_html_hash) WHERE raw_html_hash IS NOT NULL;
```

### 16. serp_features

```sql
CREATE TABLE seo.serp_features (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID NOT NULL REFERENCES seo.projects(id),
    keyword_id      UUID NOT NULL,
    snapshot_id     UUID,
    feature_type    VARCHAR(100) NOT NULL,             -- 'featured_snippet', 'people_also_ask', 'local_pack', 'knowledge_panel', 'image_pack', 'video_carousel', 'top_stories', 'reviews', 'faq', 'how_to', 'sitelinks', 'related_searches'
    position        INTEGER,                          -- position of feature in SERP
    our_url         TEXT,                              -- if we own this feature
    is_ours         BOOLEAN NOT NULL DEFAULT FALSE,
    content         TEXT,                              -- snippet text
    details         JSONB NOT NULL DEFAULT '{}',       -- feature-specific data
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lost_at         TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.serp_features IS 'Tracked SERP features (featured snippets, PAA, etc.).';

CREATE INDEX idx_sf_project ON seo.serp_features (project_id, feature_type) WHERE is_active;
CREATE INDEX idx_sf_keyword ON seo.serp_features (keyword_id);
CREATE INDEX idx_sf_org ON seo.serp_features (org_id, created_at DESC);
CREATE INDEX idx_sf_ours ON seo.serp_features (project_id, feature_type) WHERE is_ours AND is_active;
CREATE INDEX idx_sf_details ON seo.serp_features USING GIN (details);

CREATE TRIGGER trg_sf_updated_at
    BEFORE UPDATE ON seo.serp_features
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 17. backlinks

```sql
CREATE TABLE seo.backlinks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID NOT NULL REFERENCES seo.projects(id),
    source_url      TEXT NOT NULL,                     -- linking page URL
    source_domain   VARCHAR(255) NOT NULL,
    target_url      TEXT NOT NULL,                     -- our page being linked to
    anchor_text     TEXT,
    link_type       VARCHAR(50) NOT NULL DEFAULT 'dofollow',  -- 'dofollow', 'nofollow', 'sponsored', 'ugc'
    link_position   VARCHAR(50),                       -- 'body', 'header', 'footer', 'sidebar', 'nav'
    is_redirect     BOOLEAN DEFAULT FALSE,
    redirect_url    TEXT,
    source_dr       SMALLINT,                          -- domain rating (0-100)
    source_traffic  INTEGER,                           -- estimated monthly traffic
    source_title    TEXT,
    source_status   SMALLINT,                          -- HTTP status of source page
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ,
    lost_at         TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    source_data     JSONB DEFAULT '{}',                -- additional metrics from provider
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.backlinks IS 'Inbound backlinks tracked per project.';

CREATE INDEX idx_bl_project ON seo.backlinks (project_id, is_active, source_dr DESC NULLS LAST);
CREATE INDEX idx_bl_org ON seo.backlinks (org_id, created_at DESC);
CREATE INDEX idx_bl_domain ON seo.backlinks (source_domain);
CREATE INDEX idx_bl_target ON seo.backlinks (project_id, target_url);
CREATE INDEX idx_bl_active ON seo.backlinks (project_id, first_seen_at DESC) WHERE is_active;
CREATE INDEX idx_bl_lost ON seo.backlinks (project_id, lost_at DESC) WHERE lost_at IS NOT NULL;
CREATE INDEX idx_bl_dr ON seo.backlinks (project_id, source_dr DESC NULLS LAST) WHERE is_active;
CREATE INDEX idx_bl_anchor ON seo.backlinks USING GIN (TO_TSVECTOR('simple', COALESCE(anchor_text, '')));

CREATE TRIGGER trg_bl_updated_at
    BEFORE UPDATE ON seo.backlinks
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 18. backlink_campaigns

```sql
CREATE TABLE seo.backlink_campaigns (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID NOT NULL REFERENCES seo.projects(id),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    status          seo.campaign_status NOT NULL DEFAULT 'draft',
    target_pages    TEXT[] NOT NULL DEFAULT '{}',      -- our pages to build links to
    target_keywords TEXT[] DEFAULT '{}',
    strategy        VARCHAR(100),                      -- 'guest_post', 'resource_page', 'broken_link', 'skyscraper', 'custom'
    settings        JSONB NOT NULL DEFAULT '{}',
        /* {
             "min_domain_rating": 30,
             "max_outbound_links": 50,
             "required_keywords": [],
             "excluded_domains": [],
             "email_template_id": "...",
             "follow_up_days": [3, 7, 14]
           }
        */
    stats           JSONB NOT NULL DEFAULT '{}',
        /* {
             "contacts_identified": 150,
             "emails_sent": 100,
             "responses": 25,
             "links_acquired": 8,
             "average_dr": 45
           }
        */
    start_date      DATE,
    end_date        DATE,
    owner_id        UUID REFERENCES seo.users(id),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE  seo.backlink_campaigns IS 'Outreach campaigns for link building.';

CREATE INDEX idx_bc_project ON seo.backlink_campaigns (project_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_bc_org ON seo.backlink_campaigns (org_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_bc_status ON seo.backlink_campaigns (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_bc_owner ON seo.backlink_campaigns (owner_id) WHERE deleted_at IS NULL;

CREATE TRIGGER trg_bc_updated_at
    BEFORE UPDATE ON seo.backlink_campaigns
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_bc_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.backlink_campaigns
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

### 19. campaign_contacts

```sql
CREATE TABLE seo.campaign_contacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    campaign_id     UUID NOT NULL REFERENCES seo.backlink_campaigns(id),
    name            VARCHAR(255),
    email           VARCHAR(255) NOT NULL,
    domain          VARCHAR(255),
    website_url     TEXT,
    dr              SMALLINT,                          -- domain rating
    status          seo.contact_status NOT NULL DEFAULT 'identified',
    source          VARCHAR(100),                      -- 'hunter.io', 'manual', 'scraped', 'ahrens'
    outreach_stage  SMALLINT NOT NULL DEFAULT 0,       -- 0=not contacted, 1=first email, 2=follow-up 1, etc.
    response_at     TIMESTAMPTZ,
    notes           TEXT,
    custom_fields   JSONB DEFAULT '{}',
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (campaign_id, email)
);

COMMENT ON TABLE  seo.campaign_contacts IS 'Outreach contacts per link-building campaign.';

CREATE INDEX idx_cc_campaign ON seo.campaign_contacts (campaign_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_cc_email ON seo.campaign_contacts (email);
CREATE INDEX idx_cc_domain ON seo.campaign_contacts (domain);
CREATE INDEX idx_cc_org ON seo.campaign_contacts (org_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_cc_stage ON seo.campaign_contacts (campaign_id, outreach_stage)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_cc_updated_at
    BEFORE UPDATE ON seo.campaign_contacts
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 20. campaign_messages

```sql
CREATE TABLE seo.campaign_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    campaign_id     UUID NOT NULL REFERENCES seo.backlink_campaigns(id),
    contact_id      UUID NOT NULL REFERENCES seo.campaign_contacts(id),
    message_type    VARCHAR(50) NOT NULL DEFAULT 'initial',  -- 'initial', 'follow_up', 'reply'
    sequence_number SMALLINT NOT NULL DEFAULT 1,
    subject         VARCHAR(500) NOT NULL,
    body_html       TEXT NOT NULL,
    body_text       TEXT NOT NULL,
    status          seo.message_status NOT NULL DEFAULT 'queued',
    sent_at         TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    opened_at       TIMESTAMPTZ,
    clicked_at      TIMESTAMPTZ,
    replied_at      TIMESTAMPTZ,
    bounced_at      TIMESTAMPTZ,
    bounce_reason   TEXT,
    tracking_id     VARCHAR(100) UNIQUE,               -- for open/click tracking
    email_provider  VARCHAR(50),                       -- 'sendgrid', 'ses', 'smtp'
    email_message_id VARCHAR(255),                     -- provider message ID
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.campaign_messages IS 'Outreach emails sent per contact in link-building campaigns.';

CREATE INDEX idx_cm_campaign ON seo.campaign_messages (campaign_id, created_at DESC);
CREATE INDEX idx_cm_contact ON seo.campaign_messages (contact_id, sequence_number);
CREATE INDEX idx_cm_status ON seo.campaign_messages (status) WHERE status IN ('queued', 'sent');
CREATE INDEX idx_cm_tracking ON seo.campaign_messages (tracking_id) WHERE tracking_id IS NOT NULL;
CREATE INDEX idx_cm_org ON seo.campaign_messages (org_id, created_at DESC);

CREATE TRIGGER trg_cm_updated_at
    BEFORE UPDATE ON seo.campaign_messages
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 21. campaign_events

```sql
CREATE TABLE seo.campaign_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    campaign_id     UUID NOT NULL REFERENCES seo.backlink_campaigns(id),
    contact_id      UUID REFERENCES seo.campaign_contacts(id),
    message_id      UUID REFERENCES seo.campaign_messages(id),
    event_type      VARCHAR(100) NOT NULL,             -- 'contact_added', 'email_sent', 'email_opened', 'email_replied', 'link_acquired', 'link_lost', 'campaign_paused', etc.
    description     TEXT,
    data            JSONB DEFAULT '{}',
    actor_id        UUID REFERENCES seo.users(id),     -- who triggered (null for system)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.campaign_events IS 'Status change events for outreach campaigns.';

CREATE INDEX idx_cev_campaign ON seo.campaign_events (campaign_id, created_at DESC);
CREATE INDEX idx_cev_contact ON seo.campaign_events (contact_id) WHERE contact_id IS NOT NULL;
CREATE INDEX idx_cev_type ON seo.campaign_events (event_type, created_at DESC);
CREATE INDEX idx_cev_org ON seo.campaign_events (org_id, created_at DESC);
```

---

## HARO Tables

### 22. haro_queries

```sql
CREATE TABLE seo.haro_queries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID REFERENCES seo.projects(id),
    source          VARCHAR(100) NOT NULL DEFAULT 'haro',  -- 'haro', 'sourcebottle', 'quoted', 'custom'
    source_id       VARCHAR(255),                     -- original query ID from source
    query_text      TEXT NOT NULL,
    query_tsv       TSVECTOR GENERATED ALWAYS AS (TO_TSVECTOR('english', query_text)) STORED,
    category        VARCHAR(255),
    media_outlet    VARCHAR(255),
    journalist_name VARCHAR(255),
    journalist_email VARCHAR(255),
    deadline        TIMESTAMPTZ,
    requirements    TEXT,
    status          seo.haro_status NOT NULL DEFAULT 'new',
    relevance_score NUMERIC(5,2),                     -- AI-calculated relevance 0-100
    match_reasons   JSONB DEFAULT '[]',               -- why this matches our expertise
    raw_data        JSONB DEFAULT '{}',               -- original email/API data
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE  seo.haro_queries IS 'Parsed HARO (Help A Reporter Out) and similar source queries.';

CREATE INDEX idx_haro_org ON seo.haro_queries (org_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_haro_status ON seo.haro_queries (status, deadline NULLS LAST)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_haro_deadline ON seo.haro_queries (deadline)
    WHERE status IN ('new', 'matched') AND deleted_at IS NULL;
CREATE INDEX idx_haro_fts ON seo.haro_queries USING GIN (query_tsv);
CREATE INDEX idx_haro_relevance ON seo.haro_queries (org_id, relevance_score DESC NULLS LAST)
    WHERE status = 'new' AND deleted_at IS NULL;
CREATE INDEX idx_haro_source ON seo.haro_queries (source, source_id);

CREATE TRIGGER trg_haro_updated_at
    BEFORE UPDATE ON seo.haro_queries
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 23. haro_responses

```sql
CREATE TABLE seo.haro_responses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    query_id        UUID NOT NULL REFERENCES seo.haro_queries(id),
    author_id       UUID REFERENCES seo.users(id),     -- who approved/submitted
    expert_name     VARCHAR(255) NOT NULL,
    expert_title    VARCHAR(255),
    expert_bio      TEXT,
    response_text   TEXT NOT NULL,
    response_tsv    TSVECTOR GENERATED ALWAYS AS (TO_TSVECTOR('english', response_text)) STORED,
    tone            VARCHAR(50) DEFAULT 'professional', -- 'professional', 'casual', 'authoritative'
    key_points      TEXT[] DEFAULT '{}',
    ai_model        VARCHAR(100),                      -- which model generated this
    ai_prompt       TEXT,                              -- prompt used
    version         SMALLINT NOT NULL DEFAULT 1,
    parent_version  UUID,                              -- previous version for revision chain
    quality_score   NUMERIC(5,2),                      -- AI quality assessment
    is_approved     BOOLEAN DEFAULT FALSE,
    approved_at     TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.haro_responses IS 'AI-generated response drafts for HARO queries.';

CREATE INDEX idx_hr_query ON seo.haro_responses (query_id, version DESC);
CREATE INDEX idx_hr_org ON seo.haro_responses (org_id, created_at DESC);
CREATE INDEX idx_hr_approved ON seo.haro_responses (query_id) WHERE is_approved;
CREATE INDEX idx_hr_fts ON seo.haro_responses USING GIN (response_tsv);

CREATE TRIGGER trg_hr_updated_at
    BEFORE UPDATE ON seo.haro_responses
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 24. haro_submissions

```sql
CREATE TABLE seo.haro_submissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    query_id        UUID NOT NULL REFERENCES seo.haro_queries(id),
    response_id     UUID NOT NULL REFERENCES seo.haro_responses(id),
    submitted_by    UUID REFERENCES seo.users(id),
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    method          VARCHAR(50) NOT NULL DEFAULT 'email',  -- 'email', 'api', 'manual'
    email_sent_to   VARCHAR(255),
    email_message_id VARCHAR(255),                     -- provider message ID
    status          VARCHAR(50) NOT NULL DEFAULT 'sent', -- 'sent', 'delivered', 'accepted', 'declined', 'expired'
    journalist_response TEXT,
    responded_at    TIMESTAMPTZ,
    published_url   TEXT,                              -- link to published article
    published_at    TIMESTAMPTZ,
    published_dr    SMALLINT,                          -- DR of published article
    is_verified     BOOLEAN DEFAULT FALSE,
    backlink_acquired BOOLEAN DEFAULT FALSE,
    follow_up_sent  BOOLEAN DEFAULT FALSE,
    follow_up_at    TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.haro_submissions IS 'Submitted HARO responses with tracking for publication.';

CREATE INDEX idx_hs_query ON seo.haro_submissions (query_id, submitted_at DESC);
CREATE INDEX idx_hs_org ON seo.haro_submissions (org_id, submitted_at DESC);
CREATE INDEX idx_hs_status ON seo.haro_submissions (status);
CREATE INDEX idx_hs_published ON seo.haro_submissions (published_url) WHERE published_url IS NOT NULL;
CREATE INDEX idx_hs_backlink ON seo.haro_submissions (org_id)
    WHERE backlink_acquired;

CREATE TRIGGER trg_hs_updated_at
    BEFORE UPDATE ON seo.haro_submissions
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

---

## Content Tables

### 25. content_briefs

```sql
CREATE TABLE seo.content_briefs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID NOT NULL REFERENCES seo.projects(id),
    title           VARCHAR(500) NOT NULL,
    target_keyword  VARCHAR(500) NOT NULL,
    secondary_keywords TEXT[] DEFAULT '{}',
    target_audience TEXT,
    content_type    VARCHAR(100) NOT NULL,             -- 'blog_post', 'landing_page', 'pillar_page', 'guide', 'case_study', 'product_page'
    target_word_count INTEGER,
    tone            VARCHAR(50) DEFAULT 'professional',
    outline         JSONB NOT NULL DEFAULT '[]',       -- [{heading, subheadings, key_points}]
    competitor_analysis JSONB DEFAULT '{}',            -- top SERP analysis
    suggested_title_tags JSONB DEFAULT '[]',
    suggested_meta_descriptions JSONB DEFAULT '[]',
    internal_linking_suggestions JSONB DEFAULT '[]',
    external_sources JSONB DEFAULT '[]',
    seo_checklist   JSONB DEFAULT '[]',                -- [{item, checked}]
    brief_tsv       TSVECTOR GENERATED ALWAYS AS (
                        TO_TSVECTOR('english', COALESCE(title, '') || ' ' || COALESCE(target_keyword, ''))
                    ) STORED,
    status          seo.content_status NOT NULL DEFAULT 'draft',
    assigned_to     UUID REFERENCES seo.users(id),
    due_date        DATE,
    ai_model        VARCHAR(100),
    ai_prompt       TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE  seo.content_briefs IS 'AI-generated content briefs for SEO-optimized content.';

CREATE INDEX idx_cb_project ON seo.content_briefs (project_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_cb_org ON seo.content_briefs (org_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_cb_keyword ON seo.content_briefs (project_id, target_keyword);
CREATE INDEX idx_cb_assigned ON seo.content_briefs (assigned_to) WHERE assigned_to IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_cb_fts ON seo.content_briefs USING GIN (brief_tsv);

CREATE TRIGGER trg_cb_updated_at
    BEFORE UPDATE ON seo.content_briefs
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_cb_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.content_briefs
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

### 26. content_drafts

```sql
CREATE TABLE seo.content_drafts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    brief_id        UUID REFERENCES seo.content_briefs(id),
    project_id      UUID NOT NULL REFERENCES seo.projects(id),
    title           VARCHAR(500) NOT NULL,
    slug            VARCHAR(255),
    content_html    TEXT NOT NULL,
    content_markdown TEXT NOT NULL,
    content_tsv     TSVECTOR GENERATED ALWAYS AS (TO_TSVECTOR('english', COALESCE(content_markdown, ''))) STORED,
    meta_title      VARCHAR(255),
    meta_description VARCHAR(500),
    word_count      INTEGER,
    reading_time_ms INTEGER,
    readability_score NUMERIC(5,2),                    -- Flesch-Kincaid or similar
    seo_score       NUMERIC(5,2),                      -- AI SEO quality score
    seo_analysis    JSONB DEFAULT '{}',                -- detailed SEO analysis
        /* {
             "keyword_density": 2.1,
             "heading_structure": "good",
             "internal_links": 5,
             "external_links": 3,
             "images_missing_alt": 0,
             "readability": "grade_8",
             "pass": true,
             "issues": []
           }
        */
    version         SMALLINT NOT NULL DEFAULT 1,
    parent_version  UUID,
    status          seo.content_status NOT NULL DEFAULT 'draft',
    ai_model        VARCHAR(100),
    ai_prompt       TEXT,
    ai_temperature  NUMERIC(3,2),
    reviewed_by     UUID REFERENCES seo.users(id),
    reviewed_at     TIMESTAMPTZ,
    review_notes    TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE  seo.content_drafts IS 'AI-generated content drafts with versioning and SEO analysis.';

CREATE INDEX idx_cd_brief ON seo.content_drafts (brief_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_cd_project ON seo.content_drafts (project_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_cd_org ON seo.content_drafts (org_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_cd_status ON seo.content_drafts (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_cd_fts ON seo.content_drafts USING GIN (content_tsv);
CREATE INDEX idx_cd_slug ON seo.content_drafts (project_id, slug) WHERE slug IS NOT NULL AND deleted_at IS NULL;

CREATE TRIGGER trg_cd_updated_at
    BEFORE UPDATE ON seo.content_drafts
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 27. content_published

```sql
CREATE TABLE seo.content_published (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID NOT NULL REFERENCES seo.projects(id),
    draft_id        UUID REFERENCES seo.content_drafts(id),
    brief_id        UUID REFERENCES seo.content_briefs(id),
    title           VARCHAR(500) NOT NULL,
    slug            VARCHAR(255) NOT NULL,
    url             TEXT NOT NULL,
    content_html    TEXT NOT NULL,
    content_markdown TEXT NOT NULL,
    content_tsv     TSVECTOR GENERATED ALWAYS AS (TO_TSVECTOR('english', COALESCE(content_markdown, ''))) STORED,
    meta_title      VARCHAR(255),
    meta_description VARCHAR(500),
    canonical_url   TEXT,
    word_count      INTEGER,
    published_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_by    UUID REFERENCES seo.users(id),
    cms_type        VARCHAR(50),                       -- 'wordpress', 'shopify', 'custom', 'manual'
    cms_post_id     VARCHAR(255),                      -- ID in the CMS
    cms_permalink   TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'published', -- 'published', 'updated', 'unpublished', 'redirected'
    last_updated_at TIMESTAMPTZ,
    last_updated_by UUID REFERENCES seo.users(id),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE  seo.content_published IS 'Published content tracked for performance.';

CREATE INDEX idx_cp_project ON seo.content_published (project_id, published_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_cp_org ON seo.content_published (org_id, published_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_cp_url ON seo.content_published (project_id, url);
CREATE INDEX idx_cp_slug ON seo.content_published (project_id, slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_cp_draft ON seo.content_published (draft_id);
CREATE INDEX idx_cp_cms ON seo.content_published (cms_type, cms_post_id) WHERE cms_post_id IS NOT NULL;
CREATE INDEX idx_cp_fts ON seo.content_published USING GIN (content_tsv);

CREATE TRIGGER trg_cp_updated_at
    BEFORE UPDATE ON seo.content_published
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_cp_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.content_published
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

### 28. content_performance

```sql
CREATE TABLE seo.content_performance (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID NOT NULL REFERENCES seo.projects(id),
    content_id      UUID NOT NULL,                     -- FK to content_published
    date            DATE NOT NULL,
    impressions     INTEGER DEFAULT 0,
    clicks          INTEGER DEFAULT 0,
    avg_position    NUMERIC(8,2),
    ctr             NUMERIC(5,4),                      -- click-through rate
    sessions        INTEGER DEFAULT 0,                 -- from GA4
    users           INTEGER DEFAULT 0,
    new_users       INTEGER DEFAULT 0,
    bounce_rate     NUMERIC(5,4),
    avg_session_duration NUMERIC(10,2),
    page_views      INTEGER DEFAULT 0,
    conversions     INTEGER DEFAULT 0,
    conversion_rate NUMERIC(5,4),
    revenue         NUMERIC(12,2),
    backlinks_gained INTEGER DEFAULT 0,
    keywords_ranking INTEGER DEFAULT 0,                -- number of keywords this page ranks for
    custom_metrics  JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (content_id, date)
);

COMMENT ON TABLE  seo.content_performance IS 'Daily performance metrics per published content.';

CREATE INDEX idx_cperf_content ON seo.content_performance (content_id, date DESC);
CREATE INDEX idx_cperf_project ON seo.content_performance (project_id, date DESC);
CREATE INDEX idx_cperf_org ON seo.content_performance (org_id, date DESC);
CREATE INDEX idx_cperf_date ON seo.content_performance (date DESC);
CREATE INDEX idx_cperf_custom ON seo.content_performance USING GIN (custom_metrics);

CREATE TRIGGER trg_cperf_updated_at
    BEFORE UPDATE ON seo.content_performance
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

---

## Analytics Tables

### 29. analytics_snapshots

```sql
CREATE TABLE seo.analytics_snapshots (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    project_id      UUID NOT NULL,
    source          VARCHAR(50) NOT NULL,              -- 'ga4', 'plausible', 'matomo', 'custom'
    date            DATE NOT NULL,
    page_url        TEXT,
    page_path       VARCHAR(2000),
    channel_group   VARCHAR(100),                      -- 'Organic Search', 'Direct', 'Social', etc.
    source_medium   VARCHAR(255),                      -- 'google / organic'
    country         VARCHAR(5),
    device_category VARCHAR(50),                       -- 'desktop', 'mobile', 'tablet'
    browser         VARCHAR(100),
    operating_system VARCHAR(100),
    sessions        INTEGER DEFAULT 0,
    users           INTEGER DEFAULT 0,
    new_users       INTEGER DEFAULT 0,
    page_views      INTEGER DEFAULT 0,
    unique_page_views INTEGER DEFAULT 0,
    avg_session_duration NUMERIC(10,2),
    bounce_rate     NUMERIC(5,4),
    exit_rate       NUMERIC(5,4),
    conversions     INTEGER DEFAULT 0,
    conversion_rate NUMERIC(5,4),
    revenue         NUMERIC(12,2),
    transactions    INTEGER DEFAULT 0,
    custom_dimensions JSONB DEFAULT '{}',
    custom_metrics  JSONB DEFAULT '{}',
    raw_data        JSONB DEFAULT '{}',                -- raw API response
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, date)
) PARTITION BY RANGE (date);

COMMENT ON TABLE  seo.analytics_snapshots IS 'GA4/analytics data snapshots. Partitioned monthly by date.';

CREATE TABLE seo.analytics_snapshots_default PARTITION OF seo.analytics_snapshots DEFAULT;

CREATE INDEX idx_asnap_project ON seo.analytics_snapshots (project_id, date DESC);
CREATE INDEX idx_asnap_org ON seo.analytics_snapshots (org_id, date DESC);
CREATE INDEX idx_asnap_page ON seo.analytics_snapshots (project_id, page_path, date DESC);
CREATE INDEX idx_asnap_channel ON seo.analytics_snapshots (project_id, channel_group, date DESC);
CREATE INDEX idx_asnap_source ON seo.analytics_snapshots (source, date DESC);
CREATE INDEX idx_asnap_custom ON seo.analytics_snapshots USING GIN (custom_metrics);
```

### 30. search_analytics

```sql
CREATE TABLE seo.search_analytics (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    project_id      UUID NOT NULL,
    source          VARCHAR(50) NOT NULL DEFAULT 'gsc',  -- 'gsc', 'bing_webmaster'
    oauth_connection_id UUID REFERENCES seo.oauth_connections(id),
    date            DATE NOT NULL,
    query           VARCHAR(500),
    page_url        TEXT,
    page_path       VARCHAR(2000),
    country         VARCHAR(5),
    device          VARCHAR(50),                       -- 'desktop', 'mobile', 'tablet'
    search_appearance VARCHAR(100),                    -- 'web', 'image', 'video'
    impressions     INTEGER DEFAULT 0,
    clicks          INTEGER DEFAULT 0,
    ctr             NUMERIC(5,4),
    avg_position    NUMERIC(8,2),
    position_bucket VARCHAR(20),                       -- '1-3', '4-10', '11-20', '21-50', '51-100'
    raw_data        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, date)
) PARTITION BY RANGE (date);

COMMENT ON TABLE  seo.search_analytics IS 'Google Search Console / Bing Webmaster data. Partitioned monthly.';

CREATE TABLE seo.search_analytics_default PARTITION OF seo.search_analytics DEFAULT;

CREATE INDEX idx_san_project ON seo.search_analytics (project_id, date DESC);
CREATE INDEX idx_san_org ON seo.search_analytics (org_id, date DESC);
CREATE INDEX idx_san_query ON seo.search_analytics (project_id, query, date DESC)
    WHERE query IS NOT NULL;
CREATE INDEX idx_san_page ON seo.search_analytics (project_id, page_path, date DESC)
    WHERE page_path IS NOT NULL;
CREATE INDEX idx_san_device ON seo.search_analytics (project_id, device, date DESC);
CREATE INDEX idx_san_position ON seo.search_analytics (project_id, avg_position NULLS LAST, date DESC);
CREATE INDEX idx_san_country ON seo.search_analytics (project_id, country, date DESC)
    WHERE country IS NOT NULL;
```

### 31. anomalies

```sql
CREATE TABLE seo.anomalies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID NOT NULL REFERENCES seo.projects(id),
    anomaly_type    seo.anomaly_type NOT NULL,
    severity        seo.issue_severity NOT NULL,
    title           VARCHAR(500) NOT NULL,
    description     TEXT NOT NULL,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_name     VARCHAR(100) NOT NULL,             -- 'organic_sessions', 'avg_position', 'crawl_errors', etc.
    metric_value    NUMERIC(15,4),
    expected_value  NUMERIC(15,4),
    deviation_pct   NUMERIC(8,4),                      -- percentage deviation from expected
    deviation_sigma NUMERIC(5,2),                      -- standard deviations
    date_range_start DATE NOT NULL,
    date_range_end  DATE NOT NULL,
    comparison_type VARCHAR(50) DEFAULT 'wow',         -- 'wow' (week-over-week), 'mom', 'yoy', 'custom'
    affected_pages  TEXT[] DEFAULT '{}',
    affected_keywords TEXT[] DEFAULT '{}',
    root_cause      TEXT,                              -- AI-generated root cause analysis
    recommendation  TEXT,                              -- AI-generated recommendation
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by UUID REFERENCES seo.users(id),
    acknowledged_at TIMESTAMPTZ,
    is_resolved     BOOLEAN DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    resolution      TEXT,
    data            JSONB NOT NULL DEFAULT '{}',       -- supporting data/charts
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.anomalies IS 'Detected anomalies in SEO metrics (traffic drops, ranking changes, etc.).';

CREATE INDEX idx_anom_project ON seo.anomalies (project_id, detected_at DESC);
CREATE INDEX idx_anom_org ON seo.anomalies (org_id, detected_at DESC);
CREATE INDEX idx_anom_type ON seo.anomalies (anomaly_type, detected_at DESC);
CREATE INDEX idx_anom_severity ON seo.anomalies (severity) WHERE NOT is_resolved;
CREATE INDEX idx_anom_unresolved ON seo.anomalies (project_id, detected_at DESC)
    WHERE NOT is_resolved;
CREATE INDEX idx_anom_unack ON seo.anomalies (project_id, severity, detected_at DESC)
    WHERE NOT is_acknowledged;
CREATE INDEX idx_anom_data ON seo.anomalies USING GIN (data);

CREATE TRIGGER trg_anom_updated_at
    BEFORE UPDATE ON seo.anomalies
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

### 32. reports

```sql
CREATE TABLE seo.reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES seo.organizations(id),
    project_id      UUID REFERENCES seo.projects(id),
    name            VARCHAR(255) NOT NULL,
    type            VARCHAR(100) NOT NULL,             -- 'weekly_seo', 'monthly_performance', 'site_audit', 'keyword_rankings', 'backlink_profile', 'content_performance', 'executive_summary', 'custom'
    format          seo.report_format NOT NULL DEFAULT 'pdf',
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'pending', 'generating', 'completed', 'failed'
    config          JSONB NOT NULL DEFAULT '{}',
        /* {
             "date_range": { "start": "2025-06-01", "end": "2025-06-30" },
             "sections": ["overview", "keywords", "content", "backlinks", "technical"],
             "comparison_period": "previous_month",
             "branding": true,
             "charts": true,
             "executive_summary": true,
             "auto_send": true,
             "recipients": ["client@example.com"]
           }
        */
    generated_by    UUID REFERENCES seo.users(id),     -- NULL for auto-generated
    agent_id        UUID REFERENCES seo.agents(id),    -- NULL for manual
    file_url        TEXT,                              -- S3/GCS URL
    file_size_bytes BIGINT,
    page_count      INTEGER,
    scheduled_cron  VARCHAR(100),                      -- for recurring reports
    next_send_at    TIMESTAMPTZ,
    last_sent_at    TIMESTAMPTZ,
    error_message   TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE  seo.reports IS 'Generated and scheduled reports.';

CREATE INDEX idx_report_project ON seo.reports (project_id, type, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_report_org ON seo.reports (org_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_report_status ON seo.reports (status) WHERE status IN ('pending', 'generating');
CREATE INDEX idx_report_scheduled ON seo.reports (next_send_at)
    WHERE scheduled_cron IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_report_type ON seo.reports (type, created_at DESC) WHERE deleted_at IS NULL;

CREATE TRIGGER trg_report_updated_at
    BEFORE UPDATE ON seo.reports
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();

CREATE TRIGGER trg_report_audit
    AFTER INSERT OR UPDATE OR DELETE ON seo.reports
    FOR EACH ROW EXECUTE FUNCTION audit.log_change();
```

---

## Security Tables

### 33. audit_logs

```sql
CREATE TABLE audit.audit_logs (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    org_id          UUID,
    user_id         UUID,
    table_schema    VARCHAR(100) NOT NULL,
    table_name      VARCHAR(100) NOT NULL,
    record_id       UUID,
    action          VARCHAR(10) NOT NULL,              -- INSERT, UPDATE, DELETE
    old_data        JSONB,
    new_data        JSONB,
    diff            JSONB,                             -- computed diff (filled by app or trigger)
    ip_address      INET,
    user_agent      TEXT,
    session_id      VARCHAR(255),
    request_id      VARCHAR(255),                      -- for distributed tracing
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

COMMENT ON TABLE  audit.audit_logs IS 'Immutable audit trail for all data changes. Partitioned monthly.';

CREATE TABLE audit.audit_logs_default PARTITION OF audit.audit_logs DEFAULT;

CREATE INDEX idx_audit_org ON audit.audit_logs (org_id, created_at DESC);
CREATE INDEX idx_audit_user ON audit.audit_logs (user_id, created_at DESC)
    WHERE user_id IS NOT NULL;
CREATE INDEX idx_audit_table ON audit.audit_logs (table_schema, table_name, created_at DESC);
CREATE INDEX idx_audit_record ON audit.audit_logs (table_name, record_id, created_at DESC)
    WHERE record_id IS NOT NULL;
CREATE INDEX idx_audit_action ON audit.audit_logs (action, created_at DESC);
CREATE INDEX idx_audit_request ON audit.audit_logs (request_id)
    WHERE request_id IS NOT NULL;
CREATE INDEX idx_audit_new_data ON audit.audit_logs USING GIN (new_data);
```

### 34. security_events

```sql
CREATE TABLE seo.security_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID,
    user_id         UUID,
    event_type      VARCHAR(100) NOT NULL,             -- 'login_success', 'login_failed', 'logout', 'password_change', 'mfa_enabled', 'mfa_disabled', 'api_key_created', 'api_key_revoked', 'role_changed', 'suspicious_activity', 'rate_limit_exceeded', 'ip_blocked'
    severity        seo.event_severity NOT NULL DEFAULT 'info',
    description     TEXT NOT NULL,
    ip_address      INET,
    user_agent      TEXT,
    geo_location    JSONB,                             -- {country, city, lat, lon}
    session_id      VARCHAR(255),
    request_id      VARCHAR(255),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.security_events IS 'Authentication and security-related events.';

CREATE INDEX idx_sec_event_org ON seo.security_events (org_id, created_at DESC);
CREATE INDEX idx_sec_event_user ON seo.security_events (user_id, created_at DESC)
    WHERE user_id IS NOT NULL;
CREATE INDEX idx_sec_event_type ON seo.security_events (event_type, created_at DESC);
CREATE INDEX idx_sec_event_ip ON seo.security_events (ip_address, created_at DESC)
    WHERE ip_address IS NOT NULL;
CREATE INDEX idx_sec_event_severity ON seo.security_events (severity, created_at DESC)
    WHERE severity IN ('warning', 'error', 'critical');
CREATE INDEX idx_sec_event_suspicious ON seo.security_events (org_id, event_type, created_at DESC)
    WHERE event_type IN ('suspicious_activity', 'rate_limit_exceeded', 'ip_blocked');
```

### 35. rate_limit_logs

```sql
CREATE TABLE seo.rate_limit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID,
    user_id         UUID,
    api_key_id      UUID,
    ip_address      INET NOT NULL,
    endpoint        VARCHAR(500) NOT NULL,
    method          VARCHAR(10) NOT NULL,              -- GET, POST, etc.
    limit_type      VARCHAR(50) NOT NULL,              -- 'api', 'login', 'password_reset', 'export'
    limit_value     INTEGER NOT NULL,                  -- max allowed
    current_count   INTEGER NOT NULL,                  -- current usage
    window_seconds  INTEGER NOT NULL,                  -- time window
    was_blocked     BOOLEAN NOT NULL DEFAULT FALSE,
    response_code   SMALLINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

COMMENT ON TABLE  seo.rate_limit_logs IS 'Rate limiting events. Partitioned monthly.';

CREATE TABLE seo.rate_limit_logs_default PARTITION OF seo.rate_limit_logs DEFAULT;

CREATE INDEX idx_rl_ip ON seo.rate_limit_logs (ip_address, created_at DESC);
CREATE INDEX idx_rl_org ON seo.rate_limit_logs (org_id, created_at DESC) WHERE org_id IS NOT NULL;
CREATE INDEX idx_rl_user ON seo.rate_limit_logs (user_id, created_at DESC) WHERE user_id IS NOT NULL;
CREATE INDEX idx_rl_endpoint ON seo.rate_limit_logs (endpoint, created_at DESC);
CREATE INDEX idx_rl_blocked ON seo.rate_limit_logs (ip_address, created_at DESC) WHERE was_blocked;
```

### 36. ip_blocklist

```sql
CREATE TABLE seo.ip_blocklist (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID,                              -- NULL = global block
    ip_address      INET NOT NULL,
    ip_range        CIDR,                              -- for blocking ranges
    reason          TEXT NOT NULL,
    block_type      VARCHAR(50) NOT NULL DEFAULT 'manual',  -- 'manual', 'auto', 'rate_limit', 'abuse'
    expires_at      TIMESTAMPTZ,                       -- NULL = permanent
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    auto_blocked_count INTEGER NOT NULL DEFAULT 0,     -- how many times auto-triggered
    created_by      UUID REFERENCES seo.users(id),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  seo.ip_blocklist IS 'Blocked IPs/ranges for abuse prevention.';

CREATE UNIQUE INDEX idx_ipblock_ip ON seo.ip_blocklist (ip_address, org_id)
    WHERE is_active;
CREATE INDEX idx_ipblock_range ON seo.ip_blocklist (ip_range)
    WHERE is_active AND ip_range IS NOT NULL;
CREATE INDEX idx_ipblock_active ON seo.ip_blocklist (expires_at)
    WHERE is_active;
CREATE INDEX idx_ipblock_org ON seo.ip_blocklist (org_id) WHERE is_active AND org_id IS NOT NULL;

CREATE TRIGGER trg_ipblock_updated_at
    BEFORE UPDATE ON seo.ip_blocklist
    FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at();
```

---

## Row-Level Security Policies

```sql
-- ============================================================
-- ENABLE RLS ON ALL TENANT-SCOPED TABLES
-- ============================================================
ALTER TABLE seo.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.oauth_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.agent_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.agent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.page_issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.page_fixes ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.keywords ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.serp_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.serp_features ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.backlinks ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.backlink_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.campaign_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.campaign_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.campaign_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.haro_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.haro_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.haro_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.content_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.content_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.content_published ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.content_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.analytics_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.search_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.anomalies ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.security_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.rate_limit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo.ip_blocklist ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit.audit_logs ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- CREATE RLS POLICIES (using a helper function)
-- ============================================================

-- The application sets these at connection time:
--   SET LOCAL app.current_org_id = '<user's org UUID>';
--   SET LOCAL app.current_user_id = '<user's UUID>';

-- Generic policy: user can only see rows where org_id matches their session org
-- We create a reusable policy function:
CREATE OR REPLACE FUNCTION seo.tenant_isolation(org_id_column UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN org_id_column = current_setting('app.current_org_id', true)::UUID;
END;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Apply tenant isolation policy to every org-scoped table
-- (One policy per table; using 'tenant_isolation' check)

DO $$
DECLARE
    tbl TEXT;
    tables TEXT[] := ARRAY[
        'seo.users', 'seo.roles', 'seo.permissions',
        'seo.projects', 'seo.api_keys', 'seo.oauth_connections',
        'seo.agents', 'seo.agent_runs', 'seo.agent_tasks', 'seo.agent_events',
        'seo.pages', 'seo.page_issues', 'seo.page_fixes',
        'seo.keywords', 'seo.serp_snapshots', 'seo.serp_features',
        'seo.backlinks', 'seo.backlink_campaigns',
        'seo.campaign_contacts', 'seo.campaign_messages', 'seo.campaign_events',
        'seo.haro_queries', 'seo.haro_responses', 'seo.haro_submissions',
        'seo.content_briefs', 'seo.content_drafts', 'seo.content_published',
        'seo.content_performance',
        'seo.analytics_snapshots', 'seo.search_analytics',
        'seo.anomalies', 'seo.reports',
        'seo.security_events', 'seo.rate_limit_logs', 'seo.ip_blocklist',
        'audit.audit_logs'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables LOOP
        EXECUTE FORMAT(
            'CREATE POLICY tenant_isolation ON %I USING (seo.tenant_isolation(org_id))',
            tbl
        );
    END LOOP;
END $$;

-- Special policy for organizations table (users see only their own org)
CREATE POLICY org_isolation ON seo.organizations
    USING (id = current_setting('app.current_org_id', true)::UUID);

-- Service role bypass (for background workers, migrations, etc.)
-- Create a special role that bypasses RLS:
-- CREATE ROLE seo_service_role NOLOGIN;
-- GRANT seo_service_role TO app_user;
-- Then for each table:
--   ALTER TABLE <table> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY service_bypass ON <table> TO seo_service_role USING (true);
```

---

## Partition Maintenance

```sql
-- ============================================================
-- PARTITION MAINTENANCE CRON (pg_cron)
-- ============================================================
-- Requires pg_cron extension:
-- CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Auto-create next 3 months of partitions daily at midnight
-- SELECT cron.schedule('create-partitions', '0 0 * * *', $$
--     SELECT seo.create_monthly_partition('seo.agent_events', CURRENT_DATE);
--     SELECT seo.create_monthly_partition('seo.agent_events', CURRENT_DATE + INTERVAL '1 month');
--     SELECT seo.create_monthly_partition('seo.agent_events', CURRENT_DATE + INTERVAL '2 months');
--     SELECT seo.create_monthly_partition('seo.pages', CURRENT_DATE);
--     SELECT seo.create_monthly_partition('seo.pages', CURRENT_DATE + INTERVAL '1 month');
--     SELECT seo.create_monthly_partition('seo.pages', CURRENT_DATE + INTERVAL '2 months');
--     SELECT seo.create_monthly_partition('seo.keywords', CURRENT_DATE);
--     SELECT seo.create_monthly_partition('seo.keywords', CURRENT_DATE + INTERVAL '1 month');
--     SELECT seo.create_monthly_partition('seo.keywords', CURRENT_DATE + INTERVAL '2 months');
--     SELECT seo.create_monthly_partition('seo.serp_snapshots', CURRENT_DATE);
--     SELECT seo.create_monthly_partition('seo.serp_snapshots', CURRENT_DATE + INTERVAL '1 month');
--     SELECT seo.create_monthly_partition('seo.serp_snapshots', CURRENT_DATE + INTERVAL '2 months');
--     SELECT seo.create_monthly_partition('seo.analytics_snapshots', CURRENT_DATE);
--     SELECT seo.create_monthly_partition('seo.analytics_snapshots', CURRENT_DATE + INTERVAL '1 month');
--     SELECT seo.create_monthly_partition('seo.analytics_snapshots', CURRENT_DATE + INTERVAL '2 months');
--     SELECT seo.create_monthly_partition('seo.search_analytics', CURRENT_DATE);
--     SELECT seo.create_monthly_partition('seo.search_analytics', CURRENT_DATE + INTERVAL '1 month');
--     SELECT seo.create_monthly_partition('seo.search_analytics', CURRENT_DATE + INTERVAL '2 months');
--     SELECT seo.create_monthly_partition('audit.audit_logs', CURRENT_DATE);
--     SELECT seo.create_monthly_partition('audit.audit_logs', CURRENT_DATE + INTERVAL '1 month');
--     SELECT seo.create_monthly_partition('audit.audit_logs', CURRENT_DATE + INTERVAL '2 months');
--     SELECT seo.create_monthly_partition('seo.rate_limit_logs', CURRENT_DATE);
--     SELECT seo.create_monthly_partition('seo.rate_limit_logs', CURRENT_DATE + INTERVAL '1 month');
--     SELECT seo.create_monthly_partition('seo.rate_limit_logs', CURRENT_DATE + INTERVAL '2 months');
-- $$);

-- Drop partitions older than 2 years (data retention)
-- SELECT cron.schedule('drop-old-partitions', '0 2 * * 0', $$
--     -- Manually review before enabling in production
-- $$);

-- ============================================================
-- VACUUM / ANALYZE SCHEDULE
-- ============================================================
-- High-churn tables should be vacuumed frequently:
-- ALTER TABLE seo.agent_tasks SET (autovacuum_vacuum_scale_factor = 0.01);
-- ALTER TABLE seo.agent_events SET (autovacuum_vacuum_scale_factor = 0.05);
-- ALTER TABLE seo.serp_snapshots SET (autovacuum_vacuum_scale_factor = 0.05);
-- ALTER TABLE seo.rate_limit_logs SET (autovacuum_vacuum_scale_factor = 0.01);
-- ALTER TABLE audit.audit_logs SET (autovacuum_vacuum_scale_factor = 0.05);

-- ============================================================
-- INITIAL PARTITION SEEDING (run once at setup)
-- ============================================================
-- Create partitions for the current month and next 3 months:
-- SELECT seo.create_monthly_partition('seo.agent_events', '2025-01-01');
-- SELECT seo.create_monthly_partition('seo.pages', '2025-01-01');
-- SELECT seo.create_monthly_partition('seo.keywords', '2025-01-01');
-- SELECT seo.create_monthly_partition('seo.serp_snapshots', '2025-01-01');
-- SELECT seo.create_monthly_partition('seo.analytics_snapshots', '2025-01-01');
-- SELECT seo.create_monthly_partition('seo.search_analytics', '2025-01-01');
-- SELECT seo.create_monthly_partition('audit.audit_logs', '2025-01-01');
-- SELECT seo.create_monthly_partition('seo.rate_limit_logs', '2025-01-01');
```

---

## Summary: All Tables

| # | Table | Schema | Partitioned | RLS | Soft Delete | FTS |
|---|-------|--------|------------|-----|-------------|-----|
| 1 | organizations | seo | — | ✅ | ✅ | — |
| 2 | users | seo | — | ✅ | ✅ | — |
| 3 | roles | seo | — | ✅ | ✅ | — |
| 4 | permissions | seo | — | ✅ | — | — |
| 5 | projects | seo | — | ✅ | ✅ | — |
| 6 | api_keys | seo | — | ✅ | ✅ | — |
| 7 | oauth_connections | seo | — | ✅ | ✅ | — |
| 8 | agents | seo | — | ✅ | ✅ | — |
| 9 | agent_runs | seo | — | ✅ | — | — |
| 10 | agent_tasks | seo | — | ✅ | — | — |
| 11 | agent_events | seo | ✅ monthly | ✅ | — | — |
| 12 | pages | seo | ✅ monthly | ✅ | ✅ | ✅ |
| 13 | page_issues | seo | — | ✅ | — | — |
| 14 | page_fixes | seo | — | ✅ | — | — |
| 15 | keywords | seo | ✅ monthly | ✅ | ✅ | ✅ |
| 16 | serp_snapshots | seo | ✅ monthly | ✅ | — | — |
| 17 | serp_features | seo | — | ✅ | — | — |
| 18 | backlinks | seo | — | ✅ | — | ✅ |
| 19 | backlink_campaigns | seo | — | ✅ | ✅ | — |
| 20 | campaign_contacts | seo | — | ✅ | ✅ | — |
| 21 | campaign_messages | seo | — | ✅ | — | — |
| 22 | campaign_events | seo | — | ✅ | — | — |
| 23 | haro_queries | seo | — | ✅ | ✅ | ✅ |
| 24 | haro_responses | seo | — | ✅ | — | ✅ |
| 25 | haro_submissions | seo | — | ✅ | — | — |
| 26 | content_briefs | seo | — | ✅ | ✅ | ✅ |
| 27 | content_drafts | seo | — | ✅ | ✅ | ✅ |
| 28 | content_published | seo | — | ✅ | ✅ | ✅ |
| 29 | content_performance | seo | — | ✅ | — | — |
| 30 | analytics_snapshots | seo | ✅ monthly | ✅ | — | — |
| 31 | search_analytics | seo | ✅ monthly | ✅ | — | — |
| 32 | anomalies | seo | — | ✅ | — | — |
| 33 | reports | seo | — | ✅ | ✅ | — |
| 34 | audit_logs | audit | ✅ monthly | ✅ | — | — |
| 35 | security_events | seo | — | ✅ | — | — |
| 36 | rate_limit_logs | seo | ✅ monthly | ✅ | — | — |
| 37 | ip_blocklist | seo | — | ✅ | — | — |

**Total: 37 tables** across 2 schemas (`seo`, `audit`).
**Partitioned: 8 tables** (agent_events, pages, keywords, serp_snapshots, analytics_snapshots, search_analytics, audit_logs, rate_limit_logs).
**Full-text search: 7 tables** (pages, keywords, haro_queries, haro_responses, content_briefs, content_drafts, content_published).
**All tables** use UUID primary keys, JSONB for flexible data, and have `created_at`/`updated_at` timestamps.
