"""
agents/content.py
Content Agent (Forge) - Audits, generates, and optimizes content.

Components:
- On-page audit with 200+ signals
- Dual scoring: Google Score + AI Readiness Score
- Keyword gap analysis via DataForSEO
- Meta tag optimization via Codex
- Content generation pipeline
- Internal link recommendation
- AEO/GEO optimization

State Machine:
IDLE -> AUDITING -> SCORING -> GENERATING -> OPTIMIZING -> REVIEWING -> PUBLISHING -> IDLE
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx
LLM_MODEL = "gpt-5.6-sol"

logger = logging.getLogger(__name__)


# --- State Machine ---


class ForgeState(str, Enum):
    IDLE = "idle"
    AUDITING = "auditing"
    SCORING = "scoring"
    GENERATING = "generating"
    OPTIMIZING = "optimizing"
    REVIEWING = "reviewing"
    PUBLISHING = "publishing"


# --- Data Classes ---


@dataclass
class GoogleScore:
    """Traditional SEO quality score (0-100)."""

    title_optimization: float = 0.0
    meta_description: float = 0.0
    heading_structure: float = 0.0
    content_depth: float = 0.0
    keyword_usage: float = 0.0
    internal_linking: float = 0.0
    image_optimization: float = 0.0
    eeat_signals: float = 0.0
    url_structure: float = 0.0
    mobile_readability: float = 0.0
    schema_markup: float = 0.0
    page_speed_correlation: float = 0.0
    total: float = 0.0


@dataclass
class AIReadinessScore:
    """AEO/GEO readiness score (0-100)."""

    question_answer_format: float = 0.0
    structured_data: float = 0.0
    entity_clarity: float = 0.0
    citation_worthiness: float = 0.0
    conversational_tone: float = 0.0
    featured_snippet_ready: float = 0.0
    passage_independence: float = 0.0
    freshness_signals: float = 0.0
    source_authority: float = 0.0
    ai_crawlability: float = 0.0
    total: float = 0.0


@dataclass
class ContentAuditReport:
    """Complete content audit report."""

    url: str
    google_score: GoogleScore
    ai_readiness_score: AIReadinessScore
    gap_analysis: dict = field(default_factory=dict)
    internal_link_recs: list[dict] = field(default_factory=list)
    aeo_recommendations: list[str] = field(default_factory=list)
    geo_recommendations: list[str] = field(default_factory=list)
    priority: str = "P3"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "google_score": self.google_score.total,
            "ai_readiness_score": self.ai_readiness_score.total,
            "gap_analysis": self.gap_analysis,
            "internal_link_recs": self.internal_link_recs,
            "aeo_recommendations": self.aeo_recommendations,
            "geo_recommendations": self.geo_recommendations,
            "priority": self.priority,
            "timestamp": self.timestamp,
        }


@dataclass
class ContentPackage:
    """Generated content package."""

    title: str
    meta_description: str
    sections: list[str]
    schema_markup: dict = field(default_factory=dict)
    internal_links: list[dict] = field(default_factory=list)
    target_keyword: str = ""
    word_count: int = 0
    google_score_estimate: float = 0.0
    ai_readiness_estimate: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "meta_description": self.meta_description,
            "sections": self.sections,
            "schema_markup": self.schema_markup,
            "internal_links": self.internal_links,
            "target_keyword": self.target_keyword,
            "word_count": self.word_count,
            "google_score_estimate": self.google_score_estimate,
            "ai_readiness_estimate": self.ai_readiness_estimate,
            "timestamp": self.timestamp,
        }


@dataclass
class MetaTagResult:
    """Optimized meta tags."""

    title: str
    description: str
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    canonical: str = ""


# --- Dual Scorer ---


class DualScorer:
    """
    Two independent scoring axes for content quality.

    Google Score (0-100): Traditional SEO quality signals
    AI Readiness Score (0-100): AEO/GEO optimization signals
    """

    # Google Score weights
    GOOGLE_WEIGHTS = {
        "title_optimization": 0.10,
        "meta_description": 0.08,
        "heading_structure": 0.10,
        "content_depth": 0.15,
        "keyword_usage": 0.12,
        "internal_linking": 0.08,
        "image_optimization": 0.05,
        "eeat_signals": 0.12,
        "url_structure": 0.05,
        "mobile_readability": 0.05,
        "schema_markup": 0.05,
        "page_speed_correlation": 0.05,
    }

    # AI Readiness weights
    AI_WEIGHTS = {
        "question_answer_format": 0.15,
        "structured_data": 0.12,
        "entity_clarity": 0.12,
        "citation_worthiness": 0.10,
        "conversational_tone": 0.08,
        "featured_snippet_ready": 0.12,
        "passage_independence": 0.10,
        "freshness_signals": 0.08,
        "source_authority": 0.08,
        "ai_crawlability": 0.05,
    }

    def score_google(self, checks: dict[str, float]) -> GoogleScore:
        """Calculate Google Score from check results."""
        score = GoogleScore()
        total = 0.0
        for signal, weight in self.GOOGLE_WEIGHTS.items():
            value = checks.get(signal, 0.0)
            setattr(score, signal, value)
            total += value * weight
        score.total = round(min(total, 100), 1)
        return score

    def score_ai_readiness(self, checks: dict[str, float]) -> AIReadinessScore:
        """Calculate AI Readiness Score from check results."""
        score = AIReadinessScore()
        total = 0.0
        for signal, weight in self.AI_WEIGHTS.items():
            value = checks.get(signal, 0.0)
            setattr(score, signal, value)
            total += value * weight
        score.total = round(min(total, 100), 1)
        return score


# --- On-Page Auditor ---


class OnPageAuditor:
    """
    Audits pages for 200+ SEO signals.
    Produces check scores for both Google Score and AI Readiness.
    """

    def audit(self, url: str, html: str, text_content: str, target_keyword: str) -> dict[str, float]:
        """
        Run full on-page audit.

        Returns dict of check_name -> score (0-100).
        """
        checks = {}

        # Google Score checks
        checks["title_optimization"] = self._audit_title(html, target_keyword)
        checks["meta_description"] = self._audit_meta_description(html, target_keyword)
        checks["heading_structure"] = self._audit_headings(html, target_keyword)
        checks["content_depth"] = self._audit_content_depth(text_content, target_keyword)
        checks["keyword_usage"] = self._audit_keyword_usage(text_content, target_keyword)
        checks["internal_linking"] = self._audit_internal_links(html, url)
        checks["image_optimization"] = self._audit_images(html)
        checks["eeat_signals"] = self._audit_eeat(html, url)
        checks["url_structure"] = self._audit_url(url, target_keyword)
        checks["mobile_readability"] = self._audit_mobile_readability(html)
        checks["schema_markup"] = self._audit_schema(html)
        checks["page_speed_correlation"] = 50.0  # Placeholder - needs PSI data

        # AI Readiness checks
        checks["question_answer_format"] = self._audit_qa_format(text_content, html)
        checks["structured_data"] = self._audit_structured_data(html)
        checks["entity_clarity"] = self._audit_entities(text_content)
        checks["citation_worthiness"] = self._audit_citations(html)
        checks["conversational_tone"] = self._audit_readability(text_content)
        checks["featured_snippet_ready"] = self._audit_snippet_ready(text_content)
        checks["passage_independence"] = self._audit_passage_independence(text_content)
        checks["freshness_signals"] = self._audit_freshness(html)
        checks["source_authority"] = self._audit_source_authority(html)
        checks["ai_crawlability"] = self._audit_ai_crawlability(html)

        return checks

    def _audit_title(self, html: str, keyword: str) -> float:
        """Audit title tag."""
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if not title_match:
            return 0.0
        title = title_match.group(1).strip()
        score = 50.0
        if 30 <= len(title) <= 60:
            score += 20.0
        if keyword.lower() in title.lower():
            score += 30.0
        return min(score, 100.0)

    def _audit_meta_description(self, html: str, keyword: str) -> float:
        """Audit meta description."""
        desc_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
            html, re.IGNORECASE,
        )
        if not desc_match:
            return 0.0
        desc = desc_match.group(1).strip()
        score = 40.0
        if 120 <= len(desc) <= 155:
            score += 30.0
        if keyword.lower() in desc.lower():
            score += 20.0
        cta_words = ["learn", "discover", "find out", "get", "try", "start", "read"]
        if any(w in desc.lower() for w in cta_words):
            score += 10.0
        return min(score, 100.0)

    def _audit_headings(self, html: str, keyword: str) -> float:
        """Audit heading structure."""
        h1_count = len(re.findall(r"<h1[^>]*>", html, re.IGNORECASE))
        h2_count = len(re.findall(r"<h2[^>]*>", html, re.IGNORECASE))
        score = 30.0
        if h1_count == 1:
            score += 30.0
        elif h1_count > 1:
            score += 10.0
        if h2_count >= 2:
            score += 20.0
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        if h1_match and keyword.lower() in h1_match.group(1).lower():
            score += 20.0
        return min(score, 100.0)

    def _audit_content_depth(self, text: str, keyword: str) -> float:
        """Audit content depth."""
        words = text.split()
        word_count = len(words)
        score = 20.0
        if word_count >= 300:
            score += 20.0
        if word_count >= 1000:
            score += 20.0
        if word_count >= 2000:
            score += 20.0
        # Check for subtopics
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) >= 5:
            score += 20.0
        return min(score, 100.0)

    def _audit_keyword_usage(self, text: str, keyword: str) -> float:
        """Audit keyword usage."""
        if not keyword:
            return 50.0
        text_lower = text.lower()
        kw_lower = keyword.lower()
        words = text.split()
        word_count = len(words)
        kw_count = text_lower.count(kw_lower)
        if word_count == 0:
            return 0.0
        density = (kw_count * len(kw_lower.split())) / word_count * 100
        score = 30.0
        if 0.5 <= density <= 2.5:
            score += 40.0
        elif density > 0:
            score += 20.0
        # Check placement
        first_200 = text_lower[:200]
        if kw_lower in first_200:
            score += 30.0
        return min(score, 100.0)

    def _audit_internal_links(self, html: str, url: str) -> float:
        """Audit internal linking."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        links = re.findall(r'href=["\'](.*?)["\']', html, re.IGNORECASE)
        internal = [l for l in links if domain in l or l.startswith("/")]
        score = 30.0
        if len(internal) >= 3:
            score += 30.0
        if len(internal) >= 5:
            score += 20.0
        if len(internal) >= 10:
            score += 20.0
        return min(score, 100.0)

    def _audit_images(self, html: str) -> float:
        """Audit image optimization."""
        images = re.findall(r"<img[^>]*>", html, re.IGNORECASE)
        if not images:
            return 50.0  # No images is neutral
        with_alt = sum(1 for img in images if "alt=" in img.lower())
        ratio = with_alt / len(images) if images else 0
        return min(50.0 + ratio * 50.0, 100.0)

    def _audit_eeat(self, html: str, url: str) -> float:
        """Audit E-E-A-T signals."""
        score = 30.0
        text_lower = html.lower()
        if "author" in text_lower:
            score += 20.0
        if any(w in text_lower for w in ["published", "updated", "modified"]):
            score += 15.0
        if any(w in text_lower for w in ["source", "reference", "citation", "study"]):
            score += 20.0
        if any(w in text_lower for w in ["about", "expert", "credentials", "experience"]):
            score += 15.0
        return min(score, 100.0)

    def _audit_url(self, url: str, keyword: str) -> float:
        """Audit URL structure."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path
        score = 40.0
        if len(path) < 100:
            score += 20.0
        if keyword.lower().replace(" ", "-") in path.lower():
            score += 30.0
        if "_" not in path:
            score += 10.0
        return min(score, 100.0)

    def _audit_mobile_readability(self, html: str) -> float:
        """Audit mobile readability."""
        score = 50.0
        if "viewport" in html.lower():
            score += 30.0
        if "font-size" in html.lower():
            score += 10.0
        if "line-height" in html.lower():
            score += 10.0
        return min(score, 100.0)

    def _audit_schema(self, html: str) -> float:
        """Audit schema markup."""
        score = 20.0
        if "application/ld+json" in html.lower():
            score += 40.0
        if "@type" in html:
            score += 20.0
        if "Article" in html or "BlogPosting" in html:
            score += 10.0
        if "FAQPage" in html:
            score += 10.0
        return min(score, 100.0)

    def _audit_qa_format(self, text: str, html: str) -> float:
        """Audit question-answer format."""
        score = 20.0
        questions = len(re.findall(r"\?", text))
        if questions >= 3:
            score += 30.0
        if questions >= 5:
            score += 20.0
        if "FAQPage" in html:
            score += 30.0
        return min(score, 100.0)

    def _audit_structured_data(self, html: str) -> float:
        """Audit structured data completeness."""
        score = 30.0
        if "application/ld+json" in html.lower():
            score += 40.0
        if "@context" in html and "schema.org" in html:
            score += 30.0
        return min(score, 100.0)

    def _audit_entities(self, text: str) -> float:
        """Audit named entity clarity."""
        # Simple heuristic: proper nouns, capitalized words
        words = text.split()
        capitalized = sum(1 for w in words if w[0:1].isupper() and len(w) > 2)
        if len(words) == 0:
            return 0.0
        ratio = capitalized / len(words)
        return min(ratio * 200, 100.0)

    def _audit_citations(self, html: str) -> float:
        """Audit citation worthiness."""
        score = 20.0
        links = re.findall(r'href=["\'](https?://.*?)["\']', html, re.IGNORECASE)
        external = [l for l in links if "schema.org" not in l]
        if len(external) >= 3:
            score += 30.0
        text_lower = html.lower()
        if any(w in text_lower for w in ["according to", "research", "study", "data"]):
            score += 30.0
        if any(w in text_lower for w in ["%", "percent", "statistic"]):
            score += 20.0
        return min(score, 100.0)

    def _audit_readability(self, text: str) -> float:
        """Audit conversational tone / readability."""
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return 0.0
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        score = 50.0
        if avg_len <= 20:
            score += 25.0
        if avg_len <= 15:
            score += 25.0
        return min(score, 100.0)

    def _audit_snippet_ready(self, text: str) -> float:
        """Audit featured snippet readiness."""
        score = 20.0
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if paragraphs:
            first_para = paragraphs[0]
            if 40 <= len(first_para.split()) <= 60:
                score += 40.0
        # Check for list format
        list_items = len(re.findall(r"^[\-\*]\s", text, re.MULTILINE))
        if list_items >= 3:
            score += 20.0
        # Check for numbered lists
        numbered = len(re.findall(r"^\d+\.\s", text, re.MULTILINE))
        if numbered >= 3:
            score += 20.0
        return min(score, 100.0)

    def _audit_passage_independence(self, text: str) -> float:
        """Audit passage independence."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return 0.0
        score = 30.0
        if len(paragraphs) >= 5:
            score += 30.0
        # Check for topic sentences (first sentence is declarative)
        for p in paragraphs[:3]:
            first_sent = re.split(r"[.!?]", p)[0]
            if len(first_sent.split()) >= 5:
                score += 13.3
        return min(score, 100.0)

    def _audit_freshness(self, html: str) -> float:
        """Audit freshness signals."""
        score = 30.0
        text_lower = html.lower()
        if any(w in text_lower for w in ["2025", "2026", "updated", "latest"]):
            score += 40.0
        if "datepublished" in text_lower or "datemodified" in text_lower:
            score += 30.0
        return min(score, 100.0)

    def _audit_source_authority(self, html: str) -> float:
        """Audit source authority."""
        score = 30.0
        links = re.findall(r'href=["\'](https?://.*?)["\']', html, re.IGNORECASE)
        authority_domains = [".gov", ".edu", "wikipedia.org", "research", "study"]
        authority_links = sum(
            1 for l in links if any(a in l.lower() for a in authority_domains)
        )
        if authority_links >= 1:
            score += 30.0
        if authority_links >= 3:
            score += 20.0
        return min(score, 100.0)

    def _audit_ai_crawlability(self, html: str) -> float:
        """Audit AI crawlability."""
        score = 50.0
        # Check for JS-required content
        if "noscript" in html.lower():
            score += 10.0
        # Check for text in HTML vs JS-rendered
        text_ratio = len(re.sub(r"<[^>]+>", "", html)) / max(len(html), 1)
        if text_ratio > 0.3:
            score += 20.0
        if text_ratio > 0.5:
            score += 20.0
        return min(score, 100.0)


