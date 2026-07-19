export const ROUTES = [
  "/login", "/register", "/forgot-password", "/verify-email",
  "/overview", "/activity", "/notifications",
  "/projects", "/projects/new", "/projects/demo", "/projects/demo/settings",
  "/seo/overview", "/seo/keywords", "/seo/pages", "/seo/issues", "/seo/health-score",
  "/agents", "/agents/sentinel", "/agents/forge", "/agents/technical", "/agents/scout",
  "/agents/outreach", "/agents/competitor", "/agents/decision", "/agents/executor",
  "/agents/sentinel/logs", "/agents/sentinel/config",
  "/campaigns", "/campaigns/demo", "/campaigns/haro", "/campaigns/broken-links",
  "/campaigns/guest-posts", "/campaigns/unlinked-mentions",
  "/content/briefs", "/content/drafts", "/content/published", "/content/editor/demo",
  "/technical/audit", "/technical/schema", "/technical/self-healing", "/technical/multi-engine",
  "/analytics", "/analytics/traffic", "/analytics/conversions",
  "/reports", "/reports/generate", "/reports/demo",
  "/settings/profile", "/settings/organization", "/settings/team", "/settings/billing",
  "/settings/api-keys", "/settings/notifications", "/settings/security",
  "/settings/integrations", "/settings/integrations/gsc"
] as const;

export const NAVIGATION = [
  { label: "Overview", href: "/overview", icon: "overview" },
  { label: "SEO command", href: "/seo/overview", icon: "search" },
  { label: "Agents", href: "/agents", icon: "agents" },
  { label: "Campaigns", href: "/campaigns", icon: "campaigns" },
  { label: "Content", href: "/content/briefs", icon: "content" },
  { label: "Technical", href: "/technical/audit", icon: "technical" },
  { label: "Analytics", href: "/analytics", icon: "analytics" },
  { label: "Reports", href: "/reports", icon: "reports" },
  { label: "Settings", href: "/settings/profile", icon: "settings" }
] as const;

