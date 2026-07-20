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
  Link2,
  Menu,
  Moon,
  MoreHorizontal,
  Plus,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
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

const TREND = [
  { day: "Jul 13", visibility: 61, health: 77 },
  { day: "Jul 14", visibility: 63, health: 78 },
  { day: "Jul 15", visibility: 62, health: 79 },
  { day: "Jul 16", visibility: 67, health: 81 },
  { day: "Jul 17", visibility: 69, health: 82 },
  { day: "Jul 18", visibility: 72, health: 84 },
  { day: "Jul 19", visibility: 74, health: 87 }
];

const AGENTS = [
  ["Sentinel", "Crawl", "Scanning 2,481 pages", "active"],
  ["Forge", "Content", "12 briefs ready", "active"],
  ["Technical", "Technical", "3 fixes awaiting approval", "attention"],
  ["Scout", "Rank", "1,204 keywords tracked", "active"],
  ["Outreach", "Backlinks", "18 scheduled follow-ups", "paused"],
  ["Competitor", "Competitor", "4 new opportunities", "active"],
  ["Decision", "Orchestration", "Queue healthy", "active"],
  ["Executor", "Actions", "Safe mode enabled", "attention"]
] as const;

const CAMPAIGNS = [
  { name: "HARO — AI search study", type: "HARO", sent: 24, replies: 7, links: 2, status: "Active" },
  { name: "Q3 broken links", type: "Broken link", sent: 61, replies: 11, links: 6, status: "Active" },
  { name: "Developer publications", type: "Guest post", sent: 18, replies: 5, links: 1, status: "Paused" },
  { name: "Acme mentions", type: "Unlinked mention", sent: 31, replies: 12, links: 9, status: "Active" }
] as const;

function titleFor(route: string) {
  if (route === "/overview") return ["Good morning, Maya", "Here’s what your agents improved while you were away."];
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
        setAccessToken(response.data.tokens.access_token);
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
          <p>Eight specialized agents automate 87% of recurring SEO work while your team controls every consequential change.</p>
          <div className="trust-row"><ShieldCheck size={18} /> Tenant isolated · Approval gated · Fully audited</div>
        </div>
        <p className="auth-footnote">Trusted workflows for 2,400+ monitored sites</p>
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
  const { sidebarOpen, toggleSidebar, accessToken } = useWorkspace();
  const streamStatus = useSSE(`${API_URL}/stream/agents`, accessToken);
  return (
    <>
      {sidebarOpen && <button className="scrim" aria-label="Close navigation" onClick={toggleSidebar} />}
      <aside className={cn("sidebar", sidebarOpen && "sidebar-open")}>
        <div className="sidebar-brand"><span className="brand-mark">P</span><span>ProActive SEO</span><button className="mobile-close" onClick={toggleSidebar} aria-label="Close navigation"><X size={18} /></button></div>
        <div className="project-switcher"><span className="project-avatar">A</span><span><b>Acme.com</b><small>Professional</small></span><ChevronDown size={15} /></div>
        <nav aria-label="Primary navigation">
          {NAVIGATION.map((item) => {
            const Icon = icons[item.icon];
            const active = route === item.href || (item.href !== "/overview" && route.startsWith(item.href.split("/").slice(0, 2).join("/")));
            return <Link key={item.href} href={item.href} className={cn("nav-link", active && "nav-link-active")}><Icon size={17} /><span>{item.label}</span></Link>;
          })}
        </nav>
        <div className="sidebar-status"><span className="status-dot" /><span><b>{streamStatus === "connected" ? "Live agent stream" : "8 agents configured"}</b><small>{streamStatus === "error" ? "Reconnecting…" : streamStatus === "connecting" ? "Connecting…" : "Event bus ready"}</small></span></div>
        <div className="sidebar-user"><span className="user-avatar">MC</span><span><b>Maya Chen</b><small>Owner</small></span><MoreHorizontal size={16} /></div>
      </aside>
    </>
  );
}

