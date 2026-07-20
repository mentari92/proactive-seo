"""
TechnicalAgent -- Core Web Vitals monitoring, JSON-LD schema generation,
self-healing (auto-fix 8 issue types), and multi-engine technical validation.

Spec: docs/04-agent-system.md section 4
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.agents.base import AgentPriority, AgentState, BaseAgent, RetryPolicy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CWV thresholds (from spec 4.7)
# ---------------------------------------------------------------------------

CWV_THRESHOLDS = {
    "lcp_ms": {"good": 2500, "needs_improvement": 4000},
    "fid_ms": {"good": 100, "needs_improvement": 300},
    "cls":    {"good": 0.1, "needs_improvement": 0.25},
    "inp_ms": {"good": 200, "needs_improvement": 500},
    "ttfb_ms": {"good": 800, "needs_improvement": 1800},
}


def evaluate_cwv_status(metrics: dict[str, float]) -> str:
    """Evaluate overall CWV status from metric values."""
    poor_count = 0
    needs_improvement_count = 0

    for metric, value in metrics.items():
        thresholds = CWV_THRESHOLDS.get(metric)
        if thresholds is None:
            continue
        if value > thresholds["needs_improvement"]:
            poor_count += 1
        elif value > thresholds["good"]:
            needs_improvement_count += 1

    if poor_count >= 2:
        return "poor"
    if poor_count >= 1 or needs_improvement_count >= 2:
        return "needs_improvement"
    return "good"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CWVResult:
    """Core Web Vitals measurement result for a single URL."""
    url: str
    lab: dict[str, float] = field(default_factory=dict)
    field_data: dict[str, float] = field(default_factory=dict)
    status: str = "unknown"       # good | needs_improvement | poor
    performance_score: float = 0.0
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "lab": self.lab,
            "field": self.field_data,
            "status": self.status,
            "performance_score": self.performance_score,
            "opportunities": self.opportunities,
            "checked_at": self.checked_at,
        }


@dataclass
class SelfHealResult:
    """Result of a self-healing action."""
    issue_type: str
    url: str
    fix: dict[str, Any]
    confidence: float
    auto_applied: bool = False
    status: str = "fix_proposed"   # fix_proposed | pending_approval | applied | failed

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "url": self.url,
            "fix": self.fix,
            "confidence": self.confidence,
            "auto_applied": self.auto_applied,
            "status": self.status,
        }


@dataclass
class TechValidationResult:
    """Multi-engine technical SEO validation result."""
    url: str
    checks: dict[str, Any] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "checks": self.checks,
            "issues_count": len(self.issues),
            "issues": self.issues,
            "score": self.score,
        }


# ---------------------------------------------------------------------------
# 8 Healable Issue Types (spec 4.1)
# ---------------------------------------------------------------------------

HEALABLE_ISSUES: dict[str, dict[str, Any]] = {
    "missing_title":       {"confidence": 0.95, "auto_fix": True},
    "missing_meta_desc":   {"confidence": 0.90, "auto_fix": True},
    "missing_h1":          {"confidence": 0.85, "auto_fix": True},
    "missing_alt_text":    {"confidence": 0.80, "auto_fix": True},
    "broken_canonical":    {"confidence": 0.90, "auto_fix": True},
    "missing_schema":      {"confidence": 0.85, "auto_fix": True},
    "duplicate_meta":      {"confidence": 0.75, "auto_fix": False},
    "redirect_chain":      {"confidence": 0.95, "auto_fix": True},
}


# ---------------------------------------------------------------------------
# PageSpeed Insights Client
# ---------------------------------------------------------------------------

class PageSpeedInsightsClient:
    """Wrapper for Google PageSpeed Insights API."""

    BASE_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    async def analyze(
        self, url: str, client: httpx.AsyncClient, strategy: str = "mobile"
    ) -> dict[str, Any]:
        """Run PageSpeed Insights analysis on a URL."""
        params: dict[str, Any] = {
            "url": url,
            "strategy": strategy,
            "category": ["performance", "accessibility", "best-practices", "seo"],
        }
        if self.api_key:
            params["key"] = self.api_key

        resp = await client.get(self.BASE_URL, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        lh = data.get("lighthouseResult", {})
        audits = lh.get("audits", {})
        categories = lh.get("categories", {})

        # Extract CWV metrics
        lcp_audit = audits.get("largest-contentful-paint", {})
        fid_audit = audits.get("max-potential-fid", {})
        cls_audit = audits.get("cumulative-layout-shift", {})
        inp_audit = audits.get("experimental-interaction-to-next-paint", {})
        ttfb_audit = audits.get("server-response-time", {})

        # Extract opportunities
        opportunities = []
        for audit in audits.values():
            if (
                audit.get("score") is not None
                and audit["score"] < 1
                and audit.get("details", {}).get("overallSavingsMs", 0) > 0
            ):
                opportunities.append({
                    "id": audit.get("id", ""),
                    "title": audit.get("title", ""),
                    "savings_ms": audit["details"]["overallSavingsMs"],
                    "description": audit.get("description", ""),
                })

        return {
            "performance_score": (categories.get("performance", {}).get("score", 0) or 0) * 100,
            "accessibility_score": (categories.get("accessibility", {}).get("score", 0) or 0) * 100,
            "seo_score": (categories.get("seo", {}).get("score", 0) or 0) * 100,
            "best_practices_score": (categories.get("best-practices", {}).get("score", 0) or 0) * 100,
            "lcp_ms": lcp_audit.get("numericValue", 0),
            "fid_ms": fid_audit.get("numericValue", 0),
            "cls": cls_audit.get("numericValue", 0),
            "inp_ms": inp_audit.get("numericValue"),
            "ttfb_ms": ttfb_audit.get("numericValue", 0),
            "opportunities": opportunities,
        }


# ---------------------------------------------------------------------------
# Schema Markup Engine
# ---------------------------------------------------------------------------

class SchemaMarkupEngine:
    """Generate comprehensive JSON-LD schema markup for pages."""

    def generate(self, page_data: dict[str, Any]) -> dict[str, Any]:
        """
        Generate JSON-LD schema based on page type.

        page_data keys:
            url, title, meta_description, content_type,
            author, publish_date, modified_date, featured_image,
            faqs, steps, organization, site_name, breadcrumb
        """
        schemas: list[dict[str, Any]] = []
        url = page_data.get("url", "")
        parsed = urlparse(url)

        # Organization (always)
        org = page_data.get("organization", {})
        org_schema = {
            "@type": "Organization",
            "@id": f"{parsed.scheme}://{parsed.netloc}#organization",
            "name": org.get("name", parsed.netloc),
            "url": f"{parsed.scheme}://{parsed.netloc}",
        }
        if org.get("logo"):
            org_schema["logo"] = org["logo"]
        schemas.append(org_schema)

        # WebSite (always)
        schemas.append({
            "@type": "WebSite",
            "@id": f"{parsed.scheme}://{parsed.netloc}#website",
            "name": page_data.get("site_name", parsed.netloc),
            "url": f"{parsed.scheme}://{parsed.netloc}",
            "publisher": {"@id": org_schema["@id"]},
        })

        # BreadcrumbList (always)
        breadcrumb = page_data.get("breadcrumb", [])
        if breadcrumb:
            schemas.append({
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i + 1,
                        "name": item.get("name", ""),
                        "item": item.get("url", ""),
                    }
                    for i, item in enumerate(breadcrumb)
                ],
            })

        # Article / BlogPosting
        content_type = page_data.get("content_type", "")
        if content_type in ("article", "blog_post"):
            article_type = "BlogPosting" if content_type == "blog_post" else "Article"
            article: dict[str, Any] = {
                "@type": article_type,
                "headline": page_data.get("title", ""),
                "description": page_data.get("meta_description", ""),
                "mainEntityOfPage": url,
                "datePublished": page_data.get("publish_date", ""),
                "dateModified": page_data.get("modified_date", page_data.get("publish_date", "")),
                "publisher": {"@id": org_schema["@id"]},
            }
            if page_data.get("author"):
                article["author"] = {
                    "@type": "Person",
                    "name": page_data["author"],
                }
            if page_data.get("featured_image"):
                article["image"] = page_data["featured_image"]
            schemas.append(article)

        # FAQPage
        faqs = page_data.get("faqs", [])
        if faqs:
            schemas.append({
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": faq.get("question", ""),
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": faq.get("answer", ""),
                        },
                    }
                    for faq in faqs
                ],
            })

        # HowTo
        steps = page_data.get("steps", [])
        if steps:
            howto: dict[str, Any] = {
                "@type": "HowTo",
                "name": page_data.get("title", ""),
                "step": [
                    {
                        "@type": "HowToStep",
                        "position": i + 1,
                        "name": step.get("name", ""),
                        "text": step.get("text", ""),
                    }
                    for i, step in enumerate(steps)
                ],
            }
            schemas.append(howto)

        # Product
        if content_type == "product":
            product = page_data.get("product", {})
            product_schema: dict[str, Any] = {
                "@type": "Product",
                "name": product.get("name", page_data.get("title", "")),
                "description": product.get("description", page_data.get("meta_description", "")),
            }
            if product.get("image"):
                product_schema["image"] = product["image"]
            if product.get("brand"):
                product_schema["brand"] = {"@type": "Brand", "name": product["brand"]}
            if product.get("offers"):
                product_schema["offers"] = {
                    "@type": "Offer",
                    "price": product["offers"].get("price", ""),
                    "priceCurrency": product["offers"].get("currency", "USD"),
                    "availability": product["offers"].get("availability", "https://schema.org/InStock"),
                }
            if product.get("rating"):
                product_schema["aggregateRating"] = {
                    "@type": "AggregateRating",
                    "ratingValue": product["rating"].get("value", ""),
                    "reviewCount": product["rating"].get("count", "0"),
                }
            schemas.append(product_schema)

        # Merge into @graph
        return {
            "@context": "https://schema.org",
            "@graph": schemas,
        }

    def validate(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Basic local JSON-LD validation."""
        errors: list[str] = []

        if "@context" not in schema:
            errors.append("Missing @context")
        if "@graph" not in schema:
            errors.append("Missing @graph (or top-level @type)")

        for item in schema.get("@graph", []):
            if "@type" not in item:
                errors.append(f"Graph item missing @type: {json.dumps(item)[:100]}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }


# ---------------------------------------------------------------------------
# Self-Healing Engine
# ---------------------------------------------------------------------------

class SelfHealingEngine:
    """
    Auto-fix 8 technical issue types.

    Issue types:
        missing_title, missing_meta_desc, missing_h1, missing_alt_text,
        broken_canonical, missing_schema, duplicate_meta, redirect_chain
    """

    def __init__(self, confidence_threshold: float = 0.8, schema_engine: SchemaMarkupEngine | None = None):
        self.confidence_threshold = confidence_threshold
        self.schema_engine = schema_engine or SchemaMarkupEngine()

    def detect_issues(self, html: str, url: str) -> list[dict[str, Any]]:
        """Detect all 8 healable issue types from HTML content."""
        soup = BeautifulSoup(html, "html.parser")
        issues: list[dict[str, Any]] = []

        # 1. Missing title
        title_tag = soup.find("title")
        if not title_tag or not title_tag.get_text(strip=True):
            issues.append({"type": "missing_title", "url": url})

        # 2. Missing meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if not meta_desc or not meta_desc.get("content", "").strip():
            issues.append({"type": "missing_meta_desc", "url": url})

        # 3. Missing H1
        h1_tag = soup.find("h1")
        if not h1_tag or not h1_tag.get_text(strip=True):
            issues.append({"type": "missing_h1", "url": url})

        # 4. Missing alt text on images
        images = soup.find_all("img")
        images_no_alt = [img for img in images if not img.get("alt", "").strip()]
        if images_no_alt:
            issues.append({
                "type": "missing_alt_text",
                "url": url,
                "count": len(images_no_alt),
                "images": [img.get("src", "") for img in images_no_alt[:20]],
            })

        # 5. Broken canonical
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical:
            href = canonical.get("href", "")
            if not href or href == url:
                # Same URL canonical is fine; missing/broken is the issue
                pass
        else:
            issues.append({"type": "broken_canonical", "url": url, "detail": "no_canonical_tag"})

        # 6. Missing schema markup
        schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        if not schema_scripts:
            issues.append({"type": "missing_schema", "url": url})

        # 7. Duplicate meta (checked at agent level, not per-page)
        # This would require cross-page analysis -- flag for later

        # 8. Redirect chain (detected during crawling, not from HTML)

        return issues

    def generate_fix(
        self, issue_type: str, page_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Generate a fix proposal for a detected issue."""
        healable = HEALABLE_ISSUES.get(issue_type)
        if not healable:
            return None

        if healable["confidence"] < self.confidence_threshold:
            return {
                "type": "recommendation",
                "issue": issue_type,
                "confidence": healable["confidence"],
                "requires_approval": True,
                "message": f"Issue '{issue_type}' below confidence threshold ({self.confidence_threshold})",
            }

        match issue_type:
            case "missing_title":
                h1 = page_data.get("h1", "")
                keyword = page_data.get("target_keyword", "")
                title = h1 or keyword or "Page Title"
                if keyword and keyword.lower() not in title.lower():
                    title = f"{title} | {keyword}"
                return {
                    "type": "inject_meta",
                    "tag": "title",
                    "value": title[:60],
                    "confidence": healable["confidence"],
                    "auto_applied": healable["auto_fix"],
                }

            case "missing_meta_desc":
                content_preview = page_data.get("content", "")[:500]
                keyword = page_data.get("target_keyword", "")
                # Simple extraction: first meaningful sentence
                sentences = re.split(r'[.!?]+', content_preview)
                desc = next((s.strip() for s in sentences if len(s.strip()) > 40), content_preview[:155])
                if keyword and keyword.lower() not in desc.lower():
                    desc = f"{desc} Learn more about {keyword}."
                return {
                    "type": "inject_meta",
                    "tag": "meta_description",
                    "value": desc[:155],
                    "confidence": healable["confidence"],
                    "auto_applied": healable["auto_fix"],
                }

            case "missing_h1":
                title = page_data.get("title", "")
                keyword = page_data.get("target_keyword", "")
                h1 = title or keyword or "Page Heading"
                return {
                    "type": "inject_element",
                    "tag": "h1",
                    "value": h1,
                    "confidence": healable["confidence"],
                    "auto_applied": healable["auto_fix"],
                }

            case "missing_alt_text":
                images = page_data.get("images_without_alt", [])
                fixes = []
                for img in images[:20]:
                    src = img if isinstance(img, str) else img.get("src", "")
                    alt_text = self._generate_alt_from_url(src, page_data.get("content", ""))
                    fixes.append({"src": src, "alt": alt_text})
                return {
                    "type": "inject_attribute",
                    "attribute": "alt",
                    "fixes": fixes,
                    "confidence": healable["confidence"],
                    "auto_applied": healable["auto_fix"],
                }

            case "broken_canonical":
                correct_url = page_data.get("final_url", page_data.get("url", ""))
                return {
                    "type": "inject_link",
                    "rel": "canonical",
                    "href": correct_url,
                    "confidence": healable["confidence"],
                    "auto_applied": healable["auto_fix"],
                }

            case "missing_schema":
                schema = self.schema_engine.generate(page_data)
                return {
                    "type": "inject_schema",
                    "json_ld": schema,
                    "confidence": healable["confidence"],
                    "auto_applied": healable["auto_fix"],
                }

            case "redirect_chain":
                chain = page_data.get("redirect_chain", [])
                target = chain[-1] if chain else page_data.get("final_url", "")
                return {
                    "type": "update_redirect",
                    "from_url": page_data.get("url", ""),
                    "to_url": target,
                    "status": 301,
                    "confidence": healable["confidence"],
                    "auto_applied": healable["auto_fix"],
                }

            case "duplicate_meta":
                return {
                    "type": "recommendation",
                    "issue": "duplicate_meta",
                    "message": "Duplicate meta tags detected. Requires content analysis for proper fix.",
                    "duplicates": page_data.get("duplicates", []),
                    "confidence": healable["confidence"],
                    "auto_applied": False,
                    "requires_approval": True,
                }

        return None

    @staticmethod
    def _generate_alt_from_url(src: str, context: str = "") -> str:
        """Generate a reasonable alt text from image URL and page context."""
        parsed = urlparse(src)
        filename = parsed.path.split("/")[-1].rsplit(".", 1)[0] if parsed.path else ""
        # Clean up common filename patterns
        alt = re.sub(r"[-_]+", " ", filename).strip()
        alt = re.sub(r"\b(img|image|photo|pic|dsc|img)\b", "", alt, flags=re.IGNORECASE).strip()
        if alt:
            return alt[:125]
        # Fallback: use first few words of context
        words = context.split()[:8]
        return " ".join(words) if words else "Image"


# ---------------------------------------------------------------------------
# Multi-Engine Technical Validator
# ---------------------------------------------------------------------------

class MultiEngineValidator:
    """Cross-engine technical SEO validation."""

    def validate_page(self, html: str, url: str) -> TechValidationResult:
        """Run all technical checks on a page."""
        soup = BeautifulSoup(html, "html.parser")
        checks: dict[str, Any] = {}
        issues: list[dict[str, Any]] = []
        score = 100.0

        # 1. Title check
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        checks["title"] = {"present": bool(title), "length": len(title)}
        if not title:
            issues.append({"type": "missing_title", "severity": "high", "points": -15})
            score -= 15
        elif len(title) > 60:
            issues.append({"type": "title_too_long", "severity": "medium", "length": len(title), "points": -5})
            score -= 5

        # 2. Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        desc = meta_desc.get("content", "") if meta_desc else ""
        checks["meta_description"] = {"present": bool(desc), "length": len(desc)}
        if not desc:
            issues.append({"type": "missing_meta_desc", "severity": "high", "points": -10})
            score -= 10
        elif len(desc) > 155:
            issues.append({"type": "meta_desc_too_long", "severity": "low", "length": len(desc), "points": -3})
            score -= 3

        # 3. H1 check
        h1_tags = soup.find_all("h1")
        checks["h1"] = {"count": len(h1_tags), "text": h1_tags[0].get_text(strip=True) if h1_tags else ""}
        if len(h1_tags) == 0:
            issues.append({"type": "missing_h1", "severity": "high", "points": -10})
            score -= 10
        elif len(h1_tags) > 1:
            issues.append({"type": "multiple_h1", "severity": "medium", "count": len(h1_tags), "points": -5})
            score -= 5

        # 4. Canonical
        canonical = soup.find("link", attrs={"rel": "canonical"})
        checks["canonical"] = {"present": canonical is not None, "href": canonical.get("href", "") if canonical else ""}
        if not canonical:
            issues.append({"type": "missing_canonical", "severity": "medium", "points": -5})
            score -= 5

        # 5. Viewport
        viewport = soup.find("meta", attrs={"name": "viewport"})
        checks["viewport"] = {"present": viewport is not None}
        if not viewport:
            issues.append({"type": "missing_viewport", "severity": "high", "points": -10})
            score -= 10

        # 6. Schema markup
        schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        checks["schema"] = {"count": len(schema_scripts), "present": len(schema_scripts) > 0}
        if not schema_scripts:
            issues.append({"type": "missing_schema", "severity": "medium", "points": -5})
            score -= 5

        # 7. Open Graph tags
        og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
        checks["open_graph"] = {"count": len(og_tags), "present": len(og_tags) > 0}
        if not og_tags:
            issues.append({"type": "missing_og_tags", "severity": "low", "points": -3})
            score -= 3

        # 8. Image alt text
        images = soup.find_all("img")
        no_alt = sum(1 for img in images if not img.get("alt", "").strip())
        checks["images"] = {"total": len(images), "missing_alt": no_alt}
        if no_alt > 0:
            penalty = min(no_alt * 2, 10)
            issues.append({"type": "images_missing_alt", "severity": "medium", "count": no_alt, "points": -penalty})
            score -= penalty

        # 9. HTTPS check
        checks["https"] = {"secure": url.startswith("https://")}
        if not url.startswith("https://"):
            issues.append({"type": "not_https", "severity": "high", "points": -15})
            score -= 15

        # 10. Internal/external link ratio
        all_links = soup.find_all("a", href=True)
        parsed_url = urlparse(url)
        internal = sum(1 for a in all_links if urlparse(a["href"]).netloc in ("", parsed_url.netloc))
        checks["links"] = {"total": len(all_links), "internal": internal, "external": len(all_links) - internal}

        score = max(0.0, min(100.0, score))

        return TechValidationResult(
            url=url,
            checks=checks,
            issues=issues,
            score=round(score, 1),
        )


# ---------------------------------------------------------------------------
# Technical Agent
# ---------------------------------------------------------------------------

class TechnicalAgent(BaseAgent):
    """
    Technical SEO Agent -- monitors CWV, generates schema, self-heals issues.

    State machine: IDLE -> MONITORING -> DETECTING -> HEALING -> VALIDATING -> IDLE
    """

    agent_name: str = "technical"

    transitions: dict[AgentState, dict[str, AgentState]] = {
        AgentState.IDLE:        {"start_monitor": AgentState.WORKING},
        AgentState.WORKING:     {"monitor_complete": AgentState.ANALYZING, "monitor_failed": AgentState.ERROR},
        AgentState.ANALYZING:   {"analysis_complete": AgentState.REPORTING},
        AgentState.REPORTING:   {"report_sent": AgentState.WAITING},
        AgentState.WAITING:     {"interval_elapsed": AgentState.IDLE, "priority_override": AgentState.WORKING},
        AgentState.ERROR:       {"retry": AgentState.WORKING, "max_retries": AgentState.DEAD_LETTER},
    }

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.pagespeed_client = PageSpeedInsightsClient(
            api_key=os.getenv("PAGESPEED_API_KEY", self.config.get("pagespeed_api_key", "")),
        )
        self.schema_engine = SchemaMarkupEngine()
        self.self_healer = SelfHealingEngine(
            confidence_threshold=self.config.get("confidence_threshold", 0.8),
            schema_engine=self.schema_engine,
        )
        self.tech_validator = MultiEngineValidator()

    def get_triggers(self) -> list[dict[str, Any]]:
        return [
            {"type": "scheduled", "condition": "cwv_check", "priority": "P2", "cron": "0 */6 * * *"},
            {"type": "scheduled", "condition": "schema_validation", "priority": "P2", "cron": "0 3 * * 1"},
            {"type": "event", "condition": "pagespeed_below_50", "priority": "P1"},
            {"type": "event", "condition": "new_page_published", "priority": "P1"},
            {"type": "proactive", "condition": "cls_spike_above_025", "priority": "P0"},
            {"type": "proactive", "condition": "inp_regression_above_200ms", "priority": "P0"},
            {"type": "proactive", "condition": "lcp_above_4s", "priority": "P0"},
            {"type": "proactive", "condition": "mobile_usability_errors", "priority": "P1"},
        ]

    async def execute(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a technical audit task.

        task_payload keys:
            task_type: str          -- "cwv_check" | "schema_validation" | "self_heal" | "tech_audit"
            urls: list[str]         -- URLs to check
            strategy: str           -- "mobile" | "desktop" (default: "mobile")
            auto_heal: bool         -- Whether to auto-fix issues (default: True)
        """
        task_type = task_payload.get("task_type", "cwv_check")
        urls = task_payload.get("urls", [])
        strategy = task_payload.get("strategy", "mobile")
        auto_heal = task_payload.get("auto_heal", True)

        self.transition("start_monitor")
        started_at = datetime.now(timezone.utc)

        results: dict[str, Any] = {
            "task_type": task_type,
            "urls_checked": len(urls),
            "started_at": started_at.isoformat(),
        }

        async with httpx.AsyncClient(timeout=120) as client:
            if task_type == "cwv_check":
                results["cwv"] = await self._cwv_monitoring(urls, strategy, client)

            elif task_type == "schema_validation":
                results["schema"] = await self._schema_validation(urls, client)

            elif task_type == "self_heal":
                results["healing"] = await self._self_healing(urls, auto_heal, client)

            elif task_type == "tech_audit":
                # Full technical audit: CWV + schema + self-heal + validation
                results["cwv"] = await self._cwv_monitoring(urls, strategy, client)
                results["validation"] = await self._tech_validation(urls, client)
                if auto_heal:
                    results["healing"] = await self._self_healing(urls, auto_heal, client)

            else:
                logger.warning("[%s] Unknown task_type: %s", self.agent_name, task_type)
                results["error"] = f"Unknown task_type: {task_type}"

        self.transition("monitor_complete")
        self.transition("analysis_complete")

        finished_at = datetime.now(timezone.utc)
        results["finished_at"] = finished_at.isoformat()
        results["duration_seconds"] = (finished_at - started_at).total_seconds()

        self.transition("report_sent")

        return results

    # -- CWV Monitoring ---------------------------------------------------

    async def _cwv_monitoring(
        self, urls: list[str], strategy: str, client: httpx.AsyncClient
    ) -> list[dict[str, Any]]:
        """Check Core Web Vitals for a list of URLs."""
        cwv_results: list[dict[str, Any]] = []

        for url in urls:
            try:
                psi_data = await self.pagespeed_client.analyze(url, client, strategy)

                cwv_metrics = {
                    "lcp_ms": psi_data["lcp_ms"],
                    "fid_ms": psi_data["fid_ms"],
                    "cls": psi_data["cls"],
                    "ttfb_ms": psi_data["ttfb_ms"],
                }
                if psi_data.get("inp_ms") is not None:
                    cwv_metrics["inp_ms"] = psi_data["inp_ms"]

                status = evaluate_cwv_status(cwv_metrics)

                result = CWVResult(
                    url=url,
                    lab=cwv_metrics,
                    status=status,
                    performance_score=psi_data["performance_score"],
                    opportunities=psi_data.get("opportunities", []),
                    checked_at=datetime.now(timezone.utc).isoformat(),
                )

                if status in ("poor", "needs_improvement"):
                    await self.emit_event(
                        "technical.cwv_issue",
                        result.to_dict(),
                        priority=AgentPriority.P0 if status == "poor" else AgentPriority.P1,
                    )

                cwv_results.append(result.to_dict())

            except Exception as exc:
                logger.error("[%s] CWV check failed for %s: %s", self.agent_name, url, exc)
                cwv_results.append({"url": url, "error": str(exc), "status": "error"})

        return cwv_results

    # -- Schema Validation ------------------------------------------------

    async def _schema_validation(
        self, urls: list[str], client: httpx.AsyncClient
    ) -> list[dict[str, Any]]:
        """Validate existing schema markup on pages."""
        schema_results: list[dict[str, Any]] = []

        for url in urls:
            try:
                resp = await client.get(url, timeout=30)
                soup = BeautifulSoup(resp.text, "html.parser")
                schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

                page_schemas = []
                for script in schema_scripts:
                    try:
                        schema_data = json.loads(script.string or "{}")
                        validation = self.schema_engine.validate(schema_data)
                        page_schemas.append({
                            "schema": schema_data,
                            "valid": validation["valid"],
                            "errors": validation["errors"],
                        })
                    except json.JSONDecodeError:
                        page_schemas.append({"error": "invalid_json", "raw": (script.string or "")[:200]})

                schema_results.append({
                    "url": url,
                    "schemas_found": len(page_schemas),
                    "schemas": page_schemas,
                    "has_any_schema": len(page_schemas) > 0,
                })

            except Exception as exc:
                logger.error("[%s] Schema validation failed for %s: %s", self.agent_name, url, exc)
                schema_results.append({"url": url, "error": str(exc)})

        return schema_results

    # -- Self-Healing -----------------------------------------------------

    async def _self_healing(
        self, urls: list[str], auto_heal: bool, client: httpx.AsyncClient
    ) -> list[dict[str, Any]]:
        """Detect and fix technical issues on pages."""
        heal_results: list[dict[str, Any]] = []

        for url in urls:
            try:
                resp = await client.get(url, timeout=30)
                html = resp.text

                # Detect issues
                issues = self.self_healer.detect_issues(html, url)

                if not issues:
                    heal_results.append({"url": url, "issues_found": 0})
                    continue

                # Generate fixes
                page_data = {
                    "url": url,
                    "content": html[:5000],
                    "final_url": str(resp.url),
                    "redirect_chain": [str(r.url) for r in resp.history],
                }

                # Extract page data for fix generation
                soup = BeautifulSoup(html, "html.parser")
                h1 = soup.find("h1")
                page_data["h1"] = h1.get_text(strip=True) if h1 else ""
                title_tag = soup.find("title")
                page_data["title"] = title_tag.get_text(strip=True) if title_tag else ""

                # Images without alt
                images = soup.find_all("img")
                page_data["images_without_alt"] = [
                    img.get("src", "") for img in images if not img.get("alt", "").strip()
                ]

                fixes = []
                for issue in issues:
                    fix = self.self_healer.generate_fix(issue["type"], page_data)
                    if fix:
                        fix_result = SelfHealResult(
                            issue_type=issue["type"],
                            url=url,
                            fix=fix,
                            confidence=fix.get("confidence", 0),
                            auto_applied=auto_heal and fix.get("auto_applied", False),
                            status="applied" if (auto_heal and fix.get("auto_applied")) else "fix_proposed",
                        )
                        fixes.append(fix_result.to_dict())

                        # Emit event for each fix
                        await self.emit_event(
                            "technical.self_heal",
                            fix_result.to_dict(),
                            target_agent="executor",
                            priority=AgentPriority.P1,
                        )

                heal_results.append({
                    "url": url,
                    "issues_found": len(issues),
                    "fixes_proposed": len(fixes),
                    "fixes": fixes,
                })

            except Exception as exc:
                logger.error("[%s] Self-healing failed for %s: %s", self.agent_name, url, exc)
                heal_results.append({"url": url, "error": str(exc)})

        return heal_results

    # -- Technical Validation ---------------------------------------------

    async def _tech_validation(
        self, urls: list[str], client: httpx.AsyncClient
    ) -> list[dict[str, Any]]:
        """Run multi-engine technical validation on pages."""
        validation_results: list[dict[str, Any]] = []

        for url in urls:
            try:
                resp = await client.get(url, timeout=30)
                result = self.tech_validator.validate_page(resp.text, url)
                validation_results.append(result.to_dict())
            except Exception as exc:
                logger.error("[%s] Tech validation failed for %s: %s", self.agent_name, url, exc)
                validation_results.append({"url": url, "error": str(exc)})

        return validation_results