# --- Keyword Engine ---


class KeywordEngine:
    """
    Keyword gap analysis and opportunity identification via DataForSEO.
    """

    def __init__(self, dataforseo_client):
        self.dataforseo = dataforseo_client

    async def find_keyword_gaps(
        self,
        our_domain: str,
        competitor_domains: list[str],
        location_code: int = 2840,
    ) -> list[dict]:
        """
        Find keywords competitors rank for but we don't.

        Returns list of keyword opportunities with volume and difficulty.
        """
        # Get our keywords
        our_data = await self.dataforseo.get_site_keywords(
            target=our_domain,
            location_code=location_code,
            limit=1000,
        )
        our_keywords = set()
        tasks = our_data.get("tasks", [])
        if tasks and tasks[0].get("result"):
            for item in tasks[0]["result"][0].get("keywords", []):
                our_keywords.add(item.get("keyword", "").lower())

        # Get competitor keywords
        opportunities = []
        for comp_domain in competitor_domains:
            comp_data = await self.dataforseo.get_site_keywords(
                target=comp_domain,
                location_code=location_code,
                limit=500,
            )
            comp_tasks = comp_data.get("tasks", [])
            if comp_tasks and comp_tasks[0].get("result"):
                for item in comp_tasks[0]["result"][0].get("keywords", []):
                    kw = item.get("keyword", "").lower()
                    if kw and kw not in our_keywords:
                        opportunities.append({
                            "keyword": item.get("keyword", ""),
                            "search_volume": item.get("search_volume", 0),
                            "cpc": item.get("cpc", 0),
                            "competition": item.get("competition", 0),
                            "competitor": comp_domain,
                            "competitor_position": item.get("position", 0),
                        })

        # Deduplicate and sort by volume
        seen = set()
        unique = []
        for opp in opportunities:
            if opp["keyword"] not in seen:
                seen.add(opp["keyword"])
                unique.append(opp)
        unique.sort(key=lambda x: x["search_volume"], reverse=True)

        return unique[:100]  # Top 100 opportunities

    async def get_keyword_metrics(
        self,
        keywords: list[str],
        location_code: int = 2840,
    ) -> list[dict]:
        """Get metrics for a list of keywords."""
        data = await self.dataforseo.get_keyword_metrics(
            keywords=keywords,
            location_code=location_code,
        )
        results = []
        tasks = data.get("tasks", [])
        if tasks and tasks[0].get("result"):
            for item in tasks[0]["result"][0].get("keywords_info", []):
                results.append({
                    "keyword": item.get("keyword", ""),
                    "search_volume": item.get("search_volume", 0),
                    "cpc": item.get("cpc", 0),
                    "competition": item.get("competition", 0),
                    "competition_level": item.get("competition_index", ""),
                    "monthly_searches": item.get("monthly_searches", []),
                })
        return results

    async def cluster_keywords(self, keywords: list[str]) -> dict[str, list[str]]:
        """
        Group keywords into topic clusters based on similarity.
        Simple approach: group by shared words.
        """
        clusters: dict[str, list[str]] = {}

        for kw in keywords:
            words = set(kw.lower().split())
            placed = False

            for cluster_key in list(clusters.keys()):
                cluster_words = set(cluster_key.lower().split())
                overlap = len(words & cluster_words)
                if overlap >= 1:
                    clusters[cluster_key].append(kw)
                    placed = True
                    break

            if not placed:
                clusters[kw] = [kw]

        return clusters