function Header() {
  const { toggleSidebar, setCommandOpen } = useWorkspace();
  const [dark, setDark] = useState(false);
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
        <button className="avatar-button" aria-label="Open profile">MC</button>
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
  return (
    <>
      <section className="stats-grid">
        <StatCard label="SEO health" value="87 / 100" delta="4.2%" />
        <StatCard label="AI Search visibility" value="74.3%" delta="6.8%" />
        <StatCard label="Keywords in top 10" value="286" delta="23" />
        <StatCard label="Open critical issues" value="7" delta="2" positive={false} />
      </section>
      <section className="overview-grid">
        <Card className="trend-card">
          <div className="card-heading"><div><p className="overline">Search performance</p><h3>Visibility trend</h3></div><Badge>Last 7 days</Badge></div>
          <div className="chart-wrap" role="img" aria-label="Visibility increased from 61 to 74 percent">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={TREND} margin={{ top: 12, right: 8, bottom: 0, left: -20 }}>
                <defs><linearGradient id="visibility" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6366f1" stopOpacity={0.28} /><stop offset="100%" stopColor="#6366f1" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-default)" />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: "var(--ink-tertiary)", fontSize: 11 }} />
                <YAxis axisLine={false} tickLine={false} domain={[50, 90]} tick={{ fill: "var(--ink-tertiary)", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "var(--bg-surface-raised)", border: "1px solid var(--border-default)", borderRadius: 6, fontSize: 12 }} />
                <Area type="monotone" dataKey="visibility" stroke="#6366f1" strokeWidth={2} fill="url(#visibility)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card className="health-card">
          <div className="card-heading"><div><p className="overline">Site condition</p><h3>Health score</h3></div><CircleGauge size={20} /></div>
          <div className="health-ring"><span>87</span><small>Excellent</small></div>
          <div className="health-breakdown"><span><i className="success" /> 184 passed</span><span><i className="warning" /> 26 warnings</span><span><i className="danger" /> 7 critical</span></div>
        </Card>
      </section>
      <section className="lower-grid">
        <Card>
          <div className="card-heading"><div><p className="overline">Decision queue</p><h3>Recommended actions</h3></div><Link href="/activity">View all</Link></div>
          <div className="action-list">
            {["Approve 3 canonical tag fixes", "Refresh 12 decaying articles", "Review competitor keyword gap"].map((item, index) => <div key={item}><span className={cn("priority", `priority-${index}`)}>P{index}</span><span><b>{item}</b><small>{index === 0 ? "Technical · 8 min" : index === 1 ? "Forge · 24 min" : "Competitor · 6 min"}</small></span><Button variant="secondary">Review</Button></div>)}
          </div>
        </Card>
        <Card>
          <div className="card-heading"><div><p className="overline">Live operations</p><h3>Agent activity</h3></div><span className="live-label"><i /> Live</span></div>
          <div className="activity-list">
            <p><Check size={14} /> Sentinel completed a 2,481-page crawl <time>2m</time></p>
            <p><Sparkles size={14} /> Forge improved “Enterprise SEO guide” <time>8m</time></p>
            <p><Link2 size={14} /> Outreach verified two new backlinks <time>14m</time></p>
            <p><ArrowUpRight size={14} /> Scout detected 11 ranking gains <time>21m</time></p>
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
  const rows = remote.length
    ? remote.map((agent) => [agent.name ?? agent.key ?? "Agent", agent.role ?? "SEO", "Connected to the execution queue", agent.status ?? "active"] as const)
    : AGENTS;
  return <section className="agent-grid">{rows.map(([name, role, detail, status]) => <Card key={name} className="agent-card"><div className="agent-head"><span className="agent-icon"><Bot size={19} /></span><Badge tone={status === "active" ? "success" : status === "paused" ? "default" : "warning"}>{status}</Badge></div><div><h3>{name}</h3><p>{role} agent</p></div><p className="agent-detail">{detail}</p><div className="agent-foot"><span><i className={status} /> {status === "active" ? "Running" : status === "paused" ? "Paused" : "Review"}</span><Link href={`/agents/${name.toLowerCase()}`}>Open →</Link></div></Card>)}</section>;
}

function CampaignBoard() {
  const columns = ["Draft", "Sent", "Replied", "Negotiating", "Live", "Rejected"];
  return <div className="kanban" role="region" aria-label="Campaign prospect board" tabIndex={0}>{columns.map((column, index) => <section key={column} className="kanban-column"><header><span>{column}</span><Badge>{index === 1 ? 18 : index === 4 ? 6 : index + 2}</Badge></header>{CAMPAIGNS.slice(0, index % 3 === 0 ? 2 : 1).map((campaign) => <article key={`${column}-${campaign.name}`}><Badge tone={campaign.type === "HARO" ? "primary" : "default"}>{campaign.type}</Badge><h4>{campaign.name}</h4><p>{campaign.replies} replies · {campaign.links} links</p><small>Next action {index + 1}d</small></article>)}</section>)}</div>;
}

function DataTable({ route }: { route: string }) {
  const rows = route.includes("keyword")
    ? [["enterprise seo platform", "4", "+3", "8,100", "72"], ["automated seo tools", "11", "+8", "3,600", "64"], ["agentic seo", "2", "0", "1,900", "48"]]
    : CAMPAIGNS.map((item) => [item.name, item.type, String(item.sent), String(item.replies), item.status]);
  const headers = route.includes("keyword") ? ["Keyword", "Position", "Change", "Volume", "Difficulty"] : ["Campaign", "Type", "Sent", "Replies", "Status"];
  return <Card className="table-card"><div className="filter-row"><label><Search size={15} /><input placeholder="Search and filter…" /></label><Button variant="secondary">Filters</Button></div><div className="table-scroll"><table><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row[0]}>{row.map((cell, index) => <td key={`${row[0]}-${index}`}>{index === row.length - 1 ? <Badge tone={cell === "Active" ? "success" : "default"}>{cell}</Badge> : cell}</td>)}</tr>)}</tbody></table></div></Card>;
}

