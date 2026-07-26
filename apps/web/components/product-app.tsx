"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  Bot,
  Check,
  ChevronDown,
  CircleGauge,
  FileText,
  LayoutDashboard,
  Menu,
  Moon,
  MoreHorizontal,
  Plus,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sun,
  Wrench,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { NAVIGATION, ROUTES } from "@/lib/routes";
import { api, API_URL } from "@/lib/api";
import { useWorkspace } from "@/lib/state";
import { useSSE } from "@/lib/use-sse";
import { Badge, Button, Card, Skeleton, cn } from "./ui";

const icons = {
  overview: LayoutDashboard,
  search: Search,
  agents: Bot,
  campaigns: Send,
  content: FileText,
  technical: Wrench,
  analytics: BarChart3,
  reports: Activity,
  settings: Settings
};

type ApiRecord = Record<string, unknown>;

const authHeaders = (accessToken: string | null) => {
  const token = accessToken || "auto-login";
  return { Authorization: `Bearer ${token}` };
};
const textValue = (value: unknown, fallback = "—") => value === null || value === undefined || value === "" ? fallback : String(value);
const numberValue = (value: unknown) => typeof value === "number" ? value : Number(value) || 0;
const recordArray = (value: unknown): ApiRecord[] => Array.isArray(value) ? value.filter((item): item is ApiRecord => Boolean(item) && typeof item === "object") : [];
const recordValue = (value: unknown): ApiRecord => Boolean(value) && typeof value === "object" && !Array.isArray(value) ? value as ApiRecord : {};

function EmptyState({ children = "No data yet" }: { children?: string }) {
  return <Card><p className="muted">{children}</p></Card>;
}

function useProjects() {
  const accessToken = useWorkspace((state) => state.accessToken);
  return useQuery({
    queryKey: ["projects", accessToken],
    queryFn: () => api<ApiRecord[]>("/projects", { headers: authHeaders(accessToken) }),
    enabled: Boolean(accessToken)
  });
}

function useProjectQuery(path: string) {
  const accessToken = useWorkspace((state) => state.accessToken);
  const projects = useProjects();
  const projectId = textValue(projects.data?.data[0]?.id, "");
  const query = useQuery({
    queryKey: ["project", projectId, path, accessToken],
    queryFn: () => api<unknown>(`/projects/${projectId}/${path}`, { headers: authHeaders(accessToken) }),
    enabled: Boolean(accessToken && projectId)
  });
  return { ...query, projectId, projectsLoading: projects.isLoading };
}

function titleFor(route: string, userName = "") {
  if (route === "/overview") return [`Good morning, ${userName}`, "Here’s what your agents improved while you were away."];
  const segment = route.split("/").filter(Boolean).at(-1) ?? "overview";
  const title = segment.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  return [title, "Monitor performance, review recommendations, and approve high-impact work."];
}

function AuthPage({ route }: { route: string }) {
  const isRegister = route === "/register";
  const forgot = route === "/forgot-password";
  const verified = route === "/verify-email";
  const setAccessToken = useWorkspace((state) => state.setAccessToken);
  const mutation = useMutation({
    mutationFn: async (form: FormData) => {
      const email = String(form.get("email") ?? "");
      if (forgot) return api<{ accepted: boolean }>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
      const body = isRegister
        ? {
            email,
            password: String(form.get("password") ?? ""),
            name: String(form.get("name") ?? ""),
            organization_name: String(form.get("organization") ?? "")
          }
        : { email, password: String(form.get("password") ?? "") };
      return api<{ tokens: { access_token: string } }>(isRegister ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify(body)
      });
    },
    onSuccess: (response) => {
      if ("tokens" in response.data) {
        const token = response.data.tokens.access_token;
        setAccessToken(token);
        // Write directly to localStorage to ensure persistence before redirect
        try {
          const existing = JSON.parse(localStorage.getItem("proactive-session") || "{}");
          existing.state = { ...(existing.state || {}), accessToken: token };
          localStorage.setItem("proactive-session", JSON.stringify(existing));
        } catch {}
        window.location.assign("/overview");
      }
    }
  });
  return (
    <main className="auth-layout">
      <section className="auth-story">
        <div className="brand-lockup"><span className="brand-mark">P</span> ProActive SEO</div>
        <div>
          <Badge tone="primary">Agentic search operations</Badge>
          <h1>Turn SEO decisions into measurable action.</h1>
          <p>Specialized agents automate recurring SEO work while your team controls every consequential change.</p>
          <div className="trust-row"><ShieldCheck size={18} /> Tenant isolated · Approval gated · Fully audited</div>
        </div>
        <p className="auth-footnote">Trusted workflows for monitored sites</p>
      </section>
      <section className="auth-form-wrap">
        <form
          className="auth-form"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate(new FormData(event.currentTarget));
          }}
        >
          <div>
            <p className="overline">Welcome to ProActive SEO</p>
            <h2>{verified ? "Email verified" : forgot ? "Reset your password" : isRegister ? "Create your workspace" : "Sign in to your account"}</h2>
            <p className="muted">{verified ? "Your identity is confirmed. Sign in to continue." : forgot ? "We’ll send a secure reset link if the account exists." : "Use your organization credentials to continue."}</p>
          </div>
          {isRegister && <label>Full name<input name="name" autoComplete="name" placeholder="Maya Chen" /></label>}
          {isRegister && <label>Organization<input name="organization" autoComplete="organization" placeholder="Acme Inc." /></label>}
          <label>Email<input name="email" type="email" autoComplete="email" placeholder="maya@acme.com" required /></label>
          {!forgot && <label>Password<input name="password" type="password" autoComplete={isRegister ? "new-password" : "current-password"} placeholder="At least 12 characters" minLength={12} required /></label>}
          {mutation.isError && <p role="alert" className="warning-text">{mutation.error.message}</p>}
          {mutation.isSuccess && forgot && <p role="status" className="muted">If the account exists, a secure link is on its way.</p>}
          <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>{mutation.isPending ? "Working…" : forgot ? "Send reset link" : isRegister ? "Create workspace" : "Sign in"}</Button>
          <p className="form-switch">
            {isRegister ? "Already have an account?" : "New to ProActive SEO?"}{" "}
            <Link href={isRegister ? "/login" : "/register"}>{isRegister ? "Sign in" : "Create an account"}</Link>
          </p>
          {!isRegister && !forgot && <Link className="forgot-link" href="/forgot-password">Forgot password?</Link>}
        </form>
      </section>
    </main>
  );
}

