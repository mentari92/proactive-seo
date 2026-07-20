# Security Policy

Report vulnerabilities privately through GitHub Security Advisories. Do not open a public issue with
credentials, exploit details, tenant data, or personally identifiable information.

Supported releases are the current production release and its immediate rollback predecessor. The
platform uses tenant RLS, Argon2id, rotating RS256 sessions, encrypted provider credentials, approval-
gated external actions, signed webhooks, secret redaction, least-privilege containers, network
policies, and immutable audit trails.

Never commit `.env`, JWT keys, provider tokens, Terraform state, kubeconfig, exports, or customer data.
Production secrets belong in AWS Secrets Manager and reach workloads through External Secrets and
workload identity.

