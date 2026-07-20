# Contributing

Use Python 3.12, uv, Node.js 20, and pnpm 9. Create a focused branch and preserve the public v1 contract
unless a versioned change has been approved. New Python functions require type hints; public classes
and methods require docstrings. All provider work needs a deterministic fake and must remain inert in
CI.

Before requesting review, run the verification commands in `README.md`. Schema changes require an
Alembic upgrade/downgrade test and cross-tenant RLS test. Agent changes require deterministic workflow,
retry, idempotency, approval, and partial-provider-failure tests. Frontend changes require keyboard,
responsive, light/dark, loading, empty, error, and partial-failure coverage.

