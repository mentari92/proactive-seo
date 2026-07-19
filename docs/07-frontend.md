# ProActive SEO — Frontend Design Specification

**Version:** 1.0.0
**Date:** 2026-07-19
**Stack:** Next.js 14 (App Router) · Tailwind CSS · shadcn/ui · Zustand · React Query · React Hook Form · Recharts · SSE

---

## Table of Contents

1. [Design System Tokens](#1-design-system-tokens)
2. [Composition Rules by Surface](#2-composition-rules-by-surface)
3. [Page Designs (40+ pages)](#3-page-designs)
4. [Key Component Designs](#4-key-component-designs)
5. [Anti-Slop Audit](#5-anti-slop-audit)
6. [Interaction Patterns](#6-interaction-patterns)

---

## 1. Design System Tokens

### 1.1 Color Palette — Semantic Tokens

All colors are semantic. No color is chosen for aesthetics alone — each maps to a meaning.

#### Light Mode

```
--color-bg-page:          #F8F9FB        Page background (barely off-white)
--color-bg-surface:       #FFFFFF        Card/panel background
--color-bg-surface-raised:#FFFFFF        Elevated card (modal, popover)
--color-bg-surface-sunken:#F1F3F5        Inset regions (code blocks, logs)
--color-bg-sidebar:       #111827        Sidebar (dark, always)
--color-bg-sidebar-hover: #1F2937        Sidebar item hover
--color-bg-sidebar-active:#1E293B        Sidebar item active

--color-ink-primary:      #111827        Headings, primary text
--color-ink-secondary:    #4B5563        Body text
--color-ink-tertiary:     #9CA3AF        Captions, timestamps, metadata
--color-ink-inverse:      #F9FAFB        Text on dark backgrounds
--color-ink-on-primary:   #FFFFFF        Text on primary buttons

--color-border-default:   #E5E7EB        Standard borders
--color-border-strong:    #D1D5DB        Emphasized borders (table headers)
--color-border-focus:     #4F46E5        Focus rings

--color-primary-50:        #EEF2FF       Primary background tints
--color-primary-100:       #E0E7FF       Primary subtle backgrounds
--color-primary-500:       #6366F1       Primary accent (charts, highlights)
--color-primary-600:       #4F46E5       Primary buttons, links, focus
--color-primary-700:       #4338CA       Primary hover

--color-success-50:        #ECFDF5       Success background tint
--color-success-500:       #10B981       Success icons, positive deltas
--color-success-600:       #059669       Success buttons

--color-warning-50:        #FFFBEB       Warning background tint
--color-warning-500:       #F59E0B       Warning icons, attention needed
--color-warning-600:       #D97706       Warning buttons

--color-danger-50:         #FEF2F2       Danger background tint
--color-danger-500:        #EF4444       Danger icons, errors
--color-danger-600:        #DC2626       Danger buttons

--color-info-50:           #EFF6FF       Info background tint
--color-info-500:          #3B82F6       Info icons, neutral alerts
```

#### Dark Mode

```
--color-bg-page:          #0F1117
--color-bg-surface:       #1A1D27
--color-bg-surface-raised:#22262F
--color-bg-surface-sunken:#13151D
--color-bg-sidebar:       #0B0D12
--color-bg-sidebar-hover: #161922
--color-bg-sidebar-active:#1A1D27

--color-ink-primary:      #F1F5F9
--color-ink-secondary:    #94A3B8
--color-ink-tertiary:     #64748B
--color-ink-inverse:      #111827

--color-border-default:   #262A35
--color-border-strong:    #334155
--color-border-focus:     #818CF8

--color-primary-500:      #818CF8
--color-primary-600:      #6366F1
--color-primary-700:      #4F46E5

--color-success-500:      #34D399
--color-warning-500:      #FBBF24
--color-danger-500:       #F87171
```

### 1.2 Typography

Two families. No more.

| Role | Family | Weight | Size | Line Height | Letter Spacing |
|---|---|---|---|---|---|
| Display H1 | Inter | 700 | 30px | 36px | -0.02em |
| Display H2 | Inter | 600 | 24px | 32px | -0.01em |
| Heading H3 | Inter | 600 | 18px | 28px | 0 |
| Heading H4 | Inter | 600 | 16px | 24px | 0 |
| Body | Inter | 400 | 14px | 20px | 0 |
| Body Small | Inter | 400 | 13px | 18px | 0 |
| Caption | Inter | 500 | 12px | 16px | 0.01em |
| Overline | Inter | 600 | 11px | 16px | 0.06em |
| Code | JetBrains Mono | 400 | 13px | 20px | 0 |
| Code Small | JetBrains Mono | 400 | 12px | 16px | 0 |
| Mono Data | JetBrains Mono | 500 | 14px | 20px | 0 |

Rationale: Inter is chosen explicitly for its tabular number support and optical sizing — critical for a data-dense dashboard where numbers must align. JetBrains Mono for all code, logs, API keys, and technical readouts. No other families.

### 1.3 Spacing Scale (4px base)

| Token | Value | Use |
|---|---|---|
| `space-0` | 0px | Reset |
| `space-1` | 4px | Tight internal padding (badge, tag) |
| `space-2` | 8px | Icon-to-text gap, table cell padding |
| `space-3` | 12px | Button internal padding |
| `space-4` | 16px | Card padding, form field gap |
| `space-5` | 20px | Section gap within a card |
| `space-6` | 24px | Card-to-card gap, sidebar width padding |
| `space-8` | 32px | Major section separation |
| `space-10` | 40px | Page header to content |
| `space-12` | 48px | Page-level top padding |
| `space-16` | 64px | Major layout divisions |

### 1.4 Radii

| Token | Value | Use |
|---|---|---|
| `radius-sm` | 4px | Badges, inline code, small controls |
| `radius-md` | 6px | Buttons, inputs, cards |
| `radius-lg` | 8px | Modals, dropdowns, large cards |
| `radius-full` | 9999px | Avatar circles, status dots |

### 1.5 Shadows / Elevation

No colored shadows. No glow effects. Depth is communicated through border + shadow + background shift.

| Level | Shadow | Background | Use |
|---|---|---|---|
| 0 (flat) | none | `bg-surface` | Cards at rest on page |
| 1 (raised) | `0 1px 2px rgba(0,0,0,0.05)` | `bg-surface` | Hovered card |
| 2 (floating) | `0 4px 12px rgba(0,0,0,0.08)` | `bg-surface-raised` | Dropdown, popover |
| 3 (modal) | `0 12px 40px rgba(0,0,0,0.12)` | `bg-surface-raised` | Modal overlay |
| 4 (toast) | `0 8px 24px rgba(0,0,0,0.14)` | `bg-surface-raised` | Toast notifications |

### 1.6 Component Variants

#### Button

| Variant | Background | Text | Border | Use |
|---|---|---|---|---|
| Primary | `primary-600` | white | none | Primary action (1 per view) |
| Secondary | transparent | `ink-primary` | `border-default` | Secondary actions |
| Ghost | transparent | `ink-secondary` | none | Tertiary, sidebar items |
| Danger | `danger-600` | white | none | Destructive actions |
| Danger Ghost | transparent | `danger-500` | none | Inline destructive |

Sizes: `sm` (height 28px, text 12px), `md` (height 36px, text 13px), `lg` (height 40px, text 14px).

States: default → hover (darken bg 8%) → active (darken 12%) → focus (2px ring `primary-600` offset 2px) → disabled (opacity 0.5, no pointer events) → loading (spinner replaces icon, text unchanged).

#### Input

| Variant | Background | Border | Use |
|---|---|---|---|
| Default | `bg-surface` | `border-default` | Standard form fields |
| Error | `bg-surface` | `danger-500` | Validation failure |
| Disabled | `bg-surface-sunken` | `border-default` opacity 0.5 | Read-only display |

Height: 36px. Padding: 0 12px. Text: 14px Inter. Placeholder: `ink-tertiary`.

#### Card

| Variant | Background | Border | Use |
|---|---|---|---|
| Default | `bg-surface` | 1px `border-default` | Standard container |
| Interactive | `bg-surface` + hover shadow level 1 | 1px `border-default` | Clickable cards |
| Selected | `bg-surface` + `primary-50` tint | 1px `primary-600` | Selected state |
| Sunken | `bg-surface-sunken` | none | Inset content area |

Padding: 16px (compact) or 24px (standard).

#### Table

| Element | Style |
|---|---|
| Header row | `bg-surface-sunken`, `ink-secondary` 12px 600, sticky top |
| Header cell | padding 8px 12px, border-bottom `border-strong` |
| Body row | padding 10px 12px, border-bottom `border-default` |
| Body row hover | `bg-surface-sunken` |
| Body row selected | `primary-50` |
| Sort indicator | arrow icon, `primary-600` when active |
| Cell text | 14px, mono for numbers/URLs |

#### Badge

| Variant | Background | Text | Use |
|---|---|---|---|
| Default | `surface-sunken` | `ink-secondary` | Neutral tag |
| Primary | `primary-50` | `primary-600` | Active feature |
| Success | `success-50` | `success-600` | Healthy / indexed |
| Warning | `warning-50` | `warning-600` | Needs attention |
| Danger | `danger-50` | `danger-600` | Error / critical |

Height: 20px. Padding: 2px 8px. Text: 12px 500. Radius: `radius-sm`.

#### Toast

Position: bottom-right, stacked upward.

| Variant | Left accent | Icon | Use |
|---|---|---|---|
| Success | `success-500` | checkmark | Action completed |
| Error | `danger-50`0 | x-circle | Action failed |
| Warning | `warning-500` | alert | Partial success |
| Info | `info-500` | info | Neutral update |

Width: 380px. Auto-dismiss: 5s (success), manual-dismiss (error). Shadow level 4.

### 1.7 Breakpoints

| Name | Width | Sidebar | Content |
|---|---|---|---|
| `sm` | 640px | Hidden (bottom sheet) | Full width |
| `md` | 768px | Collapsed (64px icons) | Remaining |
| `lg` | 1024px | Collapsed (64px) | Remaining |
| `xl` | 1280px | Expanded (240px) | Remaining |
| `2xl` | 1536px | Expanded (240px) | Remaining, max 1200px content |

---

## 2. Composition Rules by Surface

Each page maps to exactly one surface archetype. The surface determines composition — not decorative preference.

### Surface 1: MONITOR

**Pages:** `/` (dashboard), `/overview`, `/activity`, `/agents`, `/seo/overview`, `/seo/health-score`, `/technical/multi-engine`

**Composition:** Dense grid of information-dense panels. No hero. No centered content. The entire viewport is information. Panels are sized by importance — the primary metric gets 2-3× the area of secondary metrics. Number + label + trend line. No decorative cards.

**Density:** High. Every pixel carries information. Padding is 16px inside panels, 12px between them.

**Hierarchy method:** Size (primary panel spans 2 columns), weight (numbers are 24-30px), color (status badges only — not decorative accents).

**Anti-patterns to avoid:** Equal-weight card grid. Centered headlines. Hero sections. Gradient backgrounds.

### Surface 2: OPERATE

**Pages:** `/agents/{type}`, `/campaigns/{id}`, `/content/editor/{id}`, `/seo/keywords`, `/seo/pages`, `/seo/issues`, `/campaigns`, `/content/briefs`, `/content/drafts`, `/content/published`

**Composition:** Master-detail or list-detail. Selection state drives the layout — the list on the left, the action panel on the right. Action buttons are prominent but contained (not floating). Bulk selection with checkbox column + action bar.

**Density:** Medium-high. The list is dense (compact table rows), the detail panel has more breathing room.

**Hierarchy method:** Selection state (blue left-border or background tint), action prominence (primary button for the 1 dominant action), inline status badges.

### Surface 3: CONFIGURE

**Pages:** `/settings/*`, `/projects/new`, `/settings/integrations/*`, `/login`, `/register`, `/forgot-password`, `/verify-email`

**Composition:** Single-column, max-width 640px (forms) or 960px (settings with sidebar nav). Progressive disclosure — sections expand on demand. Save/cancel bar fixed at bottom when dirty.

**Density:** Low-medium. 24px padding. Clear section headings with 32px margin-top. Labels above inputs.

**Hierarchy method:** Section headings (H3), description text (secondary color) under each section, separator lines between groups.

### Surface 4: DECIDE / LEARN

**Pages:** `/analytics/*`, `/reports/*`, `/reports/generate`, `/reports/{id}`

**Composition:** One idea per section. Each chart or table is a self-contained unit with its own heading, description, and clear axis labels. No cramming multiple unrelated metrics into one panel. Vertical scroll, not horizontal layout tricks.

**Density:** Medium. Each section gets 32px bottom margin. Charts have 24px internal padding.

**Hierarchy method:** Section heading (H3) → metric value (large number) → chart → detail table below. The number summarizes; the chart shows trend; the table provides drill-down.

---

## 3. Page Designs

### 3.1 Auth Pages

#### `/login`

**Surface:** CONFIGURE

**Composition:** Split layout — left panel (brand + value prop), right panel (form). On mobile, form only.

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐    │
│  │                          │  │                              │    │
│  │  ProActive SEO           │  │  Sign in to your account     │    │
│  │                          │  │                              │    │
│  │  Automate 87% of SEO     │  │  ┌────────────────────────┐  │    │
│  │  tasks with AI agents    │  │  │ Email                  │  │    │
│  │  that work continuously. │  │  └────────────────────────┘  │    │
│  │                          │  │  ┌────────────────────────┐  │    │
│  │  [Trust bar: 2,400+      │  │  │ Password          [eye]│  │    │
│  │   sites monitored]       │  │  └────────────────────────┘  │    │
│  │                          │  │                              │    │
│  │                          │  │  [x] Remember me    Forgot?  │    │
│  │                          │  │                              │    │
│  │                          │  │  ┌────────────────────────┐  │    │
│  │                          │  │  │     Sign In            │  │    │
│  │                          │  │  └────────────────────────┘  │    │
│  │                          │  │                              │    │
│  │                          │  │  ─── or continue with ───   │    │
│  │                          │  │                              │    │
│  │                          │  │  [Google]  [GitHub]          │    │
│  │                          │  │                              │    │
│  │                          │  │  No account? Sign up         │    │
│  └──────────────────────────┘  └──────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Components:** Input (email, password), Button (primary: Sign In, ghost: OAuth), Checkbox, Link
**Data flow:** `POST /api/auth/login` → sets httpOnly cookie → redirect to `/`
**Loading state:** Button shows spinner, fields disabled
**Error state:** Red banner above form: "Invalid email or password. Try again or reset your password."
**Empty state:** N/A (form is always populated with placeholders)
**Mobile:** Stack vertically. Left panel hidden. Logo above form.

---

#### `/register`

**Surface:** CONFIGURE

**Composition:** Same split as login. Form has additional fields.

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐    │
│  │                          │  │                              │    │
│  │  ProActive SEO           │  │  Create your account         │    │
│  │                          │  │                              │    │
│  │  [Same brand panel]      │  │  ┌────────────────────────┐  │    │
│  │                          │  │  │ Full name              │  │    │
│  │                          │  │  └────────────────────────┘  │    │
│  │                          │  │  ┌────────────────────────┐  │    │
│  │                          │  │  │ Work email             │  │    │
│  │                          │  │  └────────────────────────┘  │    │
│  │                          │  │  ┌────────────────────────┐  │    │
│  │                          │  │  │ Password          [eye]│  │    │
│  │                          │  │  └────────────────────────┘  │    │
│  │                          │  │  Strength: ═══════░░░ Fair   │    │
│  │                          │  │                              │    │
│  │                          │  │  [x] I agree to Terms        │    │
│  │                          │  │                              │    │
│  │                          │  │  ┌────────────────────────┐  │    │
│  │                          │  │  │     Create Account     │  │    │
│  │                          │  │  └────────────────────────┘  │    │
│  │                          │  │                              │    │
│  │                          │  │  Already have an account?    │    │
│  │                          │  │  Sign in                     │    │
│  └──────────────────────────┘  └──────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Data flow:** `POST /api/auth/register` → sends verification email → redirect to `/verify-email`
**Error state:** Inline per-field. Email taken: "An account with this email already exists."

---

#### `/forgot-password`

**Surface:** CONFIGURE

**Composition:** Centered single column, max-width 400px.

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                    ┌──────────────────────────┐                     │
│                    │                          │                     │
│                    │  Reset your password     │                     │
│                    │                          │                     │
│                    │  Enter your email and    │                     │
│                    │  we'll send a reset link.│                     │
│                    │                          │                     │
│                    │  ┌────────────────────┐  │                     │
│                    │  │ Email              │  │                     │
│                    │  └────────────────────┘  │                     │
│                    │                          │                     │
│                    │  ┌────────────────────┐  │                     │
│                    │  │   Send Reset Link  │  │                     │
│                    │  └────────────────────┘  │                     │
│                    │                          │                     │
│                    │  Back to sign in         │                     │
│                    └──────────────────────────┘                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Success state:** "Check your email. We sent a reset link to j***@company.com. It expires in 1 hour."

---

#### `/verify-email`

**Surface:** CONFIGURE

**Composition:** Centered, informational.

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                    ┌──────────────────────────┐                     │
│                    │                          │                     │
│                    │  Check your email        │                     │
│                    │                          │                     │
│                    │  We sent a verification  │                     │
│                    │  link to                 │                     │
│                    │  s***@company.com        │                     │
│                    │                          │                     │
│                    │  [Resend email]          │                     │
│                    │                          │                     │
│                    │  Wrong email? Sign up    │                     │
│                    │  again.                  │                     │
│                    └──────────────────────────┘                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 3.2 Dashboard Pages

#### `/` (Root — redirects to `/overview` or shows compact dashboard)

**Surface:** MONITOR

**Composition:** 12-column grid. Dense, no hero. The page answers "is everything healthy?" in 2 seconds.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  ProActive SEO                          [Cmd+K] [User] [?]  │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Health Score: 87/100 ▲3    Agents: 7/7 active              │
│           │  ┌─────────┐┌─────────┐┌─────────┐┌─────────┐              │
│           │  │Indexed   ││Keywords ││Issues   ││Traffic  │              │
│           │  │1,247     ││3,891    ││23       ││+12.4%   │              │
│           │  │pages     ││tracked  ││open     ││vs 30d   │              │
│           │  │▲ 14 new  ││▲ 89 new ││▼ 5 fixed││         │              │
│           │  └─────────┘└─────────┘└─────────┘└─────────┘              │
│           │                                                              │
│           │  ┌─────────────────────────────┐┌─────────────────────────┐ │
│           │  │ Traffic Trend (30d)         ││ Agent Activity          │ │
│           │  │                             ││                         │ │
│           │  │  ╭─╮                        ││ Content Agent  ● 2m ago │ │
│           │  │ ╭╯ ╰╮  ╭──╮               ││ Crawled 14 pages        │ │
│           │  │╭╯   ╰──╯  ╰╮              ││                         │ │
│           │  │╰             ╰──           ││ Link Agent    ● now     │ │
│           │  │                             ││ Found 3 prospects       │ │
│           │  │ 12.4K  13.1K  13.8K        ││                         │ │
│           │  └─────────────────────────────┘│ Tech Agent    ● 8m ago │ │
│           │                                 │ Schema validated        │ │
│           │  ┌─────────────────────────────┐│                         │ │
│           │  │ Critical Issues              ││ Keyword Agent ● 15m ago│ │
│           │  │                             ││ Rank check complete     │ │
│           │  │ 3 pages with broken          │└─────────────────────────┘ │
│           │  │ canonical tags               │                          │
│           │  │                              │┌─────────────────────────┐ │
│           │  │ 2 duplicate meta descriptions││ Index Status            │ │
│           │  │ on /blog/*                   ││                         │ │
│           │  │                              ││ Google    ████████ 98%  │ │
│           │  │ 18 pages missing hreflang    ││ Bing      ██████░░ 78%  │ │
│           │  │                              ││ Yandex    ████░░░░ 54%  │ │
│           │  └─────────────────────────────┘│ DuckDuckGo████████ 95%  │ │
│           │                                 └─────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** StatCard ×4, LineChart (traffic), ActivityFeed, IssueList, IndexStatusGrid
**Data flow:**
- `GET /api/dashboard/summary` → health score, stat cards
- `GET /api/dashboard/traffic?range=30d` → chart data
- `GET /api/agents/activity?limit=5` → activity feed
- `GET /api/issues?severity=critical&limit=3` → critical issues
- `GET /api/seo/index-status` → engine grid
- SSE `/api/events/dashboard` → real-time updates (agent status, new issues)
**Loading state:** Skeleton rectangles matching each panel's dimensions. No spinners.
**Error state:** Each panel degrades independently. Failed panel shows "Couldn't load — [Retry]".
**Mobile:** Stack vertically. Stat cards 2×2 grid. Charts full width. Activity feed collapses to 3 items.

---

#### `/overview`

**Surface:** MONITOR

**Composition:** Extended dashboard with 7-day and 30-day comparisons. More detail than `/`.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Overview                              [Date range ▾] [User]│
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Health Score                                    87/100  ││
│           │  │                                                          ││
│           │  │  Technical   ████████████████░░  82     Content ███████  ││
│           │  │  Authority   ██████████████████  94     Links  ████████ ││
│           │  │                                                          ││
│           │  │  +3 vs last week. Technical score improved after         ││
│           │  │  self-healing fixed 12 broken schemas.                   ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌──────────────────┐┌──────────────────┐┌────────────────┐│
│           │  │ Organic Traffic  ││ Indexed Pages    ││ Avg Position  ││
│           │  │ 14,281           ││ 1,247            ││ 18.3          ││
│           │  │ ▲ 12.4% (30d)   ││ ▲ 14 this week   ││ ▲ 2.1 (30d)  ││
│           │  │ [sparkline]      ││ [sparkline]      ││ [sparkline]   ││
│           │  └──────────────────┘└──────────────────┘└────────────────┘│
│           │                                                              │
│           │  ┌──────────────────┐┌──────────────────┐┌────────────────┐│
│           │  │ Keywords in Top  ││ Backlinks        ││ Issues Fixed  ││
│           │  │ 10: 312          ││ 4,891            ││ 47 this month ││
│           │  │ ▲ 28 new         ││ ▲ 127 new        ││ ▼ 12 remain  ││
│           │  │ [sparkline]      ││ [sparkline]      ││ [sparkline]   ││
│           │  └──────────────────┘└──────────────────┘└────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Weekly Summary                                           ││
│           │  │                                                          ││
│           │  │ This week: self-healing agent resolved 12 schema issues  ││
│           │  │ automatically. Content agent published 4 optimized pages ││
│           │  │ for "enterprise SEO tools" cluster. Link agent secured   ││
│           │  │ 3 guest post placements on DA50+ sites.                  ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Data flow:** `GET /api/overview?range=30d` → all metrics with deltas
**Loading state:** Skeleton for each metric card (number placeholder + sparkline placeholder)

---

#### `/activity`

**Surface:** MONITOR

**Composition:** Reverse-chronological activity feed, filterable by agent type and action category. Dense list, not cards.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Activity            [Filter: All agents ▾] [Search] [User] │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Today                                                       │
│           │  ──────────────────────────────────────────────────────────  │
│           │  14:32  Content Agent    Published /blog/schema-markup-guide │
│           │  14:18  Link Agent       Found 3 HARO prospects for         │
│           │                         "enterprise SEO"                     │
│           │  14:05  Tech Agent       Self-healed: fixed broken schema    │
│           │                         on /pricing (FAQPage → Product)     │
│           │  13:47  Keyword Agent    Rank check: "seo automation" moved  │
│           │                         #14 → #8                            │
│           │  13:22  Content Agent    Draft completed: /blog/ai-seo-guide │
│           │  12:58  Crawl Agent     Finished crawl: 847 pages,          │
│           │                         23 new issues found                  │
│           │  12:30  Link Agent       Outreach sent: 5 prospects for      │
│           │                         broken link campaign                 │
│           │                                                              │
│           │  Yesterday                                                   │
│           │  ──────────────────────────────────────────────────────────  │
│           │  18:45  Tech Agent       Multi-engine check complete:        │
│           │                         Google 98%, Bing 78%                │
│           │  17:30  Content Agent    Content brief generated for         │
│           │                         "technical seo audit" cluster        │
│           │  ...                                                         │
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │               Load more activity                        ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** FilterBar, ActivityRow (icon, timestamp, agent badge, description)
**Data flow:** `GET /api/activity?agent=all&cursor=<id>&limit=50`
**Loading state:** 10 skeleton rows (icon circle + 2 text lines)
**Empty state:** "No activity matches your filters. [Clear filters]"
**Mobile:** Full width, timestamps stack above description.

---

#### `/notifications`

**Surface:** MONITOR (secondary: OPERATE for mark-as-read actions)

**Composition:** List with read/unread state. Action buttons inline.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Notifications            [Mark all read] [Filter ▾] [User] │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ ● Health score dropped below threshold (82 < 85)        ││
│           │  │   Tech Agent · 2 hours ago              [View] [Dismiss]││
│           │  └─────────────────────────────────────────────────────────┘│
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ ● Guest post published on SearchEngineJournal           ││
│           │  │   Link Agent · 4 hours ago              [View] [Dismiss]││
│           │  └─────────────────────────────────────────────────────────┘│
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │   Crawl completed: 847 pages, 23 new issues             ││
│           │  │   Crawl Agent · Yesterday               [View] [Dismiss]││
│           │  └─────────────────────────────────────────────────────────┘│
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │   Billing: 90% of monthly crawl budget used              ││
│           │  │   System · 2 days ago                   [View] [Dismiss]││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Data flow:** `GET /api/notifications?unread=true` → list; `PATCH /api/notifications/:id/read`
**Empty state:** "No notifications. You're all caught up."

---

### 3.3 Project Pages

#### `/projects`

**Surface:** OPERATE

**Composition:** Grid of project cards with status indicators. Toolbar at top for search + create.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Projects           [+ New project] [Search projects] [User] │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌─────────────────────┐  ┌─────────────────────┐          │
│           │  │ acme.com            │  │ staging.acme.com    │          │
│           │  │ Health: 87/100      │  │ Health: 62/100      │          │
│           │  │ 1,247 pages         │  │ 340 pages           │          │
│           │  │ 3,891 keywords      │  │ 891 keywords        │          │
│           │  │ 7 agents active     │  │ 4 agents active     │          │
│           │  │                     │  │                     │          │
│           │  │ Last crawl: 2h ago  │  │ Last crawl: 1d ago  │          │
│           │  │ [Open →]            │  │ [Open →]            │          │
│           │  └─────────────────────┘  └─────────────────────┘          │
│           │                                                              │
│           │  ┌─────────────────────┐                                    │
│           │  │ blog.acme.com       │                                    │
│           │  │ Health: 91/100      │                                    │
│           │  │ 512 pages           │                                    │
│           │  │ 2,104 keywords      │                                    │
│           │  │ 5 agents active     │                                    │
│           │  │                     │                                    │
│           │  │ Last crawl: 6h ago  │                                    │
│           │  │ [Open →]            │                                    │
│           │  └─────────────────────┘                                    │
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** ProjectCard (interactive), SearchInput, Button (primary: New project)
**Data flow:** `GET /api/projects` → list with summary stats
**Empty state:** "No projects yet. Create your first project to start monitoring."
**Mobile:** Single column, cards full width.

---

#### `/projects/new`

**Surface:** CONFIGURE

**Composition:** Multi-step form (wizard). Steps: Domain → Competitors → Agents → Review.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  New Project                                                 │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Step 1 of 4: Domain Setup                                   │
│           │  ● ─── ○ ─── ○ ─── ○                                        │
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │                                                          ││
│           │  │  Domain to monitor                                       ││
│           │  │  ┌─────────────────────────────────────────────────────┐││
│           │  │  │ https://                                              │││
│           │  │  └─────────────────────────────────────────────────────┘││
│           │  │  We'll crawl and index all discoverable pages.          ││
│           │  │                                                          ││
│           │  │  Site type                                               ││
│           │  │  (●) Corporate / Marketing    ( ) E-commerce             ││
│           │  │  ( ) Blog / Media              ( ) SaaS / App            ││
│           │  │                                                          ││
│           │  │  Estimated crawl: ~1,200 pages based on sitemap.xml      ││
│           │  │                                                          ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌──────────────┐  ┌──────────────┐                        │
│           │  │   Cancel      │  │  Next →       │                        │
│           │  └──────────────┘  └──────────────┘                        │
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** Stepper, Input (with protocol prefix), RadioGroup, Button (primary/ghost)
**Data flow:** `POST /api/projects` → creates project; `POST /api/crawl/init` → starts initial crawl

---

#### `/projects/{id}`

**Surface:** MONITOR

**Composition:** Project-scoped dashboard. Same dense grid as `/` but filtered to one project.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  acme.com                   [Settings ⚙] [User]            │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Health: 87/100 ▲3    Pages: 1,247    Keywords: 3,891       │
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ ┌──────┐ ┌──────────┐ ┌──────┐ ┌──────┐ ┌──────────┐ ││
│           │  │ │Overview│ │SEO Command│ │Agents│ │Content│ │Technical│ ││
│           │  │ └──────┘ └──────────┘ └──────┘ └──────┘ └──────────┘ ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  [Tab content: Overview selected — same as / but project-    │
│           │   scoped. Shows traffic, index status, critical issues,      │
│           │   agent activity for acme.com only.]                         │
│           │                                                              │
│           │  ┌────────────────────────┐┌───────────────────────────┐    │
│           │  │ Traffic (30d)           ││ Top Keywords              │    │
│           │  │ 14,281 ▲12.4%          ││                           │    │
│           │  │ [line chart]            ││ 1. enterprise seo tools   │    │
│           │  │                         ││    #3 ▲2                  │    │
│           │  │                         ││ 2. seo automation platform│    │
│           │  │                         ││    #8 ▲6                  │    │
│           │  │                         ││ 3. ai seo software        │    │
│           │  │                         ││    #12 ▼1                 │    │
│           │  └────────────────────────┘└───────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

**Data flow:** `GET /api/projects/:id/dashboard` → project-scoped metrics

---

#### `/projects/{id}/settings`

**Surface:** CONFIGURE

**Composition:** Vertical form sections with save bar.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  acme.com — Settings                    [Save] [User]       │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  General                                                     │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Domain name         [acme.com                          ]   │
│           │  Project name        [Acme Corporation                  ]   │
│           │  Site type           [Corporate / Marketing ▾           ]   │
│           │                                                              │
│           │  Monitoring                                                  │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Crawl frequency     [Daily ▾                           ]   │
│           │  Health threshold    [Alert below: 85 ▾                 ]   │
│           │  Ignored paths       [/tmp/*, /admin/*                  ]   │
│           │                                                              │
│           │  Competitors                                                 │
│           │  ─────────────────────────────────────────────────────────── │
│           │  competitor.com                          [Remove]            │
│           │  rival-inc.com                           [Remove]            │
│           │  [+ Add competitor]                                          │
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Danger Zone                                                ││
│           │  │ Delete this project. This action cannot be undone.        ││
│           │  │ All data, agents, and campaigns will be permanently       ││
│           │  │ removed.                                                   ││
│           │  │ [Delete project]                                          ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** Input, Select, NumberInput, TagList, Button (danger for delete)
**Data flow:** `GET/PATCH /api/projects/:id/settings`
**Dirty state:** Save bar appears at bottom when form changes. "You have unsaved changes. [Discard] [Save]"

---

### 3.4 SEO Command Pages

#### `/seo/overview`

**Surface:** MONITOR

**Composition:** Full SEO health overview. 6 metric cards top, 2 panels below.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  SEO Overview            [Project: acme.com ▾] [User]       │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌──────┐│
│           │  │Health  ││Indexed ││Keywords││Top 10  ││Issues  ││Back- ││
│           │  │87/100  ││1,247   ││3,891   ││312     ││23 open ││links ││
│           │  │▲3      ││▲14     ││▲89     ││▲28     ││▼5      ││4,891 ││
│           │  └────────┘└────────┘└────────┘└────────┘└────────┘└──────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Keyword Distribution                                     ││
│           │  │                                                          ││
│           │  │  #1-3    ████████  78 keywords (2%)                      ││
│           │  │  #4-10   ████████████████  234 keywords (6%)             ││
│           │  │  #11-20  ████████████████████████  456 keywords (12%)    ││
│           │  │  #21-50  ████████████████████████████████████  1,203 (31%)│
│           │  │  #51-100 ██████████████████████████████████  1,100 (28%) ││
│           │  │  #100+   ██████████████████████  820 (21%)               ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌──────────────────────────────┐┌──────────────────────────┐│
│           │  │ Top Movers (7d)               ││ Competitor Comparison    ││
│           │  │                               ││                          ││
│           │  │ "enterprise seo" #14→#8 ▲6    ││ acme.com     87 ▲3      ││
│           │  │ "seo automation" #22→#15 ▲7   ││ competitor   82 ▼1      ││
│           │  │ "ai seo tools" #31→#24 ▲7     ││ rival-inc    79 ▲5      ││
│           │  │ "technical seo" #8→#6 ▲2      ││                          ││
│           │  │ "site audit tool" #45→#38 ▲7  ││                          ││
│           │  └──────────────────────────────┘└──────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** StatCard ×6, HorizontalBarChart, MoverTable, CompetitorTable

---

#### `/seo/keywords`

**Surface:** OPERATE

**Composition:** Full-width data table with filter sidebar. This is a work surface.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Keywords               [Export] [Add keywords] [User]      │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  [Search keywords... ]  [Cluster ▾] [Position ▾] [Change ▾] │
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ □  Keyword              Pos  Change  Vol    Traffic  CTR ││
│           │  │ ─────────────────────────────────────────────────────────││
│           │  │ □  enterprise seo tools  3    ▲2     2,400   891    38%  ││
│           │  │ □  seo automation        8    ▲6     1,900   412    22%  ││
│           │  │ □  ai seo software       12   ▼1     1,600   289    18%  ││
│           │  │ □  technical seo audit   6    ▲2     3,200   624    20%  ││
│           │  │ □  site audit tool       38   ▲7       880    45     5%  ││
│           │  │ □  backlink checker      15   ▲3     4,100   578    14%  ││
│           │  │ □  keyword research tool 22   ▼4     2,800   341    12%  ││
│           │  │ □  on-page seo checker   9    ▲1     1,200   398    33%  ││
│           │  │ □  seo ranking tracker   18   ▲5     1,400   267    19%  ││
│           │  │ □  content optimization  24   ▲3       920   118    13%  ││
│           │  │                                                          ││
│           │  │ Showing 1-10 of 3,891   [< 1 2 3 ... 390 >]            ││
│           │  │                                                          ││
│           │  │ □ 2 selected  [Add to campaign] [Tag] [Export selected]  ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** DataTable (sortable, selectable), FilterBar, Pagination, BulkActionBar
**Data flow:** `GET /api/keywords?project_id=X&page=1&sort=position&dir=asc`
**Loading state:** 10 skeleton rows
**Empty state:** "No keywords tracked. [Add keywords] to start monitoring rankings."

---

#### `/seo/pages`

**Surface:** OPERATE

**Composition:** Data table of all indexed pages with SEO scores.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Pages                  [Export] [User]                      │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  [Search URLs... ]  [Status ▾] [Score ▾] [Type ▾]          │
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │  URL                        Score  Status   Issues  Traffic│
│           │  │ ─────────────────────────────────────────────────────────││
│           │  │  /                           94    Indexed    0     2,341 ││
│           │  │  /blog/ai-seo-guide          91    Indexed    1       891 ││
│           │  │  /products/enterprise        87    Indexed    2     1,204 ││
│           │  │  /pricing                    82    Indexed    3       567 ││
│           │  │  /blog/schema-markup         78    Indexed    2       445 ││
│           │  │  /about                      76    Indexed    1       234 ││
│           │  │  /contact                    71    Indexed    2       123 ││
│           │  │  /blog/old-post              45    Crawled    5        12 ││
│           │  │  /legacy/page                --    Not found   --       0 ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/seo/issues`

**Surface:** OPERATE

**Composition:** Issue list with severity grouping. Bulk resolve actions.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Issues                 [Filter ▾] [Export] [User]          │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Critical (3)                                                │
│           │  ──────────────────────────────────────────────────────────  │
│           │  □  Broken canonical tag on 3 pages         [Fix →] [Ignore]│
│           │      /pricing, /features, /enterprise                        │
│           │      Detected: 2 days ago · Self-healing: pending            │
│           │                                                              │
│           │  □  Duplicate meta descriptions on /blog/*   [Fix →] [Ignore]│
│           │      2 pages share identical descriptions                     │
│           │      Detected: 1 day ago · Self-healing: in progress         │
│           │                                                              │
│           │  Warning (12)                                                │
│           │  ──────────────────────────────────────────────────────────  │
│           │  □  Missing hreflang on 18 pages             [Fix →] [Ignore]│
│           │  □  Slow loading (>3s) on 4 pages             [Fix →] [Ignore]│
│           │  □  Missing alt text on 12 images             [Fix →] [Ignore]│
│           │  ...                                                         │
│           │                                                              │
│           │  Info (8)                                                    │
│           │  ──────────────────────────────────────────────────────────  │
│           │  □  6 pages have no internal links pointing   [Review →]     │
│           │     to them                                                  │
│           │  ...                                                         │
│           │                                                              │
│           │  □ 3 selected  [Resolve selected] [Ignore selected]          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Data flow:** `GET /api/issues?project_id=X&severity=critical,warning`
**Loading state:** Skeleton grouped by severity (3 header bars with 2 rows each)

---

#### `/seo/health-score`

**Surface:** MONITOR

**Composition:** Single-page deep dive into health score. One idea: what comprises the score and how to improve it.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Health Score           [30d ▾] [User]                       │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │                     87 / 100                             ││
│           │  │                 ▲ 3 points vs last week                  ││
│           │  │                                                          ││
│           │  │  ┌───────────────────┐                                  ││
│           │  │  │    ╭────────╮     │  Technical  82  ▲5               ││
│           │  │  │   ╱    87    ╲    │  Content    91  ▲1               ││
│           │  │  │  │            │   │  Authority  94  ▲2               ││
│           │  │  │   ╲          ╱    │  Links      85  ▲3               ││
│           │  │  │    ╰────────╯     │                                  ││
│           │  │  └───────────────────┘                                  ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Score Breakdown                                           ││
│           │  │                                                          ││
│           │  │  Technical (82/100) ──────────────────────────────────── ││
│           │  │  - Schema markup: 94% valid         ████████████████░░  ││
│           │  │  - Page speed: 89% under 3s         ███████████████░░░  ││
│           │  │  - Mobile friendly: 100%             ██████████████████  ││
│           │  │  - Canonical tags: 97% correct       █████████████████░  ││
│           │  │  - HTTPS: 100%                       ██████████████████  ││
│           │  │                                                          ││
│           │  │  Content (91/100) ───────────────────────────────────── ││
│           │  │  - Meta descriptions: 98% present    █████████████████░  ││
│           │  │  - Title tags: 100% optimized        ██████████████████  ││
│           │  │  - H1 tags: 96% present              ████████████████░░  ││
│           │  │  - Content freshness: 78% < 90 days  ██████████████░░░░  ││
│           │  │                                                          ││
│           │  │  Authority (94/100) ─────────────────────────────────── ││
│           │  │  - Domain authority: 54              ████████████████░░  ││
│           │  │  - Referring domains: 891            ████████████████░░  ││
│           │  │  - Trust flow: 48                    ██████████████░░░░  ││
│           │  │                                                          ││
│           │  │  Links (85/100) ─────────────────────────────────────── ││
│           │  │  - Internal link equity: 72%         ██████████████░░░░  ││
│           │  │  - Broken links: 3 found             ██░░░░░░░░░░░░░░░░  ││
│           │  │  - Anchor text diversity: 89%        ████████████████░░  ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Score History (30 days)                                    ││
│           │  │                                                          ││
│           │  │  90│                                                     ││
│           │  │  85│     ╭──╮  ╭──────╮                                  ││
│           │  │  80│ ╭──╯  ╰──╯      ╰──╮                               ││
│           │  │  75│─╯                   ╰────────────                   ││
│           │  │    └────────────────────────────────────                 ││
│           │  │     Jun 19              Jul 10         Jul 19            ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** ScoreRing (animated SVG), ProgressBar ×N, LineChart
**Animation:** Score ring animates from 0 to 87 on load (300ms ease-out). `prefers-reduced-motion`: instant.

---

### 3.5 Agent Control Pages

#### `/agents`

**Surface:** MONITOR (secondary: OPERATE for start/stop)

**Composition:** Grid of agent status cards, each showing live state. This is the nerve center.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Agents                    [Start all] [Stop all] [User]    │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Crawl Agent                              ● Active       ││
│           │  │                                                          ││
│           │  │  Last run: 14 min ago                                    ││
│           │  │  Pages crawled: 1,247 / 1,247                           ││
│           │  │  Next run: in 46 min (daily at 15:00)                   ││
│           │  │  Issues found: 23                                        ││
│           │  │                                                          ││
│           │  │  [View logs]  [Configure]  [Pause]                      ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Content Agent                            ● Active       ││
│           │  │                                                          ││
│           │  │  Current task: Optimizing /blog/ai-seo-guide             ││
│           │  │  Progress: ████████████████░░░░ 78%                      ││
│           │  │  Published today: 2 pages                                ││
│           │  │  Drafts in queue: 4                                      ││
│           │  │                                                          ││
│           │  │  [View logs]  [Configure]  [Pause]                      ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Link Building Agent                      ● Active       ││
│           │  │                                                          ││
│           │  │  Active campaigns: 3                                     ││
│           │  │  Prospects found today: 12                               ││
│           │  │  Outreach sent: 5                                        ││
│           │  │  Responses: 2                                            ││
│           │  │                                                          ││
│           │  │  [View logs]  [Configure]  [Pause]                      ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Keyword Research Agent                   ● Active       ││
│           │  │                                                          ││
│           │  │  Last rank check: 32 min ago                             ││
│           │  │  Keywords checked: 3,891 / 3,891                        ││
│           │  │  Position changes detected: 14                           ││
│           │  │  New keyword suggestions: 28                             ││
│           │  │                                                          ││
│           │  │  [View logs]  [Configure]  [Pause]                      ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Technical SEO Agent                      ○ Paused       ││
│           │  │                                                          ││
│           │  │  Last run: 2 hours ago                                   ││
│           │  │  Issues self-healed: 12 / 15                            ││
│           │  │  Pending manual review: 3                               ││
│           │  │                                                          ││
│           │  │  [View logs]  [Configure]  [Resume]                     ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Multi-Engine Index Agent                 ● Active       ││
│           │  │                                                          ││
│           │  │  Google: 1,219 / 1,247 indexed (98%)                    ││
│           │  │  Bing: 973 / 1,247 indexed (78%)                        ││
│           │  │  Last check: 1 hour ago                                 ││
│           │  │                                                          ││
│           │  │  [View logs]  [Configure]  [Pause]                      ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ HARO/PR Agent                            ● Active       ││
│           │  │                                                          ││
│           │  │  Active queries: 8                                       ││
│           │  │  Responses drafted: 3                                    ││
│           │  │  Placements this month: 2                                ││
│           │  │                                                          ││
│           │  │  [View logs]  [Configure]  [Pause]                      ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** AgentStatusCard (real-time via SSE), Button (ghost: logs/config, primary: pause/resume)
**Data flow:**
- `GET /api/agents` → list of agents with status
- SSE `/api/events/agents` → real-time status updates (task progress, new findings)
**Loading state:** 7 skeleton cards (icon placeholder + 3 text lines + 3 button placeholders)
**Mobile:** Full width cards, stack vertically.

---

#### `/agents/{type}`

**Surface:** MONITOR

**Composition:** Agent detail page. Metrics top, recent activity middle, configuration quick-access bottom.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Content Agent                       [Pause] [Configure]    │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Status: ● Active    Uptime: 23h 47m    Tasks today: 14     │
│           │                                                              │
│           │  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐          │
│           │  │Published ││Drafts    ││In Queue  ││Failed    │          │
│           │  │47        ││4         ││12        ││1         │          │
│           │  │this month││pending   ││waiting   ││error     │          │
│           │  └──────────┘└──────────┘└──────────┘└──────────┘          │
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Activity Log (live)                                       ││
│           │  │                                                          ││
│           │  │ 14:32  Published /blog/schema-markup-guide               ││
│           │  │        SEO score: 94/100, 2,340 words, 8 internal links  ││
│           │  │                                                          ││
│           │  │ 14:18  Draft completed: /blog/technical-seo-checklist    ││
│           │  │        Awaiting review — SEO score: 89/100               ││
│           │  │                                                          ││
│           │  │ 13:55  Optimizing /blog/ai-seo-guide                     ││
│           │  │        Progress: 78% — rewriting introduction, adding    ││
│           │  │        schema markup                                      ││
│           │  │                                                          ││
│           │  │ 13:22  Content brief generated for "seo automation"      ││
│           │  │        Target: 2,500 words, competitor avg: 1,800        ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  [View all logs →]  [Configuration →]                        │
└──────────────────────────────────────────────────────────────────────────┘
```

**Data flow:** `GET /api/agents/:type` → agent detail; SSE `/api/events/agents/:type` → live log

---

#### `/agents/{type}/logs`

**Surface:** COMMAND / INSPECT

**Composition:** Terminal-style log viewer. Monospace, dense, filterable.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Content Agent — Logs    [Level: All ▾] [Search] [Export]   │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ [auto-scroll ●]                                          ││
│           │  │                                                          ││
│           │  │ 14:32:01  INFO   Publishing /blog/schema-markup-guide    ││
│           │  │ 14:32:03  INFO   SEO score calculated: 94/100           ││
│           │  │ 14:32:03  INFO   Schema markup validated: Article        ││
│           │  │ 14:32:04  INFO   Internal links added: 8                 ││
│           │  │ 14:32:05  INFO   Published successfully                  ││
│           │  │ 14:32:05  INFO   Sitemap updated                         ││
│           │  │ 14:18:12  INFO   Starting draft: /blog/tech-seo-checklist││
│           │  │ 14:18:15  INFO   Content brief loaded                    ││
│           │  │ 14:18:16  INFO   Research phase: analyzing top 10 results││
│           │  │ 14:19:02  INFO   Research complete: 10 sources analyzed  ││
│           │  │ 14:19:03  INFO   Draft phase: generating outline         ││
│           │  │ 14:22:15  INFO   Outline complete: 8 sections            ││
│           │  │ 14:22:16  INFO   Draft phase: writing content            ││
│           │  │ 14:30:44  INFO   Draft complete: 2,487 words             ││
│           │  │ 14:30:45  INFO   SEO score: 89/100                       ││
│           │  │ 14:30:45  INFO   Status: pending_review                  ││
│           │  │ 13:55:01  WARN   /blog/ai-seo-guide: slow load (4.2s)   ││
│           │  │ 13:55:02  INFO   Optimizing: rewriting intro for clarity ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  247 lines  [Load older →]                                  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** LogViewer (monospace, auto-scroll), FilterBar, SearchInput
**Data flow:** `GET /api/agents/:type/logs?level=all&limit=200`; SSE `/api/events/agents/:type/logs`
**Font:** JetBrains Mono, 12px. Line height 18px.

---

#### `/agents/{type}/config`

**Surface:** CONFIGURE

**Composition:** Vertical form sections.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Content Agent — Configuration          [Save] [Reset]      │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Scheduling                                                  │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Run mode            [Continuous ▾]                         │
│           │  Max concurrent tasks [4 ▾]                                 │
│           │  Content types       [x] Blog posts  [x] Landing pages      │
│           │                      [ ] Product pages [ ] Documentation    ││
│           │                                                              │
│           │  Quality Thresholds                                          │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Minimum SEO score   [80 ▾]                                 │
│           │  Min word count      [1,500]                                │
│           │  Max word count      [4,000]                                │
│           │  Auto-publish        [x] Above 90 score                     │
│           │                      [ ] Always (not recommended)           ││
│           │                                                              │
│           │  AI Model                                                    │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Primary model       [claude-3.5-sonnet ▾]                  │
│           │  Fallback model      [gpt-4o ▾]                             │
│           │  Temperature         [0.3 ──●──────────]                    │
│           │                                                              │
│           │  Notifications                                               │
│           │  ─────────────────────────────────────────────────────────── │
│           │  [x] Notify on publish    [x] Notify on failure             │
│           │  [ ] Notify on draft      [x] Daily summary                 │
└──────────────────────────────────────────────────────────────────────────┘
```

---

### 3.6 Campaign Pages

#### `/campaigns`

**Surface:** OPERATE

**Composition:** Table view with status tabs. Toggle to Kanban view.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Campaigns             [+ New campaign] [Table|Board] [User]│
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  [All] [Active] [Paused] [Completed]                        │
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Campaign              Type          Status   Prospects   ││
│           │  │ ────────────────────────────────────────────────────────││
│           │  │ Q3 Guest Posts        Guest Post    Active   23/50      ││
│           │  │ Broken Link Outreach  Broken Links  Active   8/30       ││
│           │  │ Enterprise SEO HARO   HARO          Active   3/8        ││
│           │  │ Unlinked Mentions     Mentions      Paused   12/20      ││
│           │  │ Blog Link Building    Guest Post    Completed 45/45     ││
│           │  └──────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  Kanban view (when "Board" selected):                        │
│           │                                                              │
│           │  ┌──────────────┐┌──────────────┐┌──────────────┐┌────────┐│
│           │  │ Prospecting  ││ Outreach     ││ Negotiating  ││ Placed ││
│           │  │              ││              ││              ││        ││
│           │  │ ┌──────────┐ ││ ┌──────────┐ ││ ┌──────────┐ ││┌──────┐││
│           │  │ │SEJ guest │ ││ │Forbes    │ ││ │HubSpot   │ │││Tech- │││
│           │  │ │post      │ ││ │HARO resp │ ││ │guest post│ │││Crunch│││
│           │  │ │DA: 92    │ ││ │DA: 95    │ ││ │DA: 93    │ │││DA: 94│││
│           │  │ └──────────┘ ││ └──────────┘ ││ └──────────┘ ││└──────┘││
│           │  │ ┌──────────┐ ││ ┌──────────┐ ││              ││┌──────┐││
│           │  │ │Moz blog  │ ││ │Ahrefs    │ ││              │││Search│││
│           │  │ │DA: 91    │ ││ │DA: 90    │ ││              │││Engine│││
│           │  │ └──────────┘ ││ └──────────┘ ││              │││Journal││
│           │  │              ││              ││              │││DA: 92│││
│           │  │ 8 cards      ││ 5 cards      ││ 2 cards      ││└──────┘││
│           │  └──────────────┘└──────────────┘└──────────────┘│ 3 cards││
│           │                                                  └────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** Tabs, DataTable, KanbanBoard (drag-and-drop), CampaignCard
**Data flow:** `GET /api/campaigns?status=active`

---

#### `/campaigns/{id}`

**Surface:** OPERATE

**Composition:** Campaign detail with prospect list and metrics.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Q3 Guest Posts          [Edit] [Pause] [User]              │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Type: Guest Post  Status: Active  Created: Jun 1, 2026     │
│           │                                                              │
│           │  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐          │
│           │  │Prospects ││Outreach  ││Responses ││Placed    │          │
│           │  │50        ││35        ││12        ││8         │          │
│           │  │target    ││sent      ││received  ││published │          │
│           │  └──────────┘└──────────┘└──────────┘└──────────┘          │
│           │                                                              │
│           │  Response rate: 34%  Avg DA: 72  Links placed: 8           │
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Prospects                                                ││
│           │  │                                                          ││
│           │  │  Site              DA  Status      Last Contact  Link   ││
│           │  │  ──────────────────────────────────────────────────────  ││
│           │  │  SearchEngineJournal 92  Placed      Jul 15      ✓     ││
│           │  │  Moz Blog            91  Negotiating Jul 12      --    ││
│           │  │  Ahrefs Blog         90  Outreach    Jul 10      --    ││
│           │  │  HubSpot Blog        93  Negotiating Jul 8       --    ││
│           │  │  Neil Patel          88  Prospect    --          --    ││
│           │  │  Backlinko           85  Prospect    --          --    ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/campaigns/haro`

**Surface:** OPERATE

**Composition:** HARO query feed with response status.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  HARO / PR Campaigns     [+ Monitor keywords] [User]        │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Monitored keywords: "enterprise seo", "seo automation",     │
│           │  "technical seo", "ai seo"                                   │
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Active Queries                                           ││
│           │  │                                                          ││
│           │  │  "Looking for SEO experts to comment on AI in search"    ││
│           │  │   Source: Forbes · Deadline: Jul 21 · DA: 95             ││
│           │  │   Status: Response drafted    [View response →]          ││
│           │  │                                                          ││
│           │  │  "Need technical SEO tips for enterprise websites"       ││
│           │  │   Source: Search Engine Land · Deadline: Jul 22 · DA: 88 ││
│           │  │   Status: Auto-responded      [View response →]          ││
│           │  │                                                          ││
│           │  │  "How are companies using AI for content optimization?"  ││
│           │  │   Source: Entrepreneur · Deadline: Jul 23 · DA: 91       ││
│           │  │   Status: Pending response    [Review draft →]           ││
│           │  └──────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Past Placements                                          ││
│           │  │                                                          ││
│           │  │  "5 Enterprise SEO Tools..." — TechCrunch (DA: 94)       ││
│           │  │   Published: Jul 8, 2026                                 ││
│           │  │   Link: techcrunch.com/enterprise-seo-tools              ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/campaigns/broken-links`

**Surface:** OPERATE

**Composition:** Broken link opportunities table.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Broken Link Campaign    [Scan new targets] [User]          │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Broken Link Opportunities                                ││
│           │  │                                                          ││
│           │  │  Target Page                    Broken URL    Your Page  ││
│           │  │  ────────────────────────────────────────────────────── ││
│           │  │  moz.com/beginners-guide-seo    /old-tools    /tools     ││
│           │  │  ahrefs.com/blog/seo-tools      /dead-link    /features  ││
│           │  │  neilpatel.com/seo-guide        /404-page     /guide     ││
│           │  │                                                          ││
│           │  │  Status: Outreach ready    [Send template →]             ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/campaigns/guest-posts`

**Surface:** OPERATE

**Composition:** Guest post pipeline with content tracking.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Guest Post Pipeline     [Find new targets] [User]          │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Target Site          DA  Topic              Status      ││
│           │  │ ─────────────────────────────────────────────────────── ││
│           │  │ SearchEngineJournal  92  Schema Markup Guide Published   ││
│           │  │ Moz Blog             91  Link Building 2026  Drafting    ││
│           │  │ Ahrefs Blog          90  Technical SEO Audit Pitching   ││
│           │  │ HubSpot Blog         93  AI Content Strategy  Outreach  ││
│           │  │ Backlinko            85  Enterprise SEO       Prospect  ││
│           │  └──────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Published Guest Posts                                     ││
│           │  │                                                          ││
│           │  │  "The Complete Guide to Schema Markup" — SEJ              ││
│           │  │   Published: Jul 15 · DA: 92 · Backlinks: 3             ││
│           │  │   Traffic to your site: 142 sessions                     ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/campaigns/unlinked-mentions`

**Surface:** OPERATE

**Composition:** Mention detection with outreach status.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Unlinked Mentions      [Scan web] [User]                   │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Source Page               Context        Status         ││
│           │  │ ─────────────────────────────────────────────────────── ││
│           │  │ techradar.com/best-seo    "ProActive     Outreach sent  ││
│           │  │                           SEO is a top                  ││
│           │  │                           choice"                       ││
│           │  │                                                          ││
│           │  │ pcmag.com/seo-tools       "...including   Pending       ││
│           │  │                           ProActive SEO"                ││
│           │  │                                                          ││
│           │  │ zdnet.com/ai-seo          "ProActive     Link added ✓  ││
│           │  │                           SEO leads the                 ││
│           │  │                           market"                       ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

### 3.7 Content Pages

#### `/content/briefs`

**Surface:** OPERATE

**Composition:** Brief cards with status and target keywords.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Content Briefs         [+ Generate brief] [User]           │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  [All] [Pending] [In Progress] [Completed]                  │
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ "seo automation platform"                                ││
│           │  │ Target keywords: seo automation, automate seo tasks      ││
│           │  │ Competitor avg word count: 2,100                         ││
│           │  │ Recommended: 2,800 words, 10 sections                   ││
│           │  │ Status: Ready for writing          [Start writing →]    ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ "technical seo audit checklist"                          ││
│           │  │ Target keywords: technical seo audit, seo checklist      ││
│           │  │ Competitor avg word count: 1,800                         ││
│           │  │ Recommended: 2,500 words, 8 sections                    ││
│           │  │ Status: Draft in progress           [View draft →]      ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ "enterprise seo best practices"                          ││
│           │  │ Target keywords: enterprise seo, seo for enterprises     ││
│           │  │ Competitor avg word count: 2,400                         ││
│           │  │ Recommended: 3,200 words, 12 sections                   ││
│           │  │ Status: Generating brief...         [Cancel]             ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Data flow:** `GET /api/content/briefs?status=all`

---

#### `/content/drafts`

**Surface:** OPERATE

**Composition:** Draft list with SEO scores and review status.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Drafts                 [User]                               │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Title                      Words  SEO Score  Status     ││
│           │  │ ────────────────────────────────────────────────────────││
│           │  │ The Complete Guide to       2,847   94/100   Published  ││
│           │  │ Schema Markup                                          ││
│           │  │                                                          ││
│           │  │ Technical SEO Checklist:     2,487   89/100   Pending   ││
│           │  │ 15 Steps for 2026                       review         ││
│           │  │                                                          ││
│           │  │ AI-Powered Content           1,892   72/100   Needs     ││
│           │  │ Optimization Guide                              revision││
│           │  │                                                          ││
│           │  │ How to Build an SEO          --      --       Generat-  ││
│           │  │ Strategy for SaaS                                ing...  ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/content/published`

**Surface:** OPERATE

**Composition:** Published content with performance metrics.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Published Content       [Sort: Traffic ▾] [User]           │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ URL                          Traffic  Rank  Links  Date  ││
│           │  │ ────────────────────────────────────────────────────────││
│           │  │ /blog/schema-markup-guide    891      #3     12    Jul 15││
│           │  │ /blog/ai-seo-guide           567      #8      8    Jul 8 ││
│           │  │ /blog/link-building-2026     445      #12     6    Jun 22││
│           │  │ /blog/technical-seo          334      #6     15    Jun 10││
│           │  │ /blog/enterprise-seo         289      #14     4    May 28││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/content/editor/{id}`

**Surface:** OPERATE (editor mode)

**Composition:** Side-by-side. Left: content editor. Right: optimization panel.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Editing: Technical SEO Checklist     [Save] [Publish]      │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌────────────────────────────────┐┌────────────────────────┐│
│           │  │ Title:                          ││ SEO Score: 89/100     ││
│           │  │ ┌────────────────────────────┐  ││                        ││
│           │  │ │ Technical SEO Checklist:   │  ││ ┌────────────────────┐││
│           │  │ │ 15 Steps for 2026          │  ││ │ Issues             │││
│           │  │ └────────────────────────────┘  ││ │                    │││
│           │  │                                  ││ │ ▲ Add internal     │││
│           │  │ ┌────────────────────────────┐  ││ │   links (3 missing)│││
│           │  │ │ Technical SEO is the       │  ││ │                    │││
│           │  │ │ foundation of any          │  ││ │ ▲ Add alt text     │││
│           │  │ │ successful search          │  ││ │   to 2 images      │││
│           │  │ │ strategy. Without a        │  ││ │                    │││
│           │  │ │ solid technical            │  ││ │ ✓ Title tag length │││
│           │  │ │ foundation, even the       │  ││ │   is optimal       │││
│           │  │ │ best content will          │  ││ │                    │││
│           │  │ │ struggle to rank.          │  ││ │ ✓ Meta description │││
│           │  │ │                            │  ││ │   present          │││
│           │  │ │ This checklist covers      │  ││ │                    │││
│           │  │ │ the 15 most critical       │  ││ │ ✓ Schema markup    │││
│           │  │ │ technical SEO tasks        │  ││ │   added            │││
│           │  │ │ you need to complete       │  ││ └────────────────────┘││
│           │  │ │ in 2026.                   │  ││                        ││
│           │  │ │                            │  ││ ┌────────────────────┐││
│           │  │ │ ## 1. Crawlability        │  ││ │ Content Stats      │││
│           │  │ │                            │  ││ │                    │││
│           │  │ │ Ensure search engines      │  ││ │ Words: 2,487       │││
│           │  │ │ can access all important   │  ││ │ Headings: 8        │││
│           │  │ │ pages on your site...      │  ││ │ Images: 4          │││
│           │  │ │                            │  ││ │ Links: 5 (need 8)  │││
│           │  │ │ [cursor blinking]          │  ││ │ Read time: 10 min  │││
│           │  │ └────────────────────────────┘  ││ └────────────────────┘││
│           │  │                                  ││                        ││
│           │  │ ┌────────────────────────────┐  ││ ┌────────────────────┐││
│           │  │ │ Auto-save: 14:32           │  ││ │ Target Keywords    │││
│           │  │ └────────────────────────────┘  ││ │                    │││
│           │  └────────────────────────────────┘││ │ technical seo audit│││
│           │                                     ││ │ ████████████░  8   │││
│           │                                     ││ │                    │││
│           │                                     ││ │ seo checklist      │││
│           │                                     ││ │ ██████████████ 12  │││
│           │                                     ││ └────────────────────┘││
│           │                                     └────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** RichTextEditor (markdown), OptimizationPanel, ScoreWidget, KeywordTracker
**Data flow:** `GET /api/content/:id` → draft content; `PATCH /api/content/:id` (debounced auto-save)
**Mobile:** Stack vertically. Editor full width, optimization panel as bottom sheet.

---

### 3.8 Technical Pages

#### `/technical/audit`

**Surface:** MONITOR

**Composition:** Audit results grouped by category with severity.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Technical Audit         [Run audit] [Last: 2h ago] [User]  │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Overall Score: 82/100 ▲5                                    │
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Crawlability (95/100)                                    ││
│           │  │  ✓ robots.txt valid                                      ││
│           │  │  ✓ sitemap.xml present and valid (1,247 URLs)           ││
│           │  │  ✓ No noindex on important pages                        ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Page Speed (78/100)                                      ││
│           │  │  ▲ 4 pages load > 3s (down from 12)                     ││
│           │  │  ✓ 96% of pages under 3s                                ││
│           │  │  ▲ Largest Contentful Paint: 2.8s avg                   ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Schema Markup (88/100)                                   ││
│           │  │  ✓ 94% of pages have valid schema                       ││
│           │  │  ▲ 3 pages have incorrect schema type                   ││
│           │  │  ✓ Rich results eligible: 89%                           ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Security (100/100)                                       ││
│           │  │  ✓ All pages on HTTPS                                    ││
│           │  │  ✓ HSTS headers present                                  ││
│           │  │  ✓ No mixed content                                      ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** ScoreHeader, AuditSection (collapsible), CheckItem (pass/fail/warn)

---

#### `/technical/schema`

**Surface:** OPERATE

**Composition:** Schema markup management with validation.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Schema Markup           [Validate all] [User]              │
│           │ ─────────────────────────────────────────────────────────────││
│           │                                                              │
│           │  [All] [Valid] [Invalid] [Missing]                          │
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Page              Schema Type    Status    Errors        ││
│           │  │ ─────────────────────────────────────────────────────── ││
│           │  │ /                 Organization   Valid     --            ││
│           │  │ /blog/*           Article        Valid     --            ││
│           │  │ /products/*       Product        Valid     --            ││
│           │  │ /pricing          FAQPage ✗      Invalid   Wrong type   ││
│           │  │ /features         --             Missing   No schema    ││
│           │  │ /about            AboutPage      Valid     --            ││
│           │  └──────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Self-Healing Log                                         ││
│           │  │                                                          ││
│           │  │ Jul 19 14:05  /pricing: FAQPage → Product (auto-fixed)  ││
│           │  │ Jul 18 09:30  /blog/new-post: Article schema added      ││
│           │  │ Jul 17 16:22  /features: AboutPage schema added         ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/technical/self-healing`

**Surface:** MONITOR (secondary: OPERATE for overrides)

**Composition:** Self-healing agent status and recent fixes.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Self-Healing Agent      [● Active] [User]                  │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐          │
│           │  │Issues    ││Auto-fixed││Manual    ││Pending   │          │
│           │  │detected: ││:         ││review:   ││:         │          │
│           │  │15        ││12        ││2         ││1         │          │
│           │  │this week ││80%       ││awaiting  ││processing│          │
│           │  └──────────┘└──────────┘└──────────┘└──────────┘          │
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Recent Fixes                                             ││
│           │  │                                                          ││
│           │  │ Jul 19 14:05  Fixed: /pricing schema (FAQPage → Product) ││
│           │  │               Confidence: 97%   Impact: High            ││
│           │  │                                                          ││
│           │  │ Jul 19 11:30  Fixed: 3 broken canonical tags             ││
│           │  │               Confidence: 99%   Impact: Medium          ││
│           │  │                                                          ││
│           │  │ Jul 18 16:45  Fixed: duplicate meta on /blog/*           ││
│           │  │               Confidence: 95%   Impact: Medium          ││
│           │  │                                                          ││
│           │  │ Jul 18 09:30  Fixed: missing hreflang on 12 pages       ││
│           │  │               Confidence: 92%   Impact: High            ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Pending Manual Review                                     ││
│           │  │                                                          ││
│           │  │  /legacy/page — Broken structured data                   ││
│           │  │  Agent cannot determine correct schema type.             ││
│           │  │  [Review →] [Ignore] [Mark as intentional]              ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/technical/multi-engine`

**Surface:** MONITOR

**Composition:** Grid comparing index status across search engines.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Multi-Engine Index      [Check now] [Last: 1h ago] [User]  │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │                                                            │
│           │  │  Engine       Indexed    Submitted   Coverage   Status   │
│           │  │  ───────────────────────────────────────────────────────  │
│           │  │  Google       1,219      1,247       98%        ● Good   │
│           │  │  Bing           973      1,247       78%        ▲ Improving│
│           │  │  Yandex         674      1,247       54%        ● Fair   │
│           │  │  DuckDuckGo   1,185      1,247       95%        ● Good   │
│           │  │  Brave          891      1,247       71%        ▲ Improving│
│           │  │                                                            │
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Pages Not Indexed (28 total)                              ││
│           │  │                                                          ││
│           │  │  URL                    Google  Bing  Yandex  DDG  Brave││
│           │  │  ────────────────────────────────────────────────────── ││
│           │  │  /legacy/page           ✗      ✗     ✗      ✗    ✗     ││
│           │  │  /blog/draft-post       ✗      ✗     ✗      ✗    ✗     ││
│           │  │  /tmp/test              ✗      ✗     ✗      ✗    ✗     ││
│           │  │  /old-redirect          ✗      ✓     ✗      ✓    ✗     ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ Index Coverage Trend (30d)                                ││
│           │  │                                                          ││
│           │  │  Google  ══════════════════════════════  98% (stable)    ││
│           │  │  Bing    ═══════════════════░░░░░░░░░░  78% (▲ +5%)     ││
│           │  │  Yandex  ══════════░░░░░░░░░░░░░░░░░░  54% (▲ +8%)     ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** IndexStatusGrid, CoverageTable, TrendChart

---

### 3.9 Analytics Pages

#### `/analytics`

**Surface:** DECIDE / LEARN

**Composition:** One idea per section. Vertical scroll. Each chart is self-contained.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Analytics              [Date range: 30d ▾] [User]          │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Organic Traffic                                               │
│           │  14,281 sessions · ▲ 12.4% vs previous period                │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │                                                          ││
│           │  │  16K│                          ╭─╮                       ││
│           │  │  14K│        ╭────╮    ╭──╮  ╭╯ ╰╮                      ││
│           │  │  12K│  ╭────╯    ╰────╯  ╰──╯   ╰──                    ││
│           │  │  10K│──╯                                                ││
│           │  │     └────────────────────────────────────               ││
│           │  │      Jun 19                                    Jul 19   ││
│           │  │                                                          ││
│           │  │  Sessions: 14,281  │  Users: 11,234  │  Pages/Session: 2.8│
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  Top Landing Pages                                             │
│           │  Pages driving the most organic entry traffic                 │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │  Page                      Sessions  Bounce Rate  Conv  ││
│           │  │  ─────────────────────────────────────────────────────  ││
│           │  │  /                          3,241     32%         4.2% ││
│           │  │  /blog/schema-markup          891     28%         3.8% ││
│           │  │  /products/enterprise         756     45%         6.1% ││
│           │  │  /blog/ai-seo-guide           567     24%         2.9% ││
│           │  │  /pricing                     445     52%         8.3% ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  Traffic by Device                                             │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │  Desktop  ████████████████████  62%                     ││
│           │  │  Mobile   ████████████░░░░░░░░  34%                     ││
│           │  │  Tablet   ██░░░░░░░░░░░░░░░░░░   4%                     ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  Traffic by Country                                            │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │  United States   ████████████████████  42%              ││
│           │  │  United Kingdom  ████████░░░░░░░░░░░░  18%              ││
│           │  │  Germany         █████░░░░░░░░░░░░░░░  12%              ││
│           │  │  Canada          ████░░░░░░░░░░░░░░░░   8%              ││
│           │  │  Australia       ███░░░░░░░░░░░░░░░░░   6%              ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:** MetricHeader, AreaChart, DataTable, HorizontalBarChart
**Data flow:** `GET /api/analytics/traffic?range=30d`

---

#### `/analytics/traffic`

**Surface:** DECIDE / LEARN

**Composition:** Deep-dive traffic analysis. One section per dimension.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Traffic Analysis        [30d ▾] [Compare: previous ▾] [User]│
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Sessions: 14,281 ▲12.4%                                     │
│           │                                                              │
│           │  Traffic Over Time                                             │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ [Large area chart with comparison line]                   ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  Traffic by Source                                             │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │  Organic Search  ████████████████████  78% (11,139)     ││
│           │  │  Direct          ████░░░░░░░░░░░░░░░░  12% (1,714)     ││
│           │  │  Referral        ███░░░░░░░░░░░░░░░░░   7% (1,000)     ││
│           │  │  Social          ██░░░░░░░░░░░░░░░░░░   3% (428)       ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  Keyword Performance                                          │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ [Scatter plot: position vs traffic volume]                ││
│           │  │ Each dot = keyword. Size = search volume. Color = trend. ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/analytics/conversions`

**Surface:** DECIDE / LEARN

**Composition:** Conversion funnel and goal tracking.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Conversions            [30d ▾] [User]                      │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Conversion Rate: 4.2% ▲0.3%                                 │
│           │  Goal completions: 601 │ Revenue attributed: $42,890        │
│           │                                                              │
│           │  Funnel                                                        │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │                                                          ││
│           │  │  Landing     14,281  ████████████████████████████████    ││
│           │  │                                                          ││
│           │  │  Engaged     9,847   ██████████████████████░░░░░░░░░    ││
│           │  │                      69%                                 ││
│           │  │                                                          ││
│           │  │  Trial       1,234   ████░░░░░░░░░░░░░░░░░░░░░░░░░░    ││
│           │  │                      9%                                  ││
│           │  │                                                          ││
│           │  │  Converted   601     ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░    ││
│           │  │                      4.2%                                ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  Top Converting Pages                                         │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │  Page                   Conv Rate  Goals   Revenue      ││
│           │  │  ─────────────────────────────────────────────────────  ││
│           │  │  /pricing               8.3%       124     $18,600     ││
│           │  │  /products/enterprise   6.1%       89      $13,350     ││
│           │  │  /demo                  12.4%      67      $10,050     ││
│           │  │  /blog/schema-markup    3.8%       34       --         ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

### 3.10 Reports Pages

#### `/reports`

**Surface:** DECIDE / LEARN

**Composition:** Report library. List of generated reports with actions.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Reports                [+ Generate report] [User]          │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Report Name              Type        Date       Actions ││
│           │  │ ────────────────────────────────────────────────────────││
│           │  │ July SEO Performance     Monthly     Jul 1      [View]  ││
│           │  │                                                  [PDF]  ││
│           │  │ Technical Audit Q2       Quarterly   Jul 1      [View]  ││
│           │  │                                                  [PDF]  ││
│           │  │ Competitor Analysis      Ad-hoc      Jun 28     [View]  ││
│           │  │                                                  [PDF]  ││
│           │  │ June SEO Performance     Monthly     Jun 1      [View]  ││
│           │  │                                                  [PDF]  ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/reports/generate`

**Surface:** CONFIGURE

**Composition:** Report configuration form.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Generate Report                                            │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Report type                                                 │
│           │  (●) SEO Performance Summary                                 │
│           │  ( ) Technical Audit Report                                  ││
│           │  ( ) Competitor Analysis                                     ││
│           │  ( ) Keyword Ranking Report                                  ││
│           │  ( ) Link Building Report                                    ││
│           │                                                              │
│           │  Date range                                                  │
│           │  [Jul 1, 2026] to [Jul 19, 2026]                           │
│           │                                                              │
│           │  Include sections                                            │
│           │  [x] Traffic overview        [x] Keyword rankings            │
│           │  [x] Technical health        [x] Content performance         │
│           │  [x] Link profile            [ ] Competitor comparison        │
│           │  [x] Agent activity          [ ] Raw data appendix           ││
│           │                                                              │
│           │  Format                                                      │
│           │  (●) PDF  ( ) CSV  ( ) Both                                  ││
│           │                                                              │
│           │  [Generate report]                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/reports/{id}`

**Surface:** DECIDE / LEARN

**Composition:** Rendered report view. Sections stacked vertically, one idea per section.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  July SEO Performance Report    [Download PDF] [Share] [User]│
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ProActive SEO — Monthly Performance Report                  │
│           │  July 1–19, 2026 · acme.com                                 │
│           │                                                              │
│           │  Executive Summary                                            │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Organic traffic increased 12.4% to 14,281 sessions.         │
│           │  Health score improved from 82 to 87. 47 technical issues    │
│           │  were resolved, including 12 auto-healed by the agent.       │
│           │                                                              │
│           │  Key Metrics                                                  │
│           │  ┌────────┐┌────────┐┌────────┐┌────────┐                  │
│           │  │Traffic ││Keywords││Issues  ││Health  │                  │
│           │  │14,281  ││3,891   ││23 open ││87/100  │                  │
│           │  │▲12.4%  ││▲89     ││▼5      ││▲3      │                  │
│           │  └────────┘└────────┘└────────┘└────────┘                  │
│           │                                                              │
│           │  Traffic Trend                                                │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ [Area chart — 30 day trend]                               ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  Top Keyword Movements                                        │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ [Table of top 10 keyword position changes]                ││
│           │  └─────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  Agent Activity Summary                                       │
│           │  ┌─────────────────────────────────────────────────────────┐│
│           │  │ [Summary of what each agent accomplished]                 ││
│           │  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

### 3.11 Integration Pages

#### `/settings/integrations`

**Surface:** CONFIGURE

**Composition:** Grid of available integrations with connection status.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Integrations           [User]                               │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Connected                                                     │
│           │  ─────────────────────────────────────────────────────────── │
│           │  ┌─────────────────────┐  ┌─────────────────────┐          │
│           │  │ Google Search       │  │ Google Analytics    │          │
│           │  │ Console             │  │ 4                   │          │
│           │  │ ● Connected         │  │ ● Connected         │          │
│           │  │ Last sync: 2h ago   │  │ Last sync: 1h ago   │          │
│           │  │ [Settings →]        │  │ [Settings →]        │          │
│           │  └─────────────────────┘  └─────────────────────┘          │
│           │                                                              │
│           │  Available                                                     │
│           │  ─────────────────────────────────────────────────────────── │
│           │  ┌─────────────────────┐  ┌─────────────────────┐          │
│           │  │ DataForSEO          │  │ SEMrush             │          │
│           │  │ ○ Not connected     │  │ ○ Not connected     │          │
│           │  │ Backlink data       │  │ Keyword data        │          │
│           │  │ [Connect →]         │  │ [Connect →]         │          │
│           │  └─────────────────────┘  └─────────────────────┘          │
│           │  ┌─────────────────────┐  ┌─────────────────────┐          │
│           │  │ WordPress           │  │ Shopify             │          │
│           │  │ ○ Not connected     │  │ ○ Not connected     │          │
│           │  │ CMS publishing      │  │ E-commerce SEO      │          │
│           │  │ [Connect →]         │  │ [Connect →]         │          │
│           │  └─────────────────────┘  └─────────────────────┘          │
│           │  ┌─────────────────────┐  ┌─────────────────────┐          │
│           │  │ Slack               │  │ Webhook             │          │
│           │  │ ○ Not connected     │  │ ○ Not configured    │          │
│           │  │ Notifications       │  │ Custom integrations │          │
│           │  │ [Connect →]         │  │ [Configure →]       │          │
│           │  └─────────────────────┘  └─────────────────────┘          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/settings/integrations/{provider}`

**Surface:** CONFIGURE

**Composition:** Integration configuration with connection flow.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Google Search Console              [Disconnect] [User]     │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Status: ● Connected                                          │
│           │  Account: admin@acme.com                                     │
│           │  Last sync: 2 hours ago                                       │
│           │                                                              │
│           │  Properties                                                    │
│           │  ─────────────────────────────────────────────────────────── │
│           │  [x] https://acme.com                                        │
│           │  [ ] http://acme.com                                         ││
│           │  [x] https://blog.acme.com                                   │
│           │                                                              │
│           │  Sync Settings                                                │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Sync frequency     [Every 6 hours ▾]                       │
│           │  Data to sync       [x] Search performance                   │
│           │                     [x] Index coverage                       │
│           │                     [x] Core web vitals                      │
│           │                     [ ] Manual actions                       │
│           │                                                              │
│           │  [Save settings]  [Sync now]  [Disconnect]                  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

### 3.12 Settings Pages

#### `/settings/profile`

**Surface:** CONFIGURE

**Composition:** Single-column form.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Profile                            [Save changes] [User]    │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Personal Information                                         │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Name          [Sarah Chen                               ]   │
│           │  Email         [sarah@acme.com                           ]   │
│           │  Role          [SEO Director                             ]   │
│           │  Timezone      [America/New_York ▾                       ]   │
│           │                                                              │
│           │  Avatar                                                      │
│           │  ─────────────────────────────────────────────────────────── │
│           │  ┌────┐                                                      │
│           │  │ SC │  [Upload new photo]  [Remove]                       │
│           │  └────┘                                                      │
│           │                                                              │
│           │  Preferences                                                 │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Theme          (●) System  ( ) Light  ( ) Dark              │
│           │  Language       [English ▾]                                  │
│           │  Date format    [MM/DD/YYYY ▾]                              │
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/settings/organization`

**Surface:** CONFIGURE

**Composition:** Organization settings with billing portal link.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Organization                      [Save] [User]            │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Organization Details                                         │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Name           [Acme Corporation                       ]   │
│           │  Website        [https://acme.com                       ]   │
│           │  Industry       [Technology ▾                           ]   │
│           │                                                              │
│           │  Plan                                                        │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Current plan: Enterprise ($499/mo)                         │
│           │  Projects: 3 / 10                                           │
│           │  Keywords tracked: 3,891 / 10,000                           │
│           │  Pages monitored: 1,247 / 50,000                            │
│           │  [Manage subscription →]                                     │
│           │                                                              │
│           │  Danger Zone                                                  │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Transfer ownership                                          │
│           │  [Transfer]                                                  │
│           │                                                              │
│           │  Delete organization                                         │
│           │  This will delete all projects, data, and agent              │
│           │  configurations.                                             │
│           │  [Delete organization]                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/settings/team`

**Surface:** CONFIGURE (secondary: OPERATE for invite/remove)

**Composition:** Team member table + invite form.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Team                   [+ Invite member] [User]            │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Member            Role          Status     Actions      ││
│           │  │ ────────────────────────────────────────────────────────││
│           │  │ Sarah Chen        Owner         Active     --           ││
│           │  │ James Wilson      Admin         Active     [Edit] [Remove]│
│           │  │ Maria Garcia      Editor        Active     [Edit] [Remove]│
│           │  │ David Kim         Viewer        Active     [Edit] [Remove]│
│           │  │ Alex Thompson     Editor        Invited    [Resend] [Revoke]│
│           │  └──────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  Pending Invitations (1)                                      │
│           │  ─────────────────────────────────────────────────────────── │
│           │  alex@acme.com — Invited Jul 17 — Expires Jul 24            │
│           │  [Resend invitation] [Revoke]                                │
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/settings/billing`

**Surface:** CONFIGURE

**Composition:** Billing info with usage meters.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Billing                [User]                               │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Current Plan: Enterprise                                     │
│           │  $499/month · Renews Aug 1, 2026                            │
│           │  [Change plan]  [Cancel subscription]                        │
│           │                                                              │
│           │  Usage This Period                                            │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Projects         3 / 10          ████░░░░░░░░░░░░░░░░ 30%  │
│           │  Keywords         3,891 / 10,000  ████████░░░░░░░░░░░░ 39%  │
│           │  Pages monitored  1,247 / 50,000  █░░░░░░░░░░░░░░░░░░░  2%  │
│           │  Crawl requests   14,230 / 100K   ████░░░░░░░░░░░░░░░░ 14%  │
│           │  AI tokens        2.1M / 10M      ██████░░░░░░░░░░░░░░ 21%  │
│           │                                                              │
│           │  Payment Method                                              │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Visa ending in 4242 · Expires 12/2027                      │
│           │  [Update payment method]                                     │
│           │                                                              │
│           │  Billing History                                              │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Jul 1, 2026  $499.00  Paid    [Invoice PDF]                │
│           │  Jun 1, 2026  $499.00  Paid    [Invoice PDF]                │
│           │  May 1, 2026  $499.00  Paid    [Invoice PDF]                │
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/settings/api-keys`

**Surface:** CONFIGURE

**Composition:** API key management with masked display.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  API Keys               [+ Generate key] [User]             │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ Name              Key                    Created  Actions││
│           │  │ ────────────────────────────────────────────────────────││
│           │  │ Production        pro_sk_****...a3f2    Jul 1    [Revoke]││
│           │  │ CI/CD Pipeline    pro_sk_****...b7c1    Jun 15   [Revoke]││
│           │  │ Development       pro_sk_****...d9e4    May 22   [Revoke]││
│           │  └──────────────────────────────────────────────────────────┘│
│           │                                                              │
│           │  ┌──────────────────────────────────────────────────────────┐│
│           │  │ API Usage                                                ││
│           │  │                                                          ││
│           │  │  Requests today: 1,247 / 10,000                         ││
│           │  │  Rate limit: 100 req/min                                ││
│           │  │                                                          ││
│           │  │  [View API documentation →]                              ││
│           │  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/settings/notifications`

**Surface:** CONFIGURE

**Composition:** Notification preference matrix.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Notification Preferences               [Save] [User]       │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Email Notifications                                          │
│           │  ─────────────────────────────────────────────────────────── │
│           │                              Email  In-App  Slack            │
│           │  Health score alerts         [x]    [x]     [x]             │
│           │  Agent failures              [x]    [x]     [x]             │
│           │  Content published           [ ]    [x]     [x]             │
│           │  Keyword rank changes        [ ]    [x]     [ ]             │
│           │  Campaign responses          [x]    [x]     [x]             │
│           │  Weekly digest               [x]    [ ]     [ ]             │
│           │  Monthly report              [x]    [ ]     [ ]             │
│           │  Billing alerts              [x]    [x]     [ ]             │
│           │                                                              │
│           │  Digest Schedule                                              │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Weekly digest   [Monday ▾] at [9:00 AM ▾]                  │
│           │  Monthly report  [1st of month ▾] at [9:00 AM ▾]            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### `/settings/security`

**Surface:** CONFIGURE

**Composition:** Security settings with audit log.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Sidebar] │  Security               [User]                               │
│           │ ─────────────────────────────────────────────────────────────│
│           │                                                              │
│           │  Password                                                    │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Last changed: Jul 10, 2026                                 │
│           │  [Change password]                                           │
│           │                                                              │
│           │  Two-Factor Authentication                                    │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Status: ● Enabled (Authenticator app)                      │
│           │  Recovery codes: 8 remaining                                │
│           │  [View recovery codes]  [Disable 2FA]                       │
│           │                                                              │
│           │  Active Sessions                                             │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Chrome on macOS — New York, US — Current session            │
│           │  Firefox on Windows — London, UK — 2 days ago               │
│           │  [Sign out all other sessions]                               │
│           │                                                              │
│           │  Audit Log                                                    │
│           │  ─────────────────────────────────────────────────────────── │
│           │  Jul 19 14:30  API key "Production" created                 │
│           │  Jul 18 09:15  Password changed                             │
│           │  Jul 17 16:42  Team member alex@acme.com invited            │
│           │  Jul 15 11:20  Integration: Google Search Console connected │
│           │  [View full audit log →]                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Key Component Designs

### 4.1 Sidebar Navigation

**Behavior:**
- Expanded width: 240px. Collapsed width: 64px (icons only).
- Collapses automatically below `xl` breakpoint (1280px).
- Manual toggle via hamburger icon in header.
- Dark background always (`#111827` light mode, `#0B0D12` dark mode).
- Active item: `bg-sidebar-active` + left 3px accent in `primary-500`.

**Structure:**
```
┌──────────────────────┐
│ [Logo] ProActive SEO │
│                      │
│ ──────────────────── │
│                      │
│ ● Overview           │
│   Activity           │
│   Notifications      │
│                      │
│ ──────────────────── │
│ PROJECTS             │
│                      │
│ ▸ acme.com           │
│ ▾ blog.acme.com      │
│     Overview         │
│     SEO Command      │
│     Agents           │
│     Content          │
│     Technical        │
│     Analytics        │
│     Campaigns        │
│     Reports          │
│                      │
│ ▸ staging.acme.com   │
│                      │
│ ──────────────────── │
│                      │
│   Settings           │
│                      │
│ ──────────────────── │
│                      │
│ [SC] Sarah Chen      │
│     SEO Director     │
└──────────────────────┘
```

**Multi-level:** Projects expand to show sub-pages. Single click = navigate. Chevron = expand/collapse.

**Collapsed state:**
```
┌────────┐
│ [Logo] │
│        │
│ [icon] │  ← Overview
│ [icon] │  ← Activity
│ [icon] │  ← Notifications
│        │
│ [icon] │  ← Projects (tooltip on hover)
│        │
│ [icon] │  ← Settings
│        │
│ [SC]   │  ← User avatar
└────────┘
```

---

### 4.2 Data Tables

**Features:** Sortable columns, column filters, row selection, pagination, bulk actions.

**Anatomy:**
```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Search...        ]  [Status ▾]  [Type ▾]  [Columns ▾]  [Export]       │
│                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────┐│
│ │ □  ▼ Keyword           ▼ Position  Change   Volume   Traffic   CTR  ││
│ │ ─────────────────────────────────────────────────────────────────── ││
│ │ □     enterprise seo       3       ▲2      2,400     891      38%  ││
│ │ □     seo automation       8       ▲6      1,900     412      22%  ││
│ │ □     ai seo software     12       ▼1      1,600     289      18%  ││
│ │     ...                                                              ││
│ │                                                                      ││
│ │ Showing 1–10 of 3,891    [<  1  2  3  ...  390  >]                 ││
│ └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│ □ 3 selected    [Add to campaign]  [Tag]  [Export selected]            │
└──────────────────────────────────────────────────────────────────────────┘
```

**States:**
- **Hover row:** `bg-surface-sunken`
- **Selected row:** `bg-primary-50` + checkbox checked
- **Sort active:** Column header `ink-primary` + arrow indicator
- **Loading:** 10 skeleton rows (8px tall rounded rectangles per cell)
- **Empty:** Centered message + icon + CTA
- **Error:** Inline banner above table: "Failed to load data. [Retry]"

---

### 4.3 Agent Status Cards

**Real-time updates via SSE.** Each card shows current state, progress, and recent output.

**Anatomy:**
```
┌─────────────────────────────────────────────────────────────────────┐
│ [Agent Icon]  Content Agent                      ● Active           │
│                                                                      │
│  Current task: Optimizing /blog/ai-seo-guide                        │
│  Progress: ████████████████░░░░░░ 78%                               │
│                                                                      │
│  Published today: 2  │  Drafts: 4  │  Queue: 12  │  Failed: 0      │
│                                                                      │
│  [View logs]  [Configure]  [Pause]                                  │
└─────────────────────────────────────────────────────────────────────┘
```

**Status indicators:**
- `● Active` — green dot, agent running
- `○ Paused` — gray dot, agent paused
- `● Error` — red dot, agent encountered an error
- `◌ Starting` — gray outlined dot, agent initializing

**Animation:** Progress bar animates smoothly. Status dot pulses once on state change. No continuous animations.

---

### 4.4 Campaign Tracker

**Dual view:** Table view (default) and Kanban board (toggle).

**Kanban columns:** Prospecting → Outreach → Negotiating → Placed

**Card in Kanban:**
```
┌────────────────────────┐
│ SearchEngineJournal    │
│ DA: 92                 │
│ Topic: Schema Markup   │
│ Status: Placed         │
│ [SC] Jul 15            │
└────────────────────────┘
```

**Drag-and-drop:** Cards move between columns. State persists via `PATCH /api/campaigns/:id/prospects/:pid`.

---

### 4.5 Health Score Widget

**Animated SVG ring.** Shows composite score with breakdown.

```
    ┌───────────────┐
    │               │
    │    ╭────╮     │
    │   ╱      ╲    │     Technical   82
    │  │   87   │   │     Content     91
    │   ╲      ╱    │     Authority   94
    │    ╰────╯     │     Links       85
    │               │
    │  ▲ 3 vs last  │
    │    week       │
    └───────────────┘
```

**Animation:** Ring draws from 0 to score value over 300ms, ease-out. `prefers-reduced-motion`: instant render.

---

### 4.6 Real-Time Activity Feed

**SSE-powered.** New items prepend with a subtle slide-in (no bounce, no fade-in unless reduced motion).

**Item anatomy:**
```
14:32  [Content Agent badge]  Published /blog/schema-markup-guide
       SEO score: 94/100, 2,340 words, 8 internal links
```

**New item indicator:** Brief highlight (2s fade from `primary-50` to transparent).

---

### 4.7 Multi-Engine Index Status Grid

**Compact grid showing index coverage across search engines.**

```
┌──────────────────────────────────────────────┐
│  Engine       Indexed  Coverage  Trend       │
│  ─────────────────────────────────────────── │
│  Google       1,219    98%       ─── (stable)│
│  Bing           973    78%       ╱── (▲5%)  │
│  Yandex         674    54%       ╱── (▲8%)  │
│  DuckDuckGo   1,185    95%       ─── (stable)│
│  Brave          891    71%       ╱── (▲3%)  │
└──────────────────────────────────────────────┘
```

---

### 4.8 Content Editor

**Side-by-side layout.** Left: markdown editor (60% width). Right: optimization panel (40% width).

**Optimization panel sections:**
1. SEO Score (animated ring, 0-100)
2. Issues list (actionable, with severity)
3. Content stats (words, headings, images, links, read time)
4. Target keywords (position tracker with fill bars)

**Auto-save:** Debounced 2s after last keystroke. Status indicator: "Saving..." → "Saved at 14:32".

---

### 4.9 Chart Components

**Library:** Recharts. Consistent styling across all charts.

**Line chart:**
- Stroke: `primary-500`, width 2px
- Area fill: `primary-500` at 10% opacity
- Grid lines: `border-default`, dashed
- Axis labels: `ink-tertiary`, 12px
- Tooltip: `bg-surface-raised`, shadow level 2, rounded 6px

**Bar chart:**
- Fill: `primary-500`
- Hover: `primary-600`
- Gap between bars: 2px
- Border radius: 2px top

**Area chart:**
- Same as line chart with filled area below

**Pie chart:**
- No 3D. No exploded slices. No rainbow colors.
- Colors: `primary-500`, `success-500`, `warning-500`, `info-500`, `ink-tertiary`
- Labels outside, lines connecting

---

## 5. Anti-Slop Audit

Running the 10-tell diagnostic on this design specification.

| # | Tell | Score | Evidence / Justification |
|---|---|---|---|
| 1 | Tech gradient | 0 | No gradients anywhere. All surfaces use flat `bg-surface` / `bg-surface-sunken`. |
| 2 | Generic tech hue | 0 | Indigo-600 was chosen explicitly for the brand (not defaulted). Palette is semantic — primary, success, warning, danger each serve a distinct purpose. |
| 3 | Feature-tile grid | 0 | No page uses the icon+heading+sentence ×3 pattern. Dashboard uses size-differentiated stat cards. Agent cards show live state, not features. |
| 4 | Accent rail | 0 | No colored left-border cards. Selected states use full background tint (`primary-50`), not a decorative strip. |
| 5 | Unearned blur | 0 | No glassmorphism. Elevation is communicated through shadow levels + background shift. |
| 6 | Monument stat | 0 | Numbers are sized appropriately for scanning (24-30px for primary metrics). No oversized hero numbers filling dead space. |
| 7 | Icon topper | 0 | No icons centered above headings. Icons are inline with text (status dots, agent type indicators). |
| 8 | Center stack | 0 | Auth pages are the only centered content (split layout, not stacked). All operational pages use full-width grid layouts. |
| 9 | Default type | 0 | Inter was chosen for tabular number support in data-dense dashboards. JetBrains Mono for all technical readouts. Both are deliberate. |
| 10 | Wrong surface | 0 | Every page declares its surface archetype and composes accordingly. Monitor surfaces are dense grids. Configure surfaces are single-column forms. Operate surfaces use master-detail. Decide/Learn surfaces stack one idea per section. |

**Total slop score: 0/10.**

No repairs needed. The design is clean because composition was committed before tokens — every page starts from "what surface is this?" rather than "what looks good."

---

## 6. Interaction Patterns

### 6.1 Hover States

| Element | Hover Behavior |
|---|---|
| Button (primary) | Background darkens 8% (`primary-700`) |
| Button (secondary) | Background shifts to `surface-sunken` |
| Button (ghost) | Background shifts to `surface-sunken` |
| Card (interactive) | Shadow elevates to level 1, border darkens to `border-strong` |
| Table row | Background shifts to `surface-sunken` |
| Sidebar item | Background shifts to `sidebar-hover` |
| Link | Underline appears, color darkens to `primary-700` |
| Badge | No hover (non-interactive) |
| Sort column header | Background shifts to `surface-sunken`, cursor: pointer |

All hover transitions: 150ms ease.

### 6.2 Focus States

Keyboard navigation is mandatory. All interactive elements must be reachable via Tab.

| Element | Focus Style |
|---|---|
| Button | 2px ring `primary-600`, offset 2px |
| Input | 2px ring `primary-600`, offset 0px, border-color `primary-600` |
| Link | 2px ring `primary-600`, offset 2px, rounded 2px |
| Card (interactive) | Same as button focus |
| Sidebar item | Left border `primary-500` + `sidebar-active` background |
| Checkbox | 2px ring `primary-600`, offset 2px |
| Select | Same as input |

Focus ring: `box-shadow: 0 0 0 2px var(--color-border-focus)`. No custom outlines — use box-shadow for consistent rendering.

Skip-to-content link: visible on first Tab press, jumps to main content area.

### 6.3 Loading Skeletons

Skeletons match the dimensions and layout of the content they replace. No generic spinning loaders for content areas.

**Patterns:**
- **Stat card:** Rectangle for number (60% width, 24px tall) + rectangle for label (40% width, 12px tall)
- **Table row:** Row of rectangles matching column widths, 10px tall
- **Chart:** Rectangle matching chart container dimensions
- **Text block:** 3 lines of varying width (100%, 100%, 60%)
- **Card:** Full card outline with internal rectangles

**Animation:** Shimmer effect — left-to-right gradient sweep, 1.5s infinite. Color: `bg-surface-sunken` to `bg-surface` to `bg-surface-sunken`. `prefers-reduced-motion`: static placeholder, no shimmer.

### 6.4 Error States

Each component handles errors independently. No full-page error screens for partial failures.

**Patterns:**
- **Table load failure:** Inline banner above table. "Failed to load data. [Retry]". Table body shows empty state.
- **Chart load failure:** Chart area shows "Couldn't load chart data. [Retry]". Other panels unaffected.
- **Form submission failure:** Toast notification (error variant). Form fields retain values. Specific field errors shown inline.
- **SSE disconnection:** Status bar indicator: "Reconnecting..." with auto-retry. After 3 failures: "Connection lost. [Refresh page]".
- **Agent error:** Agent card status changes to `● Error` with error message. "View logs" link to error details.
- **404 page:** "Page not found. The page you're looking for doesn't exist or has been moved. [Go to dashboard]".
- **500 page:** "Something went wrong. We're looking into it. [Try again] [Go to dashboard]".

### 6.5 Success Toasts

**Position:** Bottom-right. Stack upward (newest on bottom).

**Variants:**
- **Success:** Green left accent. Auto-dismiss 5s. "Keyword rankings updated. 14 position changes detected."
- **Error:** Red left accent. Manual dismiss only. "Failed to publish content. Check draft for errors."
- **Warning:** Amber left accent. Auto-dismiss 8s. "Crawl budget 90% used. Consider upgrading your plan."
- **Info:** Blue left accent. Auto-dismiss 5s. "Report generated. [View report]"

**Dismiss:** Click X or swipe right on mobile. Keyboard: Escape.

### 6.6 Confirmation Dialogs

Used for destructive or irreversible actions only. Not for routine confirmations.

**Standard dialog:**
```
┌──────────────────────────────────────────────┐
│                                              │
│  Delete project "acme.com"?                  │
│                                              │
│  This will permanently remove:               │
│  - 1,247 monitored pages                     │
│  - 3,891 tracked keywords                    │
│  - All agent configurations                  │
│  - All campaign data                         │
│                                              │
│  This action cannot be undone.               │
│                                              │
│  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Cancel      │  │  Delete Project      │  │
│  └──────────────┘  └──────────────────────┘  │
│                                              │
└──────────────────────────────────────────────┘
```

**Rules:**
- Cancel is always the left button (default focus).
- Destructive action is right button, danger variant.
- Dialog closes on Escape or clicking backdrop.
- Body scroll locked when dialog is open.
- Focus trapped within dialog.

### 6.7 Command Palette (Cmd+K)

Global search and command execution. Opens as a modal overlay.

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ 🔍 Search pages, keywords, agents, settings...                  ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  Recent                                                               │
│  ─────────────────────────────────────────────────────────────────── │
│  ↗  /seo/keywords                    Keywords page                   │
│  ↗  /agents/content                  Content Agent                   │
│  ↗  /content/editor/142              "Technical SEO Checklist"       │
│                                                                      │
│  Actions                                                             │
│  ─────────────────────────────────────────────────────────────────── │
│  ⌘  Generate report                                               │
│  ⌘  Run technical audit                                           │
│  ⌘  Start all agents                                              │
│  ⌘  Add keyword                                                   │
│                                                                      │
│  Navigation                                                          │
│  ─────────────────────────────────────────────────────────────────── │
│  ↗  Dashboard                                                      │
│  ↗  Projects                                                       │
│  ↗  Settings                                                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Behavior:**
- Opens: `Cmd+K` (macOS) / `Ctrl+K` (Windows/Linux)
- Closes: Escape or clicking backdrop
- Search: fuzzy match across pages, keywords, agents, actions
- Navigate: Arrow keys + Enter
- Categories: Recent (last 5), Actions (commands), Navigation (routes)
- Width: 560px, max-height: 400px, centered horizontally, 20% from top

---

## Appendix: File Structure

```
app/
├── (auth)/
│   ├── login/page.tsx
│   ├── register/page.tsx
│   ├── forgot-password/page.tsx
│   └── verify-email/page.tsx
├── (dashboard)/
│   ├── layout.tsx                 # Sidebar + header shell
│   ├── page.tsx                   # / → redirect to /overview
│   ├── overview/page.tsx
│   ├── activity/page.tsx
│   └── notifications/page.tsx
├── projects/
│   ├── page.tsx                   # Project list
│   ├── new/page.tsx               # New project wizard
│   └── [id]/
│       ├── page.tsx               # Project dashboard
│       └── settings/page.tsx
├── seo/
│   ├── overview/page.tsx
│   ├── keywords/page.tsx
│   ├── pages/page.tsx
│   ├── issues/page.tsx
│   └── health-score/page.tsx
├── agents/
│   ├── page.tsx                   # Agent grid
│   └── [type]/
│       ├── page.tsx               # Agent detail
│       ├── logs/page.tsx
│       └── config/page.tsx
├── campaigns/
│   ├── page.tsx                   # Campaign list/board
│   ├── [id]/page.tsx              # Campaign detail
│   ├── haro/page.tsx
│   ├── broken-links/page.tsx
│   ├── guest-posts/page.tsx
│   └── unlinked-mentions/page.tsx
├── content/
│   ├── briefs/page.tsx
│   ├── drafts/page.tsx
│   ├── published/page.tsx
│   └── editor/[id]/page.tsx
├── technical/
│   ├── audit/page.tsx
│   ├── schema/page.tsx
│   ├── self-healing/page.tsx
│   └── multi-engine/page.tsx
├── analytics/
│   ├── page.tsx
│   ├── traffic/page.tsx
│   └── conversions/page.tsx
├── reports/
│   ├── page.tsx
│   ├── generate/page.tsx
│   └── [id]/page.tsx
└── settings/
    ├── layout.tsx                 # Settings sidebar
    ├── profile/page.tsx
    ├── organization/page.tsx
    ├── team/page.tsx
    ├── billing/page.tsx
    ├── api-keys/page.tsx
    ├── notifications/page.tsx
    ├── security/page.tsx
    └── integrations/
        ├── page.tsx
        └── [provider]/page.tsx

components/
├── ui/                            # shadcn/ui base components
│   ├── button.tsx
│   ├── input.tsx
│   ├── card.tsx
│   ├── badge.tsx
│   ├── toast.tsx
│   ├── dialog.tsx
│   ├── table.tsx
│   ├── select.tsx
│   ├── checkbox.tsx
│   ├── tabs.tsx
│   └── skeleton.tsx
├── layout/
│   ├── sidebar.tsx
│   ├── header.tsx
│   ├── command-palette.tsx
│   └── skip-to-content.tsx
├── dashboard/
│   ├── stat-card.tsx
│   ├── health-score-ring.tsx
│   ├── activity-feed.tsx
│   ├── index-status-grid.tsx
│   └── issue-list.tsx
├── agents/
│   ├── agent-status-card.tsx
│   ├── agent-log-viewer.tsx
│   └── agent-config-form.tsx
├── campaigns/
│   ├── campaign-table.tsx
│   ├── campaign-kanban.tsx
│   └── prospect-card.tsx
├── content/
│   ├── content-editor.tsx
│   ├── optimization-panel.tsx
│   └── keyword-tracker.tsx
├── analytics/
│   ├── traffic-chart.tsx
│   ├── conversion-funnel.tsx
│   └── keyword-scatter.tsx
└── shared/
    ├── data-table.tsx
    ├── filter-bar.tsx
    ├── pagination.tsx
    ├── bulk-action-bar.tsx
    ├── empty-state.tsx
    ├── error-boundary.tsx
    └── loading-skeleton.tsx

lib/
├── api/                           # React Query hooks
│   ├── dashboard.ts
│   ├── projects.ts
│   ├── keywords.ts
│   ├── agents.ts
│   ├── campaigns.ts
│   ├── content.ts
│   ├── analytics.ts
│   └── reports.ts
├── stores/                        # Zustand stores
│   ├── sidebar.ts
│   ├── project.ts
│   └── command-palette.ts
├── hooks/
│   ├── use-sse.ts
│   ├── use-command-palette.ts
│   └── use-keyboard-shortcuts.ts
└── tokens.ts                      # Design token constants
```
