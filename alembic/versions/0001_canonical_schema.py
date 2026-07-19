"""Create the canonical 37-table tenant model.

Revision ID: 0001
Revises: None
"""

from collections.abc import Sequence

from alembic import op

from proactive_core.db.models import metadata, tenant_scoped_tables

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create schemas, tables, update triggers, and corrected RLS policies."""
    bind = op.get_bind()
    op.execute("CREATE SCHEMA IF NOT EXISTS seo")
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    metadata.create_all(bind=bind, checkfirst=False)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION seo.set_updated_at() RETURNS trigger AS $$
        BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in metadata.tables.values():
        if "updated_at" not in table.c:
            continue
        op.execute(
            f'CREATE TRIGGER trg_{table.name}_updated_at BEFORE UPDATE ON '
            f'"{table.schema}"."{table.name}" FOR EACH ROW EXECUTE FUNCTION seo.set_updated_at()'
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION seo.tenant_isolation(row_org UUID) RETURNS BOOLEAN AS $$
          SELECT row_org = NULLIF(current_setting('app.current_org_id', true), '')::UUID;
        $$ LANGUAGE sql STABLE;
        """
    )
    for table in tenant_scoped_tables():
        qualified = f'"{table.schema}"."{table.name}"'
        op.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {qualified} "
            "USING (seo.tenant_isolation(org_id)) WITH CHECK (seo.tenant_isolation(org_id))"
        )

    op.execute("ALTER TABLE seo.organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE seo.organizations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY organization_isolation ON seo.organizations "
        "USING (id = NULLIF(current_setting('app.current_org_id', true), '')::UUID) "
        "WITH CHECK (id = NULLIF(current_setting('app.current_org_id', true), '')::UUID)"
    )
    op.execute("ALTER TABLE seo.permissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE seo.permissions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY permission_role_isolation ON seo.permissions
        USING (EXISTS (
          SELECT 1 FROM seo.roles r
          WHERE r.id = permissions.role_id AND seo.tenant_isolation(r.org_id)
        ))
        WITH CHECK (EXISTS (
          SELECT 1 FROM seo.roles r
          WHERE r.id = permissions.role_id AND seo.tenant_isolation(r.org_id)
        ));
        """
    )


def downgrade() -> None:
    """Drop the canonical application schemas."""
    op.execute("DROP SCHEMA IF EXISTS audit CASCADE")
    op.execute("DROP SCHEMA IF EXISTS seo CASCADE")

