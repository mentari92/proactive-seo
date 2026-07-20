"""SQLAlchemy Core representation of the canonical 37-table logical model."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _id() -> Column[uuid.UUID]:
    return Column("id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _timestamps(soft_delete: bool = False) -> list[Column[object]]:
    columns: list[Column[object]] = [
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column(
            "updated_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    ]
    if soft_delete:
        columns.append(Column("deleted_at", DateTime(timezone=True)))
    return columns


def _tenant_table(
    name: str,
    *columns: Column[object],
    schema: str = "seo",
    soft_delete: bool = False,
    org_nullable: bool = False,
) -> Table:
    return Table(
        name,
        metadata,
        _id(),
        Column(
            "org_id",
            Uuid(as_uuid=True),
            ForeignKey("seo.organizations.id", ondelete="CASCADE"),
            nullable=org_nullable,
            index=True,
        ),
        *columns,
        *_timestamps(soft_delete),
        schema=schema,
    )


organizations = Table(
    "organizations",
    metadata,
    _id(),
    Column("name", String(255), nullable=False),
    Column("slug", String(100), nullable=False, unique=True),
    Column("plan", String(50), nullable=False, server_default="starter"),
    Column("status", String(30), nullable=False, server_default="active"),
    Column("settings", JSON, nullable=False, default=dict),
    *_timestamps(True),
    schema="seo",
)

roles = _tenant_table(
    "roles",
    Column("name", String(100), nullable=False),
    Column("description", Text),
    Column("is_system", Boolean, nullable=False, server_default="false"),
    UniqueConstraint("org_id", "name"),
)

users = _tenant_table(
    "users",
    Column("role_id", Uuid(as_uuid=True), ForeignKey("seo.roles.id")),
    Column("email", String(320), nullable=False),
    Column("name", String(255), nullable=False),
    Column("password_hash", Text, nullable=False),
    Column("status", String(30), nullable=False, server_default="active"),
    Column("mfa_enabled", Boolean, nullable=False, server_default="false"),
    Column("mfa_secret_encrypted", Text),
    Column("last_login_at", DateTime(timezone=True)),
    UniqueConstraint("org_id", "email"),
    soft_delete=True,
)

permissions = Table(
    "permissions",
    metadata,
    _id(),
    Column("role_id", Uuid(as_uuid=True), ForeignKey("seo.roles.id", ondelete="CASCADE")),
    Column("resource", String(100), nullable=False),
    Column("action", String(50), nullable=False),
    Column("conditions", JSON, nullable=False, default=dict),
    *_timestamps(),
    UniqueConstraint("role_id", "resource", "action"),
    schema="seo",
)

projects = _tenant_table(
    "projects",
    Column("name", String(255), nullable=False),
    Column("domain", String(500), nullable=False),
    Column("status", String(30), nullable=False, server_default="active"),
    Column("settings", JSON, nullable=False, default=dict),
    Column("health_score", Numeric(5, 2)),
    UniqueConstraint("org_id", "domain"),
    soft_delete=True,
)

api_keys = _tenant_table(
    "api_keys",
    Column("user_id", Uuid(as_uuid=True), ForeignKey("seo.users.id"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("key_prefix", String(20), nullable=False, index=True),
    Column("key_hash", Text, nullable=False),
    Column("scopes", JSON, nullable=False, default=list),
    Column("expires_at", DateTime(timezone=True)),
    Column("last_used_at", DateTime(timezone=True)),
    soft_delete=True,
)

oauth_connections = _tenant_table(
    "oauth_connections",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id")),
    Column("provider", String(50), nullable=False),
    Column("status", String(30), nullable=False, server_default="disconnected"),
    Column("access_token_encrypted", Text),
    Column("refresh_token_encrypted", Text),
    Column("expires_at", DateTime(timezone=True)),
    Column("scopes", JSON, nullable=False, default=list),
    Column("metadata", JSON, nullable=False, default=dict),
    UniqueConstraint("org_id", "project_id", "provider"),
    soft_delete=True,
)

agents = _tenant_table(
    "agents",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id")),
    Column("key", String(50), nullable=False),
    Column("name", String(100), nullable=False),
    Column("status", String(30), nullable=False, server_default="active"),
    Column("config", JSON, nullable=False, default=dict),
    Column("budget", JSON, nullable=False, default=dict),
    UniqueConstraint("org_id", "project_id", "key"),
    soft_delete=True,
)

agent_runs = _tenant_table(
    "agent_runs",
    Column("agent_id", Uuid(as_uuid=True), ForeignKey("seo.agents.id"), nullable=False),
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id")),
    Column("status", String(30), nullable=False, server_default="queued"),
    Column("trigger", String(50), nullable=False),
    Column("correlation_id", Uuid(as_uuid=True), nullable=False),
    Column("input", JSON, nullable=False, default=dict),
    Column("output", JSON, nullable=False, default=dict),
    Column("error", JSON),
    Column("started_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
)

agent_tasks = _tenant_table(
    "agent_tasks",
    Column("run_id", Uuid(as_uuid=True), ForeignKey("seo.agent_runs.id"), nullable=False),
    Column("type", String(100), nullable=False),
    Column("status", String(30), nullable=False, server_default="queued"),
    Column("priority", Integer, nullable=False, server_default="50"),
    Column("attempt", Integer, nullable=False, server_default="0"),
    Column("payload", JSON, nullable=False, default=dict),
    Column("result", JSON, nullable=False, default=dict),
    Column("idempotency_key", String(255), nullable=False, unique=True),
    Column("scheduled_for", DateTime(timezone=True)),
)

agent_events = _tenant_table(
    "agent_events",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id")),
    Column("source", String(50), nullable=False),
    Column("target", String(50), nullable=False),
    Column("type", String(100), nullable=False),
    Column("priority", String(20), nullable=False),
    Column("correlation_id", Uuid(as_uuid=True), nullable=False),
    Column("trace_id", String(64), nullable=False),
    Column("payload", JSON, nullable=False, default=dict),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)

pages = _tenant_table(
    "pages",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("url", Text, nullable=False),
    Column("status_code", Integer),
    Column("title", String(1000)),
    Column("meta_description", Text),
    Column("content", Text),
    Column("crawl_data", JSON, nullable=False, default=dict),
    Column("last_crawled_at", DateTime(timezone=True)),
    UniqueConstraint("project_id", "url"),
    soft_delete=True,
)

page_issues = _tenant_table(
    "page_issues",
    Column("page_id", Uuid(as_uuid=True), ForeignKey("seo.pages.id"), nullable=False),
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("type", String(100), nullable=False),
    Column("severity", String(20), nullable=False),
    Column("status", String(20), nullable=False, server_default="open"),
    Column("description", Text, nullable=False),
    Column("evidence", JSON, nullable=False, default=dict),
)

page_fixes = _tenant_table(
    "page_fixes",
    Column("issue_id", Uuid(as_uuid=True), ForeignKey("seo.page_issues.id"), nullable=False),
    Column("action", String(100), nullable=False),
    Column("status", String(30), nullable=False, server_default="pending"),
    Column("before_state", JSON, nullable=False, default=dict),
    Column("after_state", JSON, nullable=False, default=dict),
    Column("rollback_state", JSON, nullable=False, default=dict),
    Column("approved_by", Uuid(as_uuid=True), ForeignKey("seo.users.id")),
)

keywords = _tenant_table(
    "keywords",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("keyword", String(500), nullable=False),
    Column("search_engine", String(30), nullable=False, server_default="google"),
    Column("location", String(100), nullable=False, server_default="US"),
    Column("device", String(20), nullable=False, server_default="desktop"),
    Column("search_volume", Integer),
    Column("difficulty", Numeric(5, 2)),
    Column("tags", JSON, nullable=False, default=list),
    UniqueConstraint("project_id", "keyword", "search_engine", "location", "device"),
    soft_delete=True,
)

serp_snapshots = _tenant_table(
    "serp_snapshots",
    Column("keyword_id", Uuid(as_uuid=True), ForeignKey("seo.keywords.id"), nullable=False),
    Column("position", Integer),
    Column("url", Text),
    Column("result_type", String(50)),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("raw_data", JSON, nullable=False, default=dict),
)

serp_features = _tenant_table(
    "serp_features",
    Column("snapshot_id", Uuid(as_uuid=True), ForeignKey("seo.serp_snapshots.id"), nullable=False),
    Column("feature", String(100), nullable=False),
    Column("owned", Boolean, nullable=False, server_default="false"),
    Column("data", JSON, nullable=False, default=dict),
)

backlinks = _tenant_table(
    "backlinks",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("target_url", Text, nullable=False),
    Column("anchor_text", Text),
    Column("domain_rank", Numeric(6, 2)),
    Column("status", String(30), nullable=False, server_default="active"),
    Column("first_seen_at", DateTime(timezone=True)),
    Column("last_seen_at", DateTime(timezone=True)),
    UniqueConstraint("project_id", "source_url", "target_url"),
)

backlink_campaigns = _tenant_table(
    "backlink_campaigns",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("type", String(30), nullable=False),
    Column("status", String(30), nullable=False, server_default="draft"),
    Column("settings", JSON, nullable=False, default=dict),
    Column("started_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint(
        "status IN ('draft','active','paused','completed','archived')",
        name="campaign_status",
    ),
    soft_delete=True,
)

campaign_contacts = _tenant_table(
    "campaign_contacts",
    Column("campaign_id", Uuid(as_uuid=True), ForeignKey("seo.backlink_campaigns.id")),
    Column("name", String(255)),
    Column("email", String(320), nullable=False),
    Column("domain", String(500)),
    Column("status", String(30), nullable=False, server_default="draft"),
    Column("metadata", JSON, nullable=False, default=dict),
    CheckConstraint(
        "status IN ('draft','sent','replied','negotiating','live','rejected')",
        name="prospect_status",
    ),
    soft_delete=True,
)

campaign_messages = _tenant_table(
    "campaign_messages",
    Column("campaign_id", Uuid(as_uuid=True), ForeignKey("seo.backlink_campaigns.id")),
    Column("contact_id", Uuid(as_uuid=True), ForeignKey("seo.campaign_contacts.id")),
    Column("gmail_thread_id", String(255)),
    Column("gmail_message_id", String(255)),
    Column("direction", String(20), nullable=False, server_default="outbound"),
    Column("subject", Text, nullable=False),
    Column("body", Text, nullable=False),
    Column("delivery_status", String(30), nullable=False, server_default="draft"),
    Column("follow_up_step", Integer, nullable=False, server_default="0"),
    Column("scheduled_at", DateTime(timezone=True)),
    Column("sent_at", DateTime(timezone=True)),
)

campaign_events = _tenant_table(
    "campaign_events",
    Column("campaign_id", Uuid(as_uuid=True), ForeignKey("seo.backlink_campaigns.id")),
    Column("contact_id", Uuid(as_uuid=True), ForeignKey("seo.campaign_contacts.id")),
    Column("type", String(50), nullable=False),
    Column("data", JSON, nullable=False, default=dict),
)

haro_queries = _tenant_table(
    "haro_queries",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("source_id", String(255), nullable=False),
    Column("title", String(500), nullable=False),
    Column("query", Text, nullable=False),
    Column("journalist", String(255)),
    Column("outlet", String(255)),
    Column("deadline", DateTime(timezone=True)),
    Column("status", String(30), nullable=False, server_default="new"),
    UniqueConstraint("org_id", "source_id"),
    soft_delete=True,
)

haro_responses = _tenant_table(
    "haro_responses",
    Column("query_id", Uuid(as_uuid=True), ForeignKey("seo.haro_queries.id"), nullable=False),
    Column("content", Text, nullable=False),
    Column("status", String(30), nullable=False, server_default="draft"),
    Column("ai_model", String(100)),
    Column("citations", JSON, nullable=False, default=list),
)

haro_submissions = _tenant_table(
    "haro_submissions",
    Column("query_id", Uuid(as_uuid=True), ForeignKey("seo.haro_queries.id"), nullable=False),
    Column("response_id", Uuid(as_uuid=True), ForeignKey("seo.haro_responses.id"), nullable=False),
    Column("message_id", Uuid(as_uuid=True), ForeignKey("seo.campaign_messages.id")),
    Column("status", String(30), nullable=False, server_default="submitted"),
    Column("published_url", Text),
    Column("backlink_acquired", Boolean, nullable=False, server_default="false"),
    Column("submitted_at", DateTime(timezone=True), nullable=False),
)

content_briefs = _tenant_table(
    "content_briefs",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("title", String(500), nullable=False),
    Column("target_keyword", String(500), nullable=False),
    Column("content_type", String(100), nullable=False),
    Column("outline", JSON, nullable=False, default=list),
    Column("status", String(30), nullable=False, server_default="draft"),
    Column("metadata", JSON, nullable=False, default=dict),
    soft_delete=True,
)

content_drafts = _tenant_table(
    "content_drafts",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("brief_id", Uuid(as_uuid=True), ForeignKey("seo.content_briefs.id")),
    Column("title", String(500), nullable=False),
    Column("slug", String(255)),
    Column("content_html", Text, nullable=False),
    Column("content_markdown", Text, nullable=False),
    Column("seo_score", Numeric(5, 2)),
    Column("ai_readiness_score", Numeric(5, 2)),
    Column("status", String(30), nullable=False, server_default="draft"),
    Column("version", Integer, nullable=False, server_default="1"),
    soft_delete=True,
)

content_published = _tenant_table(
    "content_published",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("draft_id", Uuid(as_uuid=True), ForeignKey("seo.content_drafts.id")),
    Column("title", String(500), nullable=False),
    Column("slug", String(255), nullable=False),
    Column("url", Text, nullable=False),
    Column("content_html", Text, nullable=False),
    Column("content_markdown", Text, nullable=False),
    Column("cms_type", String(50)),
    Column("cms_post_id", String(255)),
    Column("published_at", DateTime(timezone=True), nullable=False),
    soft_delete=True,
)

content_performance = _tenant_table(
    "content_performance",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("content_id", Uuid(as_uuid=True), ForeignKey("seo.content_published.id"), nullable=False),
    Column("date", Date, nullable=False),
    Column("impressions", Integer, nullable=False, server_default="0"),
    Column("clicks", Integer, nullable=False, server_default="0"),
    Column("sessions", Integer, nullable=False, server_default="0"),
    Column("conversions", Integer, nullable=False, server_default="0"),
    UniqueConstraint("content_id", "date"),
)

analytics_snapshots = _tenant_table(
    "analytics_snapshots",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("source", String(50), nullable=False),
    Column("date", Date, nullable=False),
    Column("page_url", Text),
    Column("sessions", Integer, nullable=False, server_default="0"),
    Column("users", Integer, nullable=False, server_default="0"),
    Column("conversions", Integer, nullable=False, server_default="0"),
    Column("raw_data", JSON, nullable=False, default=dict),
)

search_analytics = _tenant_table(
    "search_analytics",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("source", String(50), nullable=False, server_default="gsc"),
    Column("date", Date, nullable=False),
    Column("query", String(500)),
    Column("page_url", Text),
    Column("device", String(50)),
    Column("impressions", Integer, nullable=False, server_default="0"),
    Column("clicks", Integer, nullable=False, server_default="0"),
    Column("ctr", Numeric(7, 6)),
    Column("avg_position", Numeric(8, 2)),
    Column("raw_data", JSON, nullable=False, default=dict),
)

anomalies = _tenant_table(
    "anomalies",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id"), nullable=False),
    Column("anomaly_type", String(50), nullable=False),
    Column("severity", String(20), nullable=False),
    Column("title", String(500), nullable=False),
    Column("description", Text, nullable=False),
    Column("metric_name", String(100), nullable=False),
    Column("metric_value", Numeric(15, 4)),
    Column("expected_value", Numeric(15, 4)),
    Column("is_acknowledged", Boolean, nullable=False, server_default="false"),
    Column("is_resolved", Boolean, nullable=False, server_default="false"),
    Column("data", JSON, nullable=False, default=dict),
)

reports = _tenant_table(
    "reports",
    Column("project_id", Uuid(as_uuid=True), ForeignKey("seo.projects.id")),
    Column("name", String(255), nullable=False),
    Column("type", String(100), nullable=False),
    Column("format", String(20), nullable=False, server_default="pdf"),
    Column("status", String(30), nullable=False, server_default="pending"),
    Column("config", JSON, nullable=False, default=dict),
    Column("file_url", Text),
    Column("scheduled_cron", String(100)),
    soft_delete=True,
)

audit_logs = _tenant_table(
    "audit_logs",
    Column("user_id", Uuid(as_uuid=True)),
    Column("action", String(100), nullable=False),
    Column("resource_type", String(100), nullable=False),
    Column("resource_id", Uuid(as_uuid=True)),
    Column("old_values", JSON),
    Column("new_values", JSON),
    Column("ip_address", String(64)),
    Column("request_id", String(64)),
    schema="audit",
    org_nullable=True,
)

security_events = _tenant_table(
    "security_events",
    Column("user_id", Uuid(as_uuid=True), ForeignKey("seo.users.id")),
    Column("event_type", String(100), nullable=False),
    Column("severity", String(20), nullable=False),
    Column("ip_address", String(64)),
    Column("details", JSON, nullable=False, default=dict),
    org_nullable=True,
)

rate_limit_logs = _tenant_table(
    "rate_limit_logs",
    Column("user_id", Uuid(as_uuid=True), ForeignKey("seo.users.id")),
    Column("api_key_id", Uuid(as_uuid=True), ForeignKey("seo.api_keys.id")),
    Column("ip_address", String(64), nullable=False),
    Column("endpoint", String(500), nullable=False),
    Column("method", String(10), nullable=False),
    Column("limit_value", Integer, nullable=False),
    Column("current_count", Integer, nullable=False),
    Column("window_seconds", Integer, nullable=False),
    Column("was_blocked", Boolean, nullable=False, server_default="false"),
    org_nullable=True,
)

ip_blocklist = _tenant_table(
    "ip_blocklist",
    Column("ip_address", String(64), nullable=False),
    Column("ip_range", String(64)),
    Column("reason", Text, nullable=False),
    Column("block_type", String(50), nullable=False, server_default="manual"),
    Column("expires_at", DateTime(timezone=True)),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    Column("created_by", Uuid(as_uuid=True), ForeignKey("seo.users.id")),
    Column("metadata", JSON, nullable=False, default=dict),
    org_nullable=True,
)

tables: dict[str, Table] = {table.name: table for table in metadata.tables.values()}
if len(tables) != 37:
    raise RuntimeError(f"Canonical metadata must contain exactly 37 tables, got {len(tables)}")

Index("ix_agent_tasks_status_priority", agent_tasks.c.status, agent_tasks.c.priority)
Index("ix_campaign_contacts_campaign_status", campaign_contacts.c.campaign_id, campaign_contacts.c.status)
Index("ix_serp_snapshots_keyword_captured", serp_snapshots.c.keyword_id, serp_snapshots.c.captured_at)


def tenant_scoped_tables() -> Sequence[Table]:
    """Return tables requiring tenant RLS, excluding role-derived permissions."""
    return tuple(table for table in metadata.tables.values() if "org_id" in table.c)