function Sidebar({ route }: { route: string }) {
  const { sidebarOpen, toggleSidebar } = useWorkspace();
  const accessToken = useWorkspace((state) => state.accessToken);
  const projects = useQuery({
    queryKey: ["projects", accessToken],
    queryFn: () => api<Array<{ name?: string; plan?: string }>>("/projects", { headers: { Authorization: `Bearer ${accessToken}` } }),
    enabled: Boolean(accessToken)
  });
  const users = useQuery({
    queryKey: ["users", accessToken],
    queryFn: () => api<Array<{ name?: string; role?: string }>>("/users", { headers: { Authorization: `Bearer ${accessToken}` } }),
    enabled: Boolean(accessToken)
  });
  const project = projects.data?.data[0];
  const user = users.data?.data[0];
  const projectName = project?.name ?? "";
  const projectPlan = project?.plan ?? "";
  const userName = user?.name ?? "";
  const userRole = user?.role ?? "";
  const userInitials = userName
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() || "MC";
  const streamStatus = useSSE(`${API_URL}/stream/agents`, accessToken);
  return (
    <>
      {sidebarOpen && <button className="scrim" aria-label="Close navigation" onClick={toggleSidebar} />}
      <aside className={cn("sidebar", sidebarOpen && "sidebar-open")}>
        <div className="sidebar-brand"><span className="brand-mark">P</span><span>ProActive SEO</span><button className="mobile-close" onClick={toggleSidebar} aria-label="Close navigation"><X size={18} /></button></div>
        <div className="project-switcher"><span className="project-avatar">{projectName[0]?.toUpperCase() ?? "A"}</span><span><b>{projectName}</b><small>{projectPlan}</small></span><ChevronDown size={15} /></div>
        <nav aria-label="Primary navigation">
          {NAVIGATION.map((item) => {
            const Icon = icons[item.icon];
            const active = route === item.href || (item.href !== "/overview" && route.startsWith(item.href.split("/").slice(0, 2).join("/")));
            return <Link key={item.href} href={item.href} className={cn("nav-link", active && "nav-link-active")}><Icon size={17} /><span>{item.label}</span></Link>;
          })}
        </nav>
        <div className="sidebar-status"><span className="status-dot" /><span><b>{streamStatus === "connected" ? "Live agent stream" : "Agent stream"}</b><small>{streamStatus === "error" ? "Reconnecting…" : streamStatus === "connecting" ? "Connecting…" : "Event bus ready"}</small></span></div>
        <div className="sidebar-user"><span className="user-avatar">{userInitials}</span><span><b>{userName}</b><small>{userRole}</small></span><MoreHorizontal size={16} /></div>
      </aside>
    </>
  );
}