function Integrations() {
  const providers = ["GSC", "GA4", "Bing", "Yandex", "Naver", "Gmail", "Exa", "Tavily", "DataForSEO", "PageSpeed", "WordPress", "Webflow", "Shopify"];
  return <section className="integration-grid">{providers.map((provider, index) => <Card key={provider} className="integration-card"><span className="integration-logo">{provider.slice(0, 2)}</span><div><h3>{provider}</h3><p>{index < 3 ? "Connected and syncing" : "Available to connect"}</p></div><Badge tone={index < 3 ? "success" : "default"}>{index < 3 ? "Connected" : "Connect"}</Badge></Card>)}</section>;
}

function ContentEditor() {
  return <section className="editor-layout"><Card className="editor-main"><div className="editor-toolbar"><Button variant="ghost">H1</Button><Button variant="ghost">Bold</Button><Button variant="ghost">Link</Button><span /><Badge>Saved</Badge></div><input className="editor-title" defaultValue="The Enterprise Guide to Agentic SEO" aria-label="Content title" /><textarea defaultValue={"Search is no longer a single results page. Modern teams need an operating system that makes decisions across traditional rankings, AI answers, and technical performance.\n\nProActive SEO coordinates specialized agents so every recommendation is evidence-led, reviewable, and measurable."} aria-label="Content body" /></Card><aside className="optimization-panel"><Card><p className="overline">Google score</p><strong>86</strong><progress value="86" max="100" /></Card><Card><p className="overline">AI readiness</p><strong>79</strong><progress value="79" max="100" /></Card><Card><h4>Optimization cues</h4><p><Check size={14} /> Target keyword in H1</p><p><Check size={14} /> Entity definitions are clear</p><p className="warning-text">Add two authoritative citations</p></Card></aside></section>;
}

function SettingsPage() {
  return <div className="settings-grid"><Card className="settings-nav">{["Profile", "Organization", "Team", "Billing", "API keys", "Notifications", "Security", "Integrations"].map((item) => <button key={item}>{item}</button>)}</Card><Card className="settings-form"><div><h3>Organization profile</h3><p>Manage the workspace identity used in reports and outreach.</p></div><label>Organization name<input defaultValue="Acme Inc." /></label><label>Primary domain<input defaultValue="https://acme.com" /></label><label>Default timezone<select defaultValue="UTC"><option>UTC</option><option>Asia/Makassar</option></select></label><div className="form-actions"><Button variant="secondary">Cancel</Button><Button>Save changes</Button></div></Card></div>;
}

function SEOCommandCenter() {
  return (
    <section className="stats-grid">
      <StatCard label="Keywords tracked" value="1,204" delta="5.2%" />
      <StatCard label="Avg. position" value="4.8" delta="0.3" />
      <StatCard label="SERP features" value="38" delta="7" />
      <StatCard label="Competitors" value="6" delta="1" positive={false} />
    </section>
  );
}

function ContentHub() {
  return (
    <section className="stats-grid">
      <StatCard label="Content briefs" value="12" delta="3" />
      <StatCard label="AI Readiness" value="79 / 100" delta="5.1%" />
      <StatCard label="Google score" value="86 / 100" delta="2.3%" />
      <StatCard label="Decaying articles" value="4" delta="2" positive={false} />
    </section>
  );
}

function TechnicalAudit() {
  return (
    <section className="stats-grid">
      <StatCard label="Crawl errors" value="3" delta="1" positive={false} />
      <StatCard label="Core Web Vitals" value="Pass" delta="2 sites" />
      <StatCard label="Schema coverage" value="68%" delta="12%" />
      <StatCard label="Broken links" value="7" delta="3" positive={false} />
    </section>
  );
}

function AnalyticsPage() {
  return (
    <section className="stats-grid">
      <StatCard label="Organic traffic" value="24.8K" delta="8.3%" />
      <StatCard label="AI Search visibility" value="74.3%" delta="6.8%" />
      <StatCard label="Click-through rate" value="4.2%" delta="0.3%" />
      <StatCard label="Bounce rate" value="38%" delta="2%" positive={false} />
    </section>
  );
}

function ReportsPage() {
  return (
    <section className="stats-grid">
      <StatCard label="Scheduled reports" value="6" delta="2" />
      <StatCard label="Last generated" value="2h ago" delta="-" />
      <StatCard label="Export formats" value="PDF, CSV" delta="-" />
      <StatCard label="Automated" value="Weekly" delta="-" />
    </section>
  );
}

function RouteContent({ route }: { route: string }) {
  if (route === "/overview" || route === "/") return <Overview />;
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
  if (["/login", "/register", "/forgot-password", "/verify-email"].includes(route)) return <AuthPage route={route} />;
  const [title, description] = titleFor(route);
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <Sidebar route={route} />
      <div className="main-column">
        <Header />
        <main id="main-content" className="page-content">
          <header className="page-header"><div><p className="breadcrumb">Acme.com <span>/</span> {route.split("/").filter(Boolean).join(" / ")}</p><h1>{title}</h1><p>{description}</p></div><div className="page-actions"><Button variant="secondary">Export</Button><Button><Plus size={15} /> New action</Button></div></header>
          <RouteContent route={route} />
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}