# --- Meta Tag Optimizer ---


class MetaTagOptimizer:
    """
    Meta tag optimization via Codex.
    Generates optimized title, description, and OG tags.
    """

    def __init__(self, openai_api_key: str):
        self.api_key = openai_api_key

    async def generate_meta_tags(
        self,
        content: str,
        target_keyword: str,
        current_title: str = "",
        current_description: str = "",
        count: int = 5,
    ) -> list[MetaTagResult]:
        """
        Generate optimized meta tags using Codex.

        Returns list of MetaTagResult options to choose from.
        """
        prompt = f"""Generate {count} optimized meta tag sets for a page targeting the keyword "{target_keyword}".

Current title: {current_title or "None"}
Current description: {current_description or "None"}

Content preview: {content[:1000]}

For each set, provide:
1. Title (50-60 chars, keyword near start)
2. Meta description (120-155 chars, with CTA)
3. OG title
4. OG description

Format each set as:
TITLE: ...
DESCRIPTION: ...
OG_TITLE: ...
OG_DESCRIPTION: ...
---"""

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": "You are an expert SEO copywriter. Generate optimized meta tags."},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 1000,
                        "temperature": 0.7,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                result = resp.json()
                text = result["choices"][0]["message"]["content"]

                return self._parse_meta_results(text)

        except Exception as e:
            logger.error("Meta tag generation failed: %s", e)
            # Return fallback
            return [MetaTagResult(
                title=current_title or f"{target_keyword} - Complete Guide",
                description=current_description or f"Learn everything about {target_keyword}. Expert insights and practical tips.",
            )]

    def _parse_meta_results(self, text: str) -> list[MetaTagResult]:
        """Parse LLM output into MetaTagResult objects."""
        results = []
        sets = text.split("---")
        for s in sets:
            lines = s.strip().split("\n")
            title = ""
            desc = ""
            og_title = ""
            og_desc = ""
            for line in lines:
                if line.startswith("TITLE:"):
                    title = line[6:].strip()
                elif line.startswith("DESCRIPTION:"):
                    desc = line[12:].strip()
                elif line.startswith("OG_TITLE:"):
                    og_title = line[9:].strip()
                elif line.startswith("OG_DESCRIPTION:"):
                    og_desc = line[15:].strip()
            if title or desc:
                results.append(MetaTagResult(
                    title=title,
                    description=desc,
                    og_title=og_title or title,
                    og_description=og_desc or desc,
                ))
        return results