function Header() {
  const { toggleSidebar, setCommandOpen } = useWorkspace();
  const [dark, setDark] = useState(false);
  const accessToken = useWorkspace((state) => state.accessToken);
  const users = useQuery({
    queryKey: ["users", accessToken],
    queryFn: () => api<Array<{ name?: string }>>("/users", { headers: { Authorization: `Bearer ${accessToken}` } }),
    enabled: Boolean(accessToken)
  });
  const userName = users.data?.data[0]?.name ?? "";
  const userInitials = userName
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() || "P";
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);
  return (
    <header className="topbar">
      <button className="icon-button menu-button" onClick={toggleSidebar} aria-label="Open navigation"><Menu size={19} /></button>
      <button className="command-trigger" onClick={() => setCommandOpen(true)} aria-label="Search or run a command"><Search size={16} /><span>Search or run a command</span><kbd>⌘ K</kbd></button>
      <div className="topbar-actions">
        <button className="icon-button" onClick={() => setDark(!dark)} aria-label="Toggle dark mode">{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
        <button className="icon-button notification-button" aria-label="Notifications"><Bell size={18} /><span /></button>
        <button className="avatar-button" aria-label="Open profile">{userInitials}</button>
      </div>
    </header>
  );
}

function CommandPalette() {
  const { commandOpen, setCommandOpen } = useWorkspace();
  const [query, setQuery] = useState("");
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(!commandOpen);
      }
      if (event.key === "Escape") setCommandOpen(false);
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, [commandOpen, setCommandOpen]);
  const matches = useMemo(() => ROUTES.filter((route) => route.includes(query.toLowerCase())).slice(0, 8), [query]);
  if (!commandOpen) return null;
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={() => setCommandOpen(false)}>
      <section className="command-palette" role="dialog" aria-modal="true" aria-label="Command palette" onMouseDown={(event) => event.stopPropagation()}>
        <label className="command-input"><Search size={19} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search pages, agents, and actions…" /></label>
        <p className="overline">Navigation</p>
        <div className="command-results">{matches.map((route) => <Link key={route} href={route} onClick={() => setCommandOpen(false)}><span>↗</span>{route}</Link>)}</div>
      </section>
    </div>
  );
}

function StatCard({ label, value, delta, positive = true }: { label: string; value: string; delta: string; positive?: boolean }) {
  return <Card className="stat-card"><div><p>{label}</p><h3>{value}</h3></div><Badge tone={positive ? "success" : "danger"}>{positive ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}{delta}</Badge></Card>;
}

function Overview() {
  const accessToken = useWorkspace((state) => state.accessToken);
  const dashboard = useProjectQuery("dashboard");
  const health = useProjectQuery("health-score");
  const issues = useProjectQuery("issues");
  const agents = useQuery({
    queryKey: ["agents", accessToken],
    queryFn: () => api<ApiRecord[]>("/agents", { headers: authHeaders(accessToken) }),
    enabled: Boolean(accessToken)
  });
  const agentId = textValue(agents.data?.data[0]?.id, "");
  const runs = useQuery({
    queryKey: ["agent-runs", agentId, accessToken],
    queryFn: () => api<ApiRecord[]>(`/agents/${agentId}/runs`, { headers: authHeaders(accessToken) }),
    enabled: Boolean(accessToken && agentId)
  });
  if (dashboard.isLoading || dashboard.projectsLoading || health.isLoading || issues.isLoading || agents.isLoading || runs.isLoading) return <Skeleton className="trend-card" />;
  const data = recordValue(dashboard.data?.data);
  const healthData = recordValue(health.data?.data);
  const trend = recordArray(data.trend ?? data.visibility_trend ?? data.history);
  const issueRows = recordArray(issues.data?.data);
  const runRows = recordArray(runs.data?.data);
  if (!dashboard.projectId || (Object.keys(data).length === 0 && Object.keys(healthData).length === 0 && issueRows.length === 0 && runRows.length === 0)) return <EmptyState>No overview data yet</EmptyState>;
  const scoreValue = healthData.health_score ?? healthData.score;
  const score = numberValue(scoreValue);
  const stats = [
    ["SEO health", scoreValue === undefined ? "—" : `${score} / 100`, healthData.change],
    ["AI Search visibility", textValue(data.ai_search_visibility ?? data.visibility), data.visibility_change],
    ["Keywords in top 10", textValue(data.keywords_top_10 ?? data.top_10_keywords), data.keywords_change],
    ["Open critical issues", textValue(data.critical_issues ?? issueRows.filter((issue) => issue.severity === "critical").length), data.issues_change]
  ];
  return (
    <>
      <section className="stats-grid">
        {stats.map(([label, value, delta], index) => <StatCard key={String(label)} label={String(label)} value={String(value)} delta={textValue(delta)} positive={index !== 3} />)}
      </section>
      <section className="overview-grid">
        <Card className="trend-card">
          <div className="card-heading"><div><p className="overline">Search performance</p><h3>Visibility trend</h3></div><Badge>Last 7 days</Badge></div>
          <div className="chart-wrap" role="img" aria-label="Visibility trend">
            {trend.length === 0 ? <p className="muted">No data yet</p> :
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 12, right: 8, bottom: 0, left: -20 }}>
                <defs><linearGradient id="visibility" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6366f1" stopOpacity={0.28} /><stop offset="100%" stopColor="#6366f1" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-default)" />
                <XAxis dataKey={textValue(data.trend_label_key, "day")} axisLine={false} tickLine={false} tick={{ fill: "var(--ink-tertiary)", fontSize: 11 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: "var(--ink-tertiary)", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "var(--bg-surface-raised)", border: "1px solid var(--border-default)", borderRadius: 6, fontSize: 12 }} />
                <Area type="monotone" dataKey="visibility" stroke="#6366f1" strokeWidth={2} fill="url(#visibility)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>}
          </div>
        </Card>
        <Card className="health-card">
          <div className="card-heading"><div><p className="overline">Site condition</p><h3>Health score</h3></div><CircleGauge size={20} /></div>
          <div className="health-ring"><span>{score}</span><small>{score > 80 ? "Excellent" : score > 60 ? "Good" : "Needs attention"}</small></div>
          <div className="health-breakdown"><span><i className="success" /> {textValue(healthData.passed)} passed</span><span><i className="warning" /> {textValue(healthData.warnings)} warnings</span><span><i className="danger" /> {textValue(healthData.critical)} critical</span></div>
        </Card>
      </section>
      <section className="lower-grid">
        <Card>
          <div className="card-heading"><div><p className="overline">Decision queue</p><h3>Recommended actions</h3></div><Link href="/activity">View all</Link></div>
          <div className="action-list">
            {issueRows.length === 0 ? <p className="muted">No data yet</p> : issueRows.slice(0, 3).map((issue, index) => <div key={textValue(issue.id, String(index))}><span className={cn("priority", `priority-${Math.min(index, 2)}`)}>{textValue(issue.severity, "P")}</span><span><b>{textValue(issue.title ?? issue.message ?? issue.type)}</b><small>{textValue(issue.url ?? issue.status)}</small></span><Button variant="secondary">Review</Button></div>)}
          </div>
        </Card>
        <Card>
          <div className="card-heading"><div><p className="overline">Live operations</p><h3>Agent activity</h3></div><span className="live-label"><i /> Live</span></div>
          <div className="activity-list">
            {runRows.length === 0 ? <p className="muted">No data yet</p> : runRows.slice(0, 4).map((run, index) => <p key={textValue(run.id, String(index))}><Check size={14} /> {textValue(run.message ?? run.operation ?? run.status)} <time>{textValue(run.created_at ?? run.updated_at)}</time></p>)}
          </div>
        </Card>
      </section>
    </>
  );
}

function AgentCenter() {
  const accessToken = useWorkspace((state) => state.accessToken);
  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: () => api<Array<{ name?: string; key?: string; status?: string; role?: string }>>("/agents", { headers: { Authorization: `Bearer ${accessToken}` } }),
    enabled: Boolean(accessToken)
  });
  if (agents.isLoading) return <section className="agent-grid">{Array.from({ length: 8 }, (_, index) => <Card key={index} className="agent-card"><Skeleton className="agent-detail" /><Skeleton className="agent-detail" /></Card>)}</section>;
  if (agents.isError) return <Card><h3>Agents are temporarily unavailable</h3><p className="warning-text">{agents.error.message}</p><Button variant="secondary" onClick={() => agents.refetch()}>Retry</Button></Card>;
  const remote = agents.data?.data ?? [];
  if (remote.length === 0) return <EmptyState>No agents yet</EmptyState>;
  const rows = remote.map((agent) => [agent.name ?? agent.key ?? "Agent", agent.role ?? "SEO", textValue((agent as ApiRecord).detail ?? (agent as ApiRecord).description), agent.status ?? "unknown"] as const);
  return <section className="agent-grid">{rows.map(([name, role, detail, status]) => <Card key={name} className="agent-card"><div className="agent-head"><span className="agent-icon"><Bot size={19} /></span><Badge tone={status === "active" ? "success" : status === "paused" ? "default" : "warning"}>{status}</Badge></div><div><h3>{name}</h3><p>{role} agent</p></div><p className="agent-detail">{detail}</p><div className="agent-foot"><span><i className={status} /> {status === "active" ? "Running" : status === "paused" ? "Paused" : "Review"}</span><Link href={`/agents/${name.toLowerCase()}`}>Open →</Link></div></Card>)}</section>;
}

function CampaignBoard() {
  const accessToken = useWorkspace((state) => state.accessToken);
  const campaigns = useQuery({
    queryKey: ["campaigns", accessToken],
    queryFn: () => api<ApiRecord[]>("/campaigns", { headers: authHeaders(accessToken) }),
    enabled: Boolean(accessToken)
  });
  const columns = ["Draft", "Sent", "Replied", "Negotiating", "Live", "Rejected"];
  if (campaigns.isLoading) return <Skeleton className="kanban" />;
  const rows = campaigns.data?.data ?? [];
  if (rows.length === 0) return <EmptyState>No campaigns yet</EmptyState>;
  return <div className="kanban" role="region" aria-label="Campaign prospect board" tabIndex={0}>{columns.map((column) => { const matches = rows.filter((campaign) => String(campaign.status ?? "Draft").toLowerCase() === column.toLowerCase()); return <section key={column} className="kanban-column"><header><span>{column}</span><Badge>{matches.length}</Badge></header>{matches.map((campaign, index) => <article key={textValue(campaign.id, String(index))}><Badge tone={campaign.type === "HARO" ? "primary" : "default"}>{textValue(campaign.type)}</Badge><h4>{textValue(campaign.name ?? campaign.title)}</h4><p>{textValue(campaign.replies, "0")} replies · {textValue(campaign.links, "0")} links</p><small>{textValue(campaign.next_action_at ?? campaign.updated_at)}</small></article>)}</section>; })}</div>;
}