# --- Content Generator ---


class ContentGenerator:
    """
    LLM-powered content creation pipeline.
    Generates content section by section with research context.
    """

    def __init__(self, openai_api_key: str):
        self.api_key = openai_api_key

    async def generate_outline(
        self,
        target_keyword: str,
        content_type: str,
        serp_data: dict,
        research: dict,
    ) -> dict:
        """Generate content outline based on SERP analysis and research."""
        prompt = f"""Create a detailed content outline for a {content_type} targeting the keyword "{target_keyword}".

SERP Analysis: Top results cover these topics: {self._extract_serp_topics(serp_data)}
Research context: {research.get('answer', 'N/A')[:500]}

Generate an outline with:
- H1 title
- 5-8 H2 sections
- Key points for each section
- Suggested word count per section

Format as JSON."""

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": "You are an expert content strategist. Generate structured content outlines."},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 2000,
                        "temperature": 0.7,
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                result = resp.json()
                text = result["choices"][0]["message"]["content"]
                import json
                # Try to parse JSON from response
                json_match = re.search(r"\{.*\}", text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return {"sections": [], "raw": text}

        except Exception as e:
            logger.error("Outline generation failed: %s", e)
            return {"sections": [], "error": str(e)}

    async def generate_section(
        self,
        section_title: str,
        keyword: str,
        research_snippets: list[str],
        tone: str,
        target_words: int,
    ) -> str:
        """Generate a single content section."""
        research_text = "\n".join(research_snippets[:3])

        prompt = f"""Write a section titled "{section_title}" for an article targeting "{keyword}".

Tone: {tone}
Target word count: {target_words}
Research context: {research_text[:1000]}

Write engaging, informative content. Use short paragraphs, bullet points where appropriate, and include relevant data/statistics."""

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": "You are an expert content writer. Write engaging, SEO-optimized content."},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 4096,
                        "temperature": 0.7,
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                result = resp.json()
                return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error("Section generation failed: %s", e)
            return f"[Content generation failed for: {section_title}]"

    def _extract_serp_topics(self, serp_data: dict) -> str:
        """Extract topic coverage from SERP data."""
        topics = []
        tasks = serp_data.get("tasks", [])
        if tasks and tasks[0].get("result"):
            items = tasks[0]["result"][0].get("items", []) if tasks[0]["result"] else []
            for item in items[:5]:
                title = item.get("title", "")
                desc = item.get("description", "")
                if title:
                    topics.append(f"{title}: {desc[:100]}")
        return "; ".join(topics) if topics else "No SERP data"


# --- AEO/GEO Optimizer ---


class AEOOptimizer:
    """Answer Engine Optimization - optimize for AI-generated answers."""

    def generate_recommendations(self, ai_checks: dict, competitor_content: dict) -> list[str]:
        """Generate AEO optimization recommendations."""
        recs = []

        qa_score = ai_checks.get("question_answer_format", 0)
        if qa_score < 50:
            recs.append("Add FAQ section with direct question-answer pairs")
            recs.append("Include questions in H2/H3 headings with immediate answers below")

        snippet_score = ai_checks.get("featured_snippet_ready", 0)
        if snippet_score < 50:
            recs.append("Add a concise 40-60 word paragraph directly answering the main query")
            recs.append("Format key information as numbered or bulleted lists")

        entity_score = ai_checks.get("entity_clarity", 0)
        if entity_score < 50:
            recs.append("Use clear, unambiguous references to named entities")
            recs.append("Add structured data for key entities (Person, Organization, Product)")

        citation_score = ai_checks.get("citation_worthiness", 0)
        if citation_score < 50:
            recs.append("Add statistics, data points, and expert quotes")
            recs.append("Link to authoritative external sources (.gov, .edu, research)")

        return recs


class GEOOptimizer:
    """Generative Engine Optimization - optimize for generative AI search."""

    def generate_recommendations(self, ai_checks: dict, exa_analysis: dict) -> list[str]:
        """Generate GEO optimization recommendations."""
        recs = []

        passage_score = ai_checks.get("passage_independence", 0)
        if passage_score < 50:
            recs.append("Make each paragraph self-contained with clear topic sentences")
            recs.append("Ensure individual passages can be understood without surrounding context")

        freshness_score = ai_checks.get("freshness_signals", 0)
        if freshness_score < 50:
            recs.append("Add publication and last-updated dates prominently")
            recs.append("Include recent data, statistics, and examples from the current year")

        crawl_score = ai_checks.get("ai_crawlability", 0)
        if crawl_score < 50:
            recs.append("Ensure content is in HTML text, not JavaScript-rendered")
            recs.append("Remove any JS requirements for core content display")

        return recs


# --- Internal Link Engine ---


class InternalLinkEngine:
    """Internal link recommendation engine."""

    def recommend(
        self,
        source_url: str,
        source_content: str,
        target_keyword: str,
        link_graph: dict,
        max_recommendations: int = 10,
    ) -> list[dict]:
        """
        Recommend internal links from source page to other pages.

        Args:
            source_url: URL of the page being optimized
            source_content: Text content of the source page
            target_keyword: Target keyword
            link_graph: Dict of url -> {title, keywords, content_summary}
            max_recommendations: Max links to recommend

        Returns:
            List of recommended internal links with anchor text suggestions.
        """
        recommendations = []
        source_lower = source_content.lower()
        source_words = set(source_lower.split())

        for url, page_data in link_graph.items():
            if url == source_url:
                continue

            page_keywords = set(page_data.get("keywords", []))
            page_title = page_data.get("title", "")

            # Calculate relevance
            overlap = len(source_words & page_keywords)
            if overlap >= 2:
                # Find good anchor text
                anchor = self._suggest_anchor(source_content, page_keywords, page_title)
                if anchor:
                    recommendations.append({
                        "target_url": url,
                        "target_title": page_title,
                        "anchor_text": anchor,
                        "relevance_score": overlap,
                    })

        # Sort by relevance and return top N
        recommendations.sort(key=lambda x: x["relevance_score"], reverse=True)
        return recommendations[:max_recommendations]

    def _suggest_anchor(
        self, content: str, target_keywords: set, target_title: str
    ) -> Optional[str]:
        """Suggest anchor text for an internal link."""
        content_lower = content.lower()
        for kw in target_keywords:
            if kw.lower() in content_lower:
                return kw
        if target_title:
            return target_title
        return None


# --- Forge Agent (Content Agent) ---


class ForgeAgent:
    """
    Content Agent (Forge) - Audits, generates, and optimizes content.

    Integrates:
    - On-page audit with dual scoring
    - Keyword gap analysis via DataForSEO
    - Meta tag optimization via Codex
    - Content generation pipeline
    - Internal link recommendation
    - AEO/GEO optimization

    State Machine:
    IDLE -> AUDITING -> SCORING -> GENERATING -> OPTIMIZING -> REVIEWING -> PUBLISHING -> IDLE
    """

    def __init__(
        self,
        dataforseo_client,
        openai_api_key: str,
        tavily_client=None,
        exa_client=None,
        gsc_client=None,
    ):
        self.dataforseo = dataforseo_client
        self.tavily = tavily_client
        self.exa = exa_client
        self.gsc = gsc_client

        self.state = ForgeState.IDLE
        self.scorer = DualScorer()
        self.auditor = OnPageAuditor()
        self.keyword_engine = KeywordEngine(dataforseo_client)
        self.meta_optimizer = MetaTagOptimizer(openai_api_key)
        self.content_generator = ContentGenerator(openai_api_key)
        self.internal_linker = InternalLinkEngine()
        self.aeo_optimizer = AEOOptimizer()
        self.geo_optimizer = GEOOptimizer()

    async def audit_page(
        self,
        url: str,
        html: str,
        text_content: str,
        target_keyword: str,
        link_graph: Optional[dict] = None,
    ) -> ContentAuditReport:
        """
        Full on-page audit with dual scoring.

        Produces:
        - Google Score (0-100)
        - AI Readiness Score (0-100)
        - Gap analysis
        - Internal link recommendations
        - AEO/GEO recommendations
        """
        self.state = ForgeState.AUDITING

        # Run on-page audit
        checks = self.auditor.audit(url, html, text_content, target_keyword)

        self.state = ForgeState.SCORING

        # Score
        google_score = self.scorer.score_google(checks)
        ai_readiness = self.scorer.score_ai_readiness(checks)

        # Gap analysis via Tavily + Exa
        gap_analysis = {}
        try:
            if self.tavily:
                competitor_content = await self.tavily.search(
                    query=f"best results for '{target_keyword}'",
                    search_depth="advanced",
                    include_answer=True,
                    max_results=5,
                )
                gap_analysis["competitor_insights"] = competitor_content.get("answer", "")

            if self.exa:
                exa_analysis = await self.exa.search(
                    query=target_keyword,
                    num_results=10,
                )
                gap_analysis["exa_results"] = len(exa_analysis.get("results", []))
        except Exception as e:
            logger.warning("Gap analysis failed: %s", e)

        # Internal link recommendations
        internal_recs = []
        if link_graph:
            internal_recs = self.internal_linker.recommend(
                source_url=url,
                source_content=text_content,
                target_keyword=target_keyword,
                link_graph=link_graph,
            )

        # AEO/GEO recommendations
        aeo_recs = self.aeo_optimizer.generate_recommendations(checks, gap_analysis)
        geo_recs = self.geo_optimizer.generate_recommendations(checks, gap_analysis)

        # Calculate priority
        priority = self._calculate_priority(google_score.total, ai_readiness.total)

        self.state = ForgeState.IDLE

        report = ContentAuditReport(
            url=url,
            google_score=google_score,
            ai_readiness_score=ai_readiness,
            gap_analysis=gap_analysis,
            internal_link_recs=internal_recs,
            aeo_recommendations=aeo_recs,
            geo_recommendations=geo_recs,
            priority=priority,
        )

        logger.info(
            "Content audit complete for %s: Google=%.1f, AI=%.1f, Priority=%s",
            url, google_score.total, ai_readiness.total, priority,
        )

        return report

    async def generate_content(
        self,
        target_keyword: str,
        content_type: str = "article",
        tone: str = "professional",
        word_count: int = 2000,
    ) -> ContentPackage:
        """
        Content generation pipeline.

        1. Research via Tavily + Exa
        2. SERP analysis via DataForSEO
        3. Outline generation
        4. Section-by-section generation
        5. Meta tag optimization
        6. AEO/GEO enrichment
        7. Internal link placement
        8. Schema markup generation
        """
        self.state = ForgeState.GENERATING

        # Research
        research = {}
        try:
            if self.tavily:
                research = await self.tavily.search(
                    query=target_keyword,
                    search_depth="advanced",
                    include_answer=True,
                    max_results=10,
                )
        except Exception as e:
            logger.warning("Research failed: %s", e)

        # SERP analysis
        serp_data = {}
        try:
            serp_data = await self.dataforseo.google_serp(
                keyword=target_keyword, depth=10
            )
        except Exception as e:
            logger.warning("SERP analysis failed: %s", e)

        # Generate outline
        outline = await self.content_generator.generate_outline(
            target_keyword=target_keyword,
            content_type=content_type,
            serp_data=serp_data,
            research=research,
        )

        # Generate sections
        sections = []
        for section in outline.get("sections", []):
            section_title = section.get("title", "") if isinstance(section, dict) else str(section)
            section_content = await self.content_generator.generate_section(
                section_title=section_title,
                keyword=target_keyword,
                research_snippets=[research.get("answer", "")],
                tone=tone,
                target_words=word_count // max(len(outline.get("sections", [1])), 1),
            )
            sections.append(section_content)

        self.state = ForgeState.OPTIMIZING

        # Meta tags
        full_content = "\n\n".join(sections)
        meta_tags = await self.meta_optimizer.generate_meta_tags(
            content=full_content,
            target_keyword=target_keyword,
        )

        # Schema markup
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": meta_tags[0].title if meta_tags else target_keyword,
            "description": meta_tags[0].description if meta_tags else "",
            "datePublished": datetime.utcnow().isoformat(),
            "dateModified": datetime.utcnow().isoformat(),
        }

        self.state = ForgeState.REVIEWING

        # Estimate scores
        word_count_actual = len(full_content.split())

        package = ContentPackage(
            title=meta_tags[0].title if meta_tags else target_keyword,
            meta_description=meta_tags[0].description if meta_tags else "",
            sections=sections,
            schema_markup=schema,
            target_keyword=target_keyword,
            word_count=word_count_actual,
            google_score_estimate=70.0,
            ai_readiness_estimate=65.0,
        )

        self.state = ForgeState.IDLE

        logger.info(
            "Content generated for '%s': %d words, %d sections",
            target_keyword, word_count_actual, len(sections),
        )

        return package

    async def optimize_meta_tags(
        self,
        content: str,
        target_keyword: str,
        current_title: str = "",
        current_description: str = "",
    ) -> list[MetaTagResult]:
        """Generate optimized meta tag options."""
        return await self.meta_optimizer.generate_meta_tags(
            content=content,
            target_keyword=target_keyword,
            current_title=current_title,
            current_description=current_description,
        )

    async def find_keyword_gaps(
        self,
        our_domain: str,
        competitor_domains: list[str],
    ) -> list[dict]:
        """Find keyword gaps vs competitors."""
        return await self.keyword_engine.find_keyword_gaps(
            our_domain=our_domain,
            competitor_domains=competitor_domains,
        )

    def _calculate_priority(
        self, google_score: float, ai_score: float
    ) -> str:
        """Calculate priority based on scores."""
        avg = (google_score + ai_score) / 2
        if avg < 40:
            return "P0"
        elif avg < 60:
            return "P1"
        elif avg < 75:
            return "P2"
        return "P3"