function DataTable({ route }: { route: string }) {
  const accessToken = useWorkspace((state) => state.accessToken);
  const projects = useProjects();
  const projectId = textValue(projects.data?.data[0]?.id, "");
  const resource = route.includes("keyword") ? `projects/${projectId}/keywords` : route.includes("pages") ? `projects/${projectId}/pages` : route.includes("issues") ? `projects/${projectId}/issues` : "campaigns";
  const result = useQuery({ queryKey: ["table", resource, accessToken], queryFn: () => api<ApiRecord[]>(`/${resource}`, { headers: authHeaders(accessToken) }), enabled: Boolean(accessToken && (!resource.startsWith("projects/") || projectId)) });
  if (result.isLoading || projects.isLoading) return <Skeleton className="table-card" />;
  const records = recordArray(result.data?.data);
  if (records.length === 0) return <EmptyState />;
  const headers = Object.keys(records[0]).filter((key) => !["id", "organization_id", "project_id"].includes(key)).slice(0, 6);
  return <Card className="table-card"><div className="filter-row"><label><Search size={15} /><input placeholder="Search and filter…" /></label><Button variant="secondary">Filters</Button></div><div className="table-scroll"><table><thead><tr>{headers.map((header) => <th key={header}>{header.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{records.map((row, rowIndex) => <tr key={textValue(row.id, String(rowIndex))}>{headers.map((header) => <td key={`${textValue(row.id, String(rowIndex))}-${header}`}>{header === "status" ? <Badge>{textValue(row[header])}</Badge> : textValue(row[header])}</td>)}</tr>)}</tbody></table></div></Card>;
}

function NewProject() {
  const accessToken = useWorkspace((state) => state.accessToken);
  const mutation = useMutation({
    mutationFn: (form: FormData) => api<ApiRecord>("/projects", {
      method: "POST",
      headers: authHeaders(accessToken),
      body: JSON.stringify({
        name: String(form.get("name") ?? ""),
        domain: String(form.get("domain") ?? "")
      })
    }),
    onSuccess: () => window.location.assign("/overview")
  });
  return (
    <Card>
      <form className="settings-form" onSubmit={(event) => { event.preventDefault(); mutation.mutate(new FormData(event.currentTarget)); }}>
        <div><h3>Create a project</h3><p>Add the site you want ProActive SEO to monitor.</p></div>
        <label>Project name<input name="name" required /></label>
        <label>Domain/URL<input name="domain" required /></label>
        {mutation.isError && <p role="alert" className="warning-text">{mutation.error.message}</p>}
        <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>{mutation.isPending ? "Creating…" : "Create project"}</Button>
      </form>
    </Card>
  );
}

function Integrations() {
  const accessToken = useWorkspace((state) => state.accessToken);
  const integrations = useQuery({ queryKey: ["integrations", accessToken], queryFn: () => api<ApiRecord[]>("/integrations", { headers: authHeaders(accessToken) }), enabled: Boolean(accessToken) });
  if (integrations.isLoading) return <Skeleton className="integration-grid" />;
  const providers = integrations.data?.data ?? [];
  if (providers.length === 0) return <EmptyState>No integrations yet</EmptyState>;
  return <section className="integration-grid">{providers.map((provider, index) => <Card key={textValue(provider.id, String(index))} className="integration-card"><span className="integration-logo">{textValue(provider.provider ?? provider.name).slice(0, 2)}</span><div><h3>{textValue(provider.provider ?? provider.name)}</h3><p>{textValue(provider.message ?? provider.status)}</p></div><Badge tone={provider.status === "connected" ? "success" : "default"}>{textValue(provider.status)}</Badge></Card>)}</section>;
}

function ContentEditor() {
  const pages = useProjectQuery("pages");
  if (pages.isLoading || pages.projectsLoading) return <Skeleton className="editor-layout" />;
  const page = recordArray(pages.data?.data)[0];
  if (!page) return <EmptyState>No content yet</EmptyState>;
  const googleScore = numberValue(page.google_score ?? page.seo_score);
  const aiScore = numberValue(page.ai_readiness ?? page.ai_score);
  return <section className="editor-layout"><Card className="editor-main"><div className="editor-toolbar"><Button variant="ghost">H1</Button><Button variant="ghost">Bold</Button><Button variant="ghost">Link</Button><span /><Badge>{textValue(page.status)}</Badge></div><input className="editor-title" value={textValue(page.title, "")} readOnly aria-label="Content title" /><textarea value={textValue(page.content ?? page.body, "")} readOnly aria-label="Content body" /></Card><aside className="optimization-panel"><Card><p className="overline">Google score</p><strong>{googleScore}</strong><progress value={googleScore} max="100" /></Card><Card><p className="overline">AI readiness</p><strong>{aiScore}</strong><progress value={aiScore} max="100" /></Card></aside></section>;
}

function SettingsPage() {
  const accessToken = useWorkspace((state) => state.accessToken);
  const organizations = useQuery({ queryKey: ["organizations", accessToken], queryFn: () => api<ApiRecord[]>("/organizations", { headers: authHeaders(accessToken) }), enabled: Boolean(accessToken) });
  if (organizations.isLoading) return <Skeleton className="settings-grid" />;
  const organization = organizations.data?.data[0];
  if (!organization) return <EmptyState>No settings data yet</EmptyState>;
  return <div className="settings-grid"><Card className="settings-nav"><button>Organization</button></Card><Card className="settings-form"><div><h3>Organization profile</h3><p>Manage the workspace identity used in reports and outreach.</p></div><label>Organization name<input value={textValue(organization.name, "")} readOnly /></label><label>Primary domain<input value={textValue(organization.domain, "")} readOnly /></label><label>Default timezone<input value={textValue(organization.timezone, "")} readOnly /></label></Card></div>;
}

function SEOCommandCenter() {
  const dashboard = useProjectQuery("dashboard");
  if (dashboard.isLoading || dashboard.projectsLoading) return <Skeleton className="stats-grid" />;
  const data = (dashboard.data?.data ?? {}) as ApiRecord;
  return (
    <>
      <section className="stats-grid">
        <StatCard label="Keywords tracked" value={textValue(data.keywords_tracked)} delta={textValue(data.keywords_change)} />
        <StatCard label="Avg. position" value={textValue(data.average_position)} delta={textValue(data.position_change)} />
        <StatCard label="SERP features" value={textValue(data.serp_features)} delta={textValue(data.serp_features_change)} />
        <StatCard label="Competitors" value={textValue(data.competitors)} delta={textValue(data.competitors_change)} positive={false} />
      </section>
      <div className="section-spacer" />
      <DataTable route="/seo/keywords" />
    </>
  );
}

function ContentHub() {
  const pages = useProjectQuery("pages");
  if (pages.isLoading || pages.projectsLoading) return <Skeleton className="lower-grid" />;
  const rows = recordArray(pages.data?.data);
  if (rows.length === 0) return <EmptyState>No content yet</EmptyState>;
  return (
    <>
      <section className="stats-grid">
        <StatCard label="Content items" value={String(rows.length)} delta="—" />
        <StatCard label="AI Readiness" value={textValue(rows[0].ai_readiness)} delta={textValue(rows[0].ai_change)} />
        <StatCard label="Google score" value={textValue(rows[0].google_score ?? rows[0].seo_score)} delta={textValue(rows[0].seo_change)} />
        <StatCard label="Decaying articles" value={String(rows.filter((row) => row.status === "decaying").length)} delta="—" positive={false} />
      </section>
      <div className="section-spacer" />
      <section className="lower-grid">
        <Card>
          <div className="card-heading"><div><p className="overline">Dual scoring</p><h3>Content performance</h3></div></div>
          <div className="health-breakdown">{Object.entries(rows[0]).filter(([key]) => key.includes("score") || key.includes("readiness")).map(([key, value]) => <span key={key}><i className="success" /> <b>{key.replaceAll("_", " ")}:</b> {textValue(value)}</span>)}</div>
        </Card>
        <Card>
          <div className="card-heading"><div><p className="overline">Recommended</p><h3>Content briefs</h3></div></div>
          <div className="action-list">{rows.slice(0, 3).map((row, index) => <div key={textValue(row.id, String(index))}><span className={cn("priority", `priority-${index}`)}>{textValue(row.priority, "P")}</span><span><b>{textValue(row.title ?? row.url)}</b><small>{textValue(row.status)}</small></span><Button variant="secondary">Open</Button></div>)}</div>
        </Card>
      </section>
    </>
  );
}

function TechnicalAudit() {
  const issues = useProjectQuery("issues");
  const score = useProjectQuery("technical-score");
  if (issues.isLoading || issues.projectsLoading || score.isLoading) return <Skeleton className="lower-grid" />;
  const rows = recordArray(issues.data?.data);
  const scoreData = (score.data?.data ?? {}) as ApiRecord;
  if (rows.length === 0 && Object.keys(scoreData).length === 0) return <EmptyState>No technical audit data yet</EmptyState>;
  return (
    <>
      <section className="stats-grid">
        <StatCard label="Technical score" value={textValue(scoreData.score ?? scoreData.technical_score)} delta={textValue(scoreData.change)} />
        <StatCard label="Open issues" value={String(rows.length)} delta="—" positive={false} />
        <StatCard label="Critical issues" value={String(rows.filter((row) => row.severity === "critical").length)} delta="—" positive={false} />
        <StatCard label="Resolved issues" value={String(rows.filter((row) => row.status === "resolved").length)} delta="—" />
      </section>
      <div className="section-spacer" />
      <section className="lower-grid">
        <Card>
          <div className="card-heading"><div><p className="overline">Issues</p><h3>Critical findings</h3></div><Link href="/technical/issues">View all</Link></div>
          <div className="action-list">{rows.length === 0 ? <p className="muted">No data yet</p> : rows.slice(0, 4).map((row, index) => <div key={textValue(row.id, String(index))}><span className={cn("priority", `priority-${Math.min(index, 2)}`)}>{textValue(row.severity)}</span><span><b>{textValue(row.title ?? row.message ?? row.type)}</b><small>{textValue(row.url ?? row.status)}</small></span><Button variant="secondary">Review</Button></div>)}</div>
        </Card>
        <Card>
          <div className="card-heading"><div><p className="overline">Self-healing</p><h3>Auto-resolved</h3></div><Badge tone="success">{rows.filter((row) => row.status === "resolved").length} fixed</Badge></div>
          <div className="activity-list">{rows.filter((row) => row.status === "resolved").slice(0, 4).map((row, index) => <p key={textValue(row.id, String(index))}><Check size={14} /> {textValue(row.title ?? row.type)} <time>{textValue(row.resolved_at)}</time></p>)}</div>
        </Card>
      </section>
    </>
  );
}

function AnalyticsPage() {
  const dashboard = useProjectQuery("dashboard");
  const accessToken = useWorkspace((state) => state.accessToken);
  const integrations = useQuery({ queryKey: ["integrations", accessToken], queryFn: () => api<ApiRecord[]>("/integrations", { headers: authHeaders(accessToken) }), enabled: Boolean(accessToken) });
  if (dashboard.isLoading || dashboard.projectsLoading || integrations.isLoading) return <Skeleton className="overview-grid" />;
  const data = (dashboard.data?.data ?? {}) as ApiRecord;
  const trend = recordArray(data.analytics_trend ?? data.traffic_trend ?? data.trend);
  return (
    <>
      <section className="stats-grid">
        <StatCard label="Organic traffic" value={textValue(data.organic_traffic)} delta={textValue(data.traffic_change)} />
        <StatCard label="AI Search visibility" value={textValue(data.ai_search_visibility ?? data.visibility)} delta={textValue(data.visibility_change)} />
        <StatCard label="Click-through rate" value={textValue(data.click_through_rate ?? data.ctr)} delta={textValue(data.ctr_change)} />
        <StatCard label="Bounce rate" value={textValue(data.bounce_rate)} delta={textValue(data.bounce_rate_change)} positive={false} />
      </section>
      <div className="section-spacer" />
      <section className="overview-grid">
        <Card className="trend-card">
          <div className="card-heading"><div><p className="overline">Traffic sources</p><h3>Channel breakdown</h3></div><Badge>Last 30 days</Badge></div>
          <div className="chart-wrap" role="img" aria-label="Traffic by channel">
            {trend.length === 0 ? <p className="muted">No data yet</p> : <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{top:12,right:8,bottom:0,left:-20}}>
                <defs>
                  <linearGradient id="organic" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6366f1" stopOpacity={0.28} /><stop offset="100%" stopColor="#6366f1" stopOpacity={0} /></linearGradient>
                  <linearGradient id="ai" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#10b981" stopOpacity={0.28} /><stop offset="100%" stopColor="#10b981" stopOpacity={0} /></linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-default)" />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{fill:"var(--ink-tertiary)",fontSize:11}} />
                <YAxis axisLine={false} tickLine={false} tick={{fill:"var(--ink-tertiary)",fontSize:11}} />
                <Tooltip contentStyle={{background:"var(--bg-surface-raised)",border:"1px solid var(--border-default)",borderRadius:6,fontSize:12}} />
                <Area type="monotone" dataKey="organic" stroke="#6366f1" strokeWidth={2} fill="url(#organic)" isAnimationActive={false} name="Organic" />
                <Area type="monotone" dataKey="ai" stroke="#10b981" strokeWidth={2} fill="url(#ai)" isAnimationActive={false} name="AI Search" />
              </AreaChart>
            </ResponsiveContainer>}
          </div>
        </Card>
        <Card>
          <div className="card-heading"><div><p className="overline">Integrations</p><h3>Connection status</h3></div></div>
          <div className="activity-list">{(integrations.data?.data ?? []).length === 0 ? <p className="muted">No data yet</p> : (integrations.data?.data ?? []).slice(0, 4).map((item, index) => <p key={textValue(item.id, String(index))}><Check size={14} color="var(--ink-success)" /> {textValue(item.provider ?? item.name)} — {textValue(item.status)} <time>{textValue(item.updated_at)}</time></p>)}</div>
        </Card>
      </section>
    </>
  );
}

function ReportsPage() {
  const accessToken = useWorkspace((state) => state.accessToken);
  const reports = useQuery({ queryKey: ["reports", accessToken], queryFn: () => api<ApiRecord[]>("/reports", { headers: authHeaders(accessToken) }), enabled: Boolean(accessToken) });
  const summary = useQuery({ queryKey: ["reports-summary", accessToken], queryFn: () => api<ApiRecord>("/reports/summary", { headers: authHeaders(accessToken) }), enabled: Boolean(accessToken) });
  if (reports.isLoading || summary.isLoading) return <Skeleton className="table-card" />;
  const rows = reports.data?.data ?? [];
  const data = summary.data?.data ?? {};
  if (rows.length === 0 && Object.keys(data).length === 0) return <EmptyState>No reports yet</EmptyState>;
  return (
    <>
      <section className="stats-grid">
        <StatCard label="Scheduled reports" value={textValue(data.scheduled_reports ?? rows.length)} delta={textValue(data.scheduled_change)} />
        <StatCard label="Last generated" value={textValue(data.last_generated)} delta="—" />
        <StatCard label="Export formats" value={textValue(data.export_formats)} delta="—" />
        <StatCard label="Automated" value={textValue(data.automation_frequency)} delta="—" />
      </section>
      <div className="section-spacer" />
      <Card className="table-card">
        <div className="card-heading"><div><p className="overline">Report library</p><h3>Generated reports</h3></div><Button variant="secondary">Generate new</Button></div>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Report</th><th>Period</th><th>Format</th><th>Generated</th><th>Status</th></tr></thead>
            <tbody>{rows.map((report, index) => <tr key={textValue(report.id, String(index))}><td>{textValue(report.name ?? report.title)}</td><td>{textValue(report.period)}</td><td>{textValue(report.format)}</td><td>{textValue(report.generated_at ?? report.created_at)}</td><td><Badge tone={report.status === "ready" ? "success" : "default"}>{textValue(report.status)}</Badge></td></tr>)}</tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

function RouteContent({ route }: { route: string }) {
  if (route === "/overview" || route === "/") return <Overview />;
  if (route === "/projects/new") return <NewProject />;
  if (route === "/agents" || /^\/agents\/[^/]+$/.test(route)) return <AgentCenter />;
  if (route.startsWith("/campaigns")) return route === "/campaigns" ? <CampaignBoard /> : <DataTable route={route} />;
  if (route.startsWith("/settings/integrations")) return <Integrations />;
  if (route.startsWith("/settings")) return <SettingsPage />;
  if (route.startsWith("/content/editor")) return <ContentEditor />;
  if (route.startsWith("/seo/overview") || route.startsWith("/seo")) return <SEOCommandCenter />;
  if (route.startsWith("/content/briefs") || route.startsWith("/content")) return <ContentHub />;
  if (route.startsWith("/technical/audit") || route.startsWith("/technical")) return <TechnicalAudit />;
  if (route.startsWith("/analytics")) return <AnalyticsPage />;
  if (route === "/reports") return <ReportsPage />;
  if (route.includes("keywords") || route.includes("pages") || route.includes("issues") || route.startsWith("/reports")) return <DataTable route={route} />;
  return <><Overview /><div className="section-spacer" /><DataTable route={route} /></>;
}

export function ProductApp({ route }: { route: string }) {
  const accessToken = useWorkspace((state) => state.accessToken);
  const users = useQuery({
    queryKey: ["users", accessToken],
    queryFn: () => api<Array<{ name?: string }>>("/users", { headers: { Authorization: `Bearer ${accessToken}` } }),
    enabled: Boolean(accessToken)
  });
  const projects = useQuery({
    queryKey: ["projects", accessToken],
    queryFn: () => api<Array<{ name?: string; plan?: string }>>("/projects", { headers: { Authorization: `Bearer ${accessToken}` } }),
    enabled: Boolean(accessToken)
  });
  const projectName = projects.data?.data[0]?.name ?? "";
  if (["/login", "/register", "/forgot-password", "/verify-email"].includes(route)) return <AuthPage route={route} />;
  const userName = users.data?.data[0]?.name ?? "";
  const [title, description] = titleFor(route, userName);
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <Sidebar route={route} />
      <div className="main-column">
        <Header />
        <main id="main-content" className="page-content">
          <header className="page-header"><div><p className="breadcrumb">{projectName} <span>/</span> {route.split("/").filter(Boolean).join(" / ")}</p><h1>{title}</h1><p>{description}</p></div><div className="page-actions"><Button variant="secondary">Export</Button><Button><Plus size={15} /> New action</Button></div></header>
          <RouteContent route={route} />
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}
