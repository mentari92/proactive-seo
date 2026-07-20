"""
agents/backlink.py
Backlink & Outreach Agent - The competitive differentiator.

Components:
- HARO Response Generator
- Broken Link Building (via Exa AI)
- Guest Post Outreach (via Tavily)
- Unlinked Mention Monitor
- Campaign Tracker (6 status states)
- Email sending via Gmail API
- Follow-up automation
- Link verification

Campaign States:
PROSPECTING -> OUTREACH_SENT -> FOLLOW_UP_1 -> FOLLOW_UP_2 -> NEGOTIATING -> ACQUIRED (or DEAD)
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

LLM_MODEL = "gpt-5.6-sol"
logger = logging.getLogger(__name__)


# --- Campaign States ---


class CampaignStatus(str, Enum):
    PROSPECTING = "prospecting"
    OUTREACH_SENT = "outreach_sent"
    FOLLOW_UP_1 = "follow_up_1"
    FOLLOW_UP_2 = "follow_up_2"
    NEGOTIATING = "negotiating"
    ACQUIRED = "acquired"
    DEAD = "dead"


class CampaignType(str, Enum):
    HARO = "haro"
    BROKEN_LINK = "broken_link"
    GUEST_POST = "guest_post"
    UNLINKED_MENTION = "unlinked_mention"


# --- Data Classes ---


@dataclass
class Prospect:
    """Outreach prospect."""

    name: str
    email: str
    domain: str
    role: str = ""
    company: str = ""
    source: str = ""
    domain_rank: float = 0.0


@dataclass
class Campaign:
    """Outreach campaign."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: CampaignType = CampaignType.HARO
    status: CampaignStatus = CampaignStatus.PROSPECTING
    prospect: Optional[Prospect] = None
    target_url: str = ""
    our_page_url: str = ""
    subject: str = ""
    body: str = ""
    email_message_id: str = ""
    email_thread_id: str = ""
    sent_at: Optional[datetime] = None
    last_email_sent_at: Optional[datetime] = None
    last_reply_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verification_failures: int = 0
    link_details: dict = field(default_factory=dict)
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    death_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "prospect": {
                "name": self.prospect.name,
                "email": self.prospect.email,
                "domain": self.prospect.domain,
                "domain_rank": self.prospect.domain_rank,
            } if self.prospect else None,
            "target_url": self.target_url,
            "our_page_url": self.our_page_url,
            "subject": self.subject,
            "email_message_id": self.email_message_id,
            "email_thread_id": self.email_thread_id,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "last_email_sent_at": self.last_email_sent_at.isoformat() if self.last_email_sent_at else None,
            "last_reply_at": self.last_reply_at.isoformat() if self.last_reply_at else None,
            "next_followup_at": self.next_followup_at.isoformat() if self.next_followup_at else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "verification_failures": self.verification_failures,
            "link_details": self.link_details,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "death_reason": self.death_reason,
        }


@dataclass
class HAROQuery:
    """HARO query from journalist."""

    query_id: str
    journalist_name: str
    journalist_email: str
    subject: str
    summary: str
    topic: str
    deadline: Optional[datetime] = None
    source: str = "HARO"


@dataclass
class BrokenLinkOpportunity:
    """Broken link building opportunity."""

    broken_url: str
    found_on: str
    domain: str
    domain_rank: float = 0.0
    original_topic: str = ""
    replacement_url: str = ""
    contact: Optional[Prospect] = None


@dataclass
class GuestPostTarget:
    """Guest post opportunity."""

    url: str
    domain: str
    domain_rank: float = 0.0
    guidelines: str = ""
    pitch_ideas: list[str] = field(default_factory=list)
    contact: Optional[Prospect] = None


@dataclass
class UnlinkedMention:
    """Unlinked brand mention."""

    url: str
    domain: str
    mention_text: str
    context: str = ""
    domain_rank: float = 0.0
    contact: Optional[Prospect] = None


# --- Campaign Tracker ---


class CampaignTracker:
    """
    Campaign tracking with 6-state machine.

    States:
    prospecting -> outreach_sent -> follow_up_1 -> follow_up_2 -> negotiating -> acquired
    Any state can transition to dead.
    """

    def __init__(self):
        # In-memory store (would be DB in production)
        self._campaigns: dict[str, Campaign] = {}

    def create_campaign(
        self,
        campaign_type: CampaignType,
        prospect: Prospect,
        target_url: str = "",
        our_page_url: str = "",
        subject: str = "",
        body: str = "",
    ) -> Campaign:
        """Create a new campaign."""
        campaign = Campaign(
            type=campaign_type,
            status=CampaignStatus.PROSPECTING,
            prospect=prospect,
            target_url=target_url,
            our_page_url=our_page_url,
            subject=subject,
            body=body,
        )
        self._campaigns[campaign.id] = campaign
        logger.info("Created campaign %s for %s", campaign.id, prospect.email)
        return campaign

    def update_status(
        self,
        campaign_id: str,
        new_status: CampaignStatus,
        **kwargs,
    ) -> Optional[Campaign]:
        """Update campaign status with validation."""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return None

        # Validate transition
        valid_transitions = {
            CampaignStatus.PROSPECTING: [
                CampaignStatus.OUTREACH_SENT, CampaignStatus.DEAD
            ],
            CampaignStatus.OUTREACH_SENT: [
                CampaignStatus.FOLLOW_UP_1, CampaignStatus.NEGOTIATING,
                CampaignStatus.DEAD,
            ],
            CampaignStatus.FOLLOW_UP_1: [
                CampaignStatus.FOLLOW_UP_2, CampaignStatus.NEGOTIATING,
                CampaignStatus.DEAD,
            ],
            CampaignStatus.FOLLOW_UP_2: [
                CampaignStatus.NEGOTIATING, CampaignStatus.DEAD,
            ],
            CampaignStatus.NEGOTIATING: [
                CampaignStatus.ACQUIRED, CampaignStatus.DEAD,
            ],
            CampaignStatus.ACQUIRED: [],  # Terminal
            CampaignStatus.DEAD: [],  # Terminal
        }

        allowed = valid_transitions.get(campaign.status, [])
        if new_status not in allowed and new_status != CampaignStatus.DEAD:
            logger.warning(
                "Invalid transition: %s -> %s for campaign %s",
                campaign.status.value, new_status.value, campaign_id,
            )
            return None

        campaign.status = new_status
        campaign.updated_at = datetime.utcnow()

        for key, value in kwargs.items():
            if hasattr(campaign, key):
                setattr(campaign, key, value)

        logger.info(
            "Campaign %s: %s -> %s",
            campaign_id, campaign.status.value, new_status.value,
        )
        return campaign

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get a campaign by ID."""
        return self._campaigns.get(campaign_id)

    def list_campaigns(
        self,
        status: Optional[CampaignStatus] = None,
        campaign_type: Optional[CampaignType] = None,
    ) -> list[Campaign]:
        """List campaigns with optional filters."""
        campaigns = list(self._campaigns.values())
        if status:
            campaigns = [c for c in campaigns if c.status == status]
        if campaign_type:
            campaigns = [c for c in campaigns if c.type == campaign_type]
        return campaigns

    def get_campaigns_needing_followup(self) -> list[Campaign]:
        """Get campaigns that need follow-up."""
        now = datetime.utcnow()
        followup_states = {
            CampaignStatus.OUTREACH_SENT,
            CampaignStatus.FOLLOW_UP_1,
            CampaignStatus.FOLLOW_UP_2,
        }
        return [
            c for c in self._campaigns.values()
            if c.status in followup_states
            and c.next_followup_at
            and c.next_followup_at <= now
        ]

    def get_stats(self) -> dict:
        """Get campaign statistics."""
        campaigns = list(self._campaigns.values())
        status_counts = {}
        for status in CampaignStatus:
            status_counts[status.value] = sum(
                1 for c in campaigns if c.status == status
            )

        total = len(campaigns)
        acquired = status_counts.get("acquired", 0)

        return {
            "total": total,
            "by_status": status_counts,
            "by_type": {
                t.value: sum(1 for c in campaigns if c.type == t)
                for t in CampaignType
            },
            "acquisition_rate": (acquired / total * 100) if total > 0 else 0,
            "active": sum(
                status_counts.get(s, 0)
                for s in ["prospecting", "outreach_sent", "follow_up_1",
                          "follow_up_2", "negotiating"]
            ),
        }

    def delete_campaign(self, campaign_id: str) -> bool:
        """Delete a campaign."""
        if campaign_id in self._campaigns:
            del self._campaigns[campaign_id]
            return True
        return False


# --- HARO Response Generator ---


class HAROResponseGenerator:
    """
    End-to-end HARO query monitoring and response generation.

    Pipeline:
    1. Monitor HARO queries
    2. Score relevance
    3. Research context
    4. Generate responses
    5. Send via Gmail
    6. Track outcomes
    """

    def __init__(self, openai_api_key: str, exa_client=None, tavily_client=None):
        self.api_key = openai_api_key
        self.exa = exa_client
        self.tavily = tavily_client

    def score_relevance(
        self,
        query: HAROQuery,
        expert_profiles: list[dict],
        min_relevance: float = 0.6,
    ) -> tuple[float, Optional[dict]]:
        """
        Score how relevant a HARO query is to our expertise.

        Returns:
            Tuple of (relevance_score, best_matching_expert)
        """
        best_score = 0.0
        best_expert = None

        query_words = set(
            f"{query.topic} {query.subject} {query.summary}".lower().split()
        )

        for expert in expert_profiles:
            expert_words = set(
                " ".join(expert.get("expertise", [])).lower().split()
            )
            overlap = len(query_words & expert_words)
            score = min(overlap / max(len(query_words), 1), 1.0)

            if score > best_score:
                best_score = score
                best_expert = expert

        if best_score < min_relevance:
            return best_score, None

        return best_score, best_expert

    async def generate_response(
        self,
        query: HAROQuery,
        expert_profile: dict,
        research: Optional[dict] = None,
    ) -> str:
        """
        Generate a HARO response using Codex.

        Args:
            query: HARO query
            expert_profile: Expert credentials
            research: Research context

        Returns:
            Generated response text.
        """
        import httpx

        research_text = ""
        if research:
            research_text = research.get("answer", "")[:500]

        prompt = f"""Generate a HARO response for the following query:

QUERY: {query.subject}
SUMMARY: {query.summary}
TOPIC: {query.topic}

EXPERT: {expert_profile.get('name', 'Expert')}
EXPERTISE: {', '.join(expert_profile.get('expertise', []))}
CREDENTIALS: {expert_profile.get('credentials', '')}

RESEARCH CONTEXT: {research_text}

Requirements:
- Maximum 300 words
- Include specific data/statistics where possible
- Quote the expert by name
- Include credentials and authority signals
- Professional, concise tone
- Direct answer to the query

Write the response:"""

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
                            {"role": "system", "content": "You are an expert PR writer crafting HARO responses."},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 500,
                        "temperature": 0.7,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                result = resp.json()
                return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error("HARO response generation failed: %s", e)
            return f"[Response generation failed: {e}]"


# --- Broken Link Builder ---


class BrokenLinkBuilder:
    """
    Broken Link Building pipeline.

    Pipeline:
    1. Find broken links on authority sites
    2. Create or find replacement content
    3. Find contact information
    4. Send outreach emails
    """

    def __init__(self, dataforseo_client, exa_client=None, tavily_client=None):
        self.dataforseo = dataforseo_client
        self.exa = exa_client
        self.tavily = tavily_client

    async def find_broken_links(
        self,
        domain: str,
        mode: str = "subdomains",
        limit: int = 100,
    ) -> list[dict]:
        """Find broken outbound links on a domain."""
        try:
            data = await self.dataforseo.get_broken_backlinks(
                target=domain,
                mode=mode,
                limit=limit,
            )
            tasks = data.get("tasks", [])
            if tasks and tasks[0].get("result"):
                items = tasks[0]["result"][0].get("items", [])
                return [
                    {
                        "broken_url": item.get("url_from", ""),
                        "found_on": item.get("url_to", ""),
                        "anchor": item.get("anchor", ""),
                        "domain_from": item.get("domain_from", ""),
                        "domain_rank": item.get("domain_rank", 0),
                        "first_seen": item.get("first_seen", ""),
                        "last_seen": item.get("last_seen", ""),
                    }
                    for item in items
                ]
        except Exception as e:
            logger.error("Broken link search failed for %s: %s", domain, e)
        return []

    async def discover_authority_domains(
        self,
        niche: str,
        count: int = 20,
    ) -> list[str]:
        """Discover authority domains in a niche via Exa AI."""
        if not self.exa:
            return []

        try:
            data = await self.exa.search(
                query=f"top authority sites for {niche}",
                num_results=count,
            )
            results = data.get("results", [])
            return [r.get("url", "") for r in results if r.get("url")]
        except Exception as e:
            logger.error("Authority domain discovery failed: %s", e)
            return []


# --- Guest Post Outreach ---


class GuestPostOutreach:
    """
    Guest Post Outreach pipeline.

    Pipeline:
    1. Discover guest post targets
    2. Generate pitch ideas
    3. Find contacts
    4. Send pitches
    """

    def __init__(self, exa_client=None, tavily_client=None, dataforseo_client=None):
        self.exa = exa_client
        self.tavily = tavily_client
        self.dataforseo = dataforseo_client

    async def discover_targets(
        self,
        niche: str,
        count: int = 50,
    ) -> list[GuestPostTarget]:
        """Discover guest post targets."""
        targets = []
        search_queries = [
            f'{niche} "write for us"',
            f'{niche} "guest post"',
            f'{niche} "contribute"',
            f'{niche} "submit an article"',
        ]

        for query in search_queries:
            try:
                if self.exa:
                    data = await self.exa.search(
                        query=query,
                        num_results=20,
                    )
                    for result in data.get("results", []):
                        url = result.get("url", "")
                        if url:
                            domain = url.split("//")[-1].split("/")[0]
                            dr = 0.0
                            if self.dataforseo:
                                try:
                                    dr = await self.dataforseo.get_domain_rank(domain)
                                except Exception:
                                    pass
                            targets.append(GuestPostTarget(
                                url=url,
                                domain=domain,
                                domain_rank=dr,
                            ))
            except Exception as e:
                logger.error("Guest post discovery failed for query '%s': %s", query, e)

        # Deduplicate and sort by DR
        seen = set()
        unique = []
        for t in targets:
            if t.domain not in seen:
                seen.add(t.domain)
                unique.append(t)
        unique.sort(key=lambda x: x.domain_rank, reverse=True)

        return unique[:count]


# --- Unlinked Mention Monitor ---


class UnlinkedMentionMonitor:
    """
    Unlinked Mention Monitor - finds brand mentions without links.
    """

    def __init__(self, exa_client=None, tavily_client=None, dataforseo_client=None):
        self.exa = exa_client
        self.tavily = tavily_client
        self.dataforseo = dataforseo_client

    async def find_unlinked_mentions(
        self,
        brand_variants: list[str],
        our_domain: str,
        min_domain_rank: float = 20.0,
        max_results: int = 50,
    ) -> list[UnlinkedMention]:
        """Find unlinked brand mentions."""
        if not self.exa:
            return []

        unlinked = []

        for variant in brand_variants:
            try:
                data = await self.exa.search(
                    query=f'"{variant}"',
                    num_results=50,
                )

                for result in data.get("results", []):
                    url = result.get("url", "")
                    text = result.get("text", "")

                    # Skip our own domain
                    if our_domain in url:
                        continue

                    # Check if it already links to us
                    if our_domain in text:
                        continue

                    domain = url.split("//")[-1].split("/")[0] if url else ""
                    dr = 0.0
                    if self.dataforseo and domain:
                        try:
                            dr = await self.dataforseo.get_domain_rank(domain)
                        except Exception:
                            pass

                    if dr >= min_domain_rank:
                        unlinked.append(UnlinkedMention(
                            url=url,
                            domain=domain,
                            mention_text=text[:200],
                            domain_rank=dr,
                        ))

            except Exception as e:
                logger.error("Unlinked mention search failed for '%s': %s", variant, e)

        # Deduplicate
        seen = set()
        unique = []
        for m in unlinked:
            if m.url not in seen:
                seen.add(m.url)
                unique.append(m)

        unique.sort(key=lambda x: x.domain_rank, reverse=True)
        return unique[:max_results]


# --- Link Verifier ---


class LinkVerifier:
    """Verify that acquired backlinks are actually live."""

    def __init__(self, dataforseo_client):
        self.dataforseo = dataforseo_client

    async def verify_link(
        self,
        target_url: str,
        our_domain: str,
        our_page_url: str,
    ) -> dict:
        """
        Verify that a backlink is live.

        Methods:
        1. Direct HTTP check
        2. DataForSEO backlink check

        Returns:
            Verification result dict.
        """
        import httpx

        # Method 1: Direct HTTP check
        try:
            resp = await httpx.AsyncClient().get(
                target_url,
                timeout=15,
                follow_redirects=True,
            )
            content = resp.text

            if our_domain in content:
                # Find the specific link
                import re
                link_pattern = rf'href=["\'](https?://[^"\']*{re.escape(our_domain)}[^"\']*)["\']'
                match = re.search(link_pattern, content)
                if match:
                    href = match.group(1)
                    # Check for nofollow
                    nofollow_pattern = rf'<a[^>]*href=["\']{re.escape(href)}["\'][^>]*rel=["\'][^"\']*nofollow'
                    is_nofollow = bool(re.search(nofollow_pattern, content))

                    return {
                        "status": "live",
                        "anchor": href,
                        "target_url": href,
                        "is_nofollow": is_nofollow,
                        "is_correct_page": our_page_url in href,
                        "method": "direct_http",
                    }
        except Exception as e:
            logger.debug("Direct HTTP check failed: %s", e)

        # Method 2: DataForSEO check
        try:
            check = await self.dataforseo.check_backlink(
                target=target_url,
                source=our_domain,
            )
            if check.get("found"):
                return {
                    "status": "live",
                    "anchor": check.get("anchor", ""),
                    "target_url": check.get("target_url", ""),
                    "is_nofollow": check.get("is_nofollow", False),
                    "first_seen": check.get("first_seen", ""),
                    "method": "dataforseo",
                }
        except Exception as e:
            logger.debug("DataForSEO check failed: %s", e)

        return {"status": "not_found"}


# --- Follow-Up Engine ---


class FollowUpEngine:
    """
    Automated follow-up sequence engine.

    Sequences:
    - outreach_sent: wait 3 days -> follow_up_1
    - follow_up_1: wait 5 days -> follow_up_2
    - follow_up_2: wait 7 days -> dead (or final follow-up for high-value)
    """

    def __init__(
        self,
        campaign_tracker: CampaignTracker,
        gmail_client,
        followup_1_days: int = 3,
        followup_2_days: int = 5,
        final_days: int = 7,
    ):
        self.tracker = campaign_tracker
        self.gmail = gmail_client
        self.followup_1_days = followup_1_days
        self.followup_2_days = followup_2_days
        self.final_days = final_days

    async def process_followups(self) -> dict:
        """
        Process all campaigns needing follow-up.

        Returns:
            Summary of actions taken.
        """
        campaigns = self.tracker.get_campaigns_needing_followup()
        results = {
            "processed": 0,
            "followups_sent": 0,
            "replies_detected": 0,
            "marked_dead": 0,
        }

        for campaign in campaigns:
            results["processed"] += 1

            # Check for replies first
            if campaign.email_thread_id and self.gmail:
                try:
                    replies = await self.gmail.check_thread_replies(
                        thread_id=campaign.email_thread_id,
                        since=campaign.last_email_sent_at or campaign.sent_at or campaign.created_at,
                    )

                    if replies:
                        # Reply received - move to negotiating
                        campaign.last_reply_at = datetime.utcnow()
                        self.tracker.update_status(
                            campaign.id,
                            CampaignStatus.NEGOTIATING,
                            last_reply_at=datetime.utcnow(),
                        )
                        results["replies_detected"] += 1
                        continue

                except Exception as e:
                    logger.error("Reply check failed for %s: %s", campaign.id, e)

            # No reply - send follow-up
            now = datetime.utcnow()

            if campaign.status == CampaignStatus.OUTREACH_SENT:
                if campaign.sent_at and (now - campaign.sent_at).days >= self.followup_1_days:
                    await self._send_followup(campaign, CampaignStatus.FOLLOW_UP_1)
                    results["followups_sent"] += 1

            elif campaign.status == CampaignStatus.FOLLOW_UP_1:
                if campaign.last_email_sent_at and (now - campaign.last_email_sent_at).days >= self.followup_2_days:
                    await self._send_followup(campaign, CampaignStatus.FOLLOW_UP_2)
                    results["followups_sent"] += 1

            elif campaign.status == CampaignStatus.FOLLOW_UP_2:
                if campaign.last_email_sent_at and (now - campaign.last_email_sent_at).days >= self.final_days:
                    # Mark as dead after final follow-up
                    self.tracker.update_status(
                        campaign.id,
                        CampaignStatus.DEAD,
                        death_reason="no_response_after_followups",
                    )
                    results["marked_dead"] += 1

        return results

    async def _send_followup(self, campaign: Campaign, new_status: CampaignStatus):
        """Send a follow-up email."""
        if not self.gmail:
            logger.warning("Gmail client not available for follow-up")
            return

        try:
            from app.integrations.gmail import OutreachEmail

            template_name = new_status.value
            subject = f"Re: {campaign.subject}"

            # Simple follow-up body
            if new_status == CampaignStatus.FOLLOW_UP_1:
                body = "Hi, I wanted to follow up on my previous email. Would love to hear your thoughts when you have a moment."
            else:
                body = "Just checking in one more time about my earlier message. If this isn't a good fit, no worries - just let me know either way."

            email = OutreachEmail(
                to=campaign.prospect.email if campaign.prospect else "",
                subject=subject,
                body_html=f"<p>{body}</p>",
                body_text=body,
            )

            result = await self.gmail.send_reply(
                thread_id=campaign.email_thread_id,
                email=email,
            )

            self.tracker.update_status(
                campaign.id,
                new_status,
                last_email_sent_at=datetime.utcnow(),
                next_followup_at=datetime.utcnow() + timedelta(days=self.final_days if new_status == CampaignStatus.FOLLOW_UP_2 else self.followup_2_days),
            )

        except Exception as e:
            logger.error("Follow-up send failed for %s: %s", campaign.id, e)


# --- Outreach Agent ---


class OutreachAgent:
    """
    Backlink & Outreach Agent - the competitive differentiator.

    Integrates:
    - HARO Response Generator
    - Broken Link Building (via Exa AI)
    - Guest Post Outreach (via Tavily)
    - Unlinked Mention Monitor
    - Campaign Tracker (6 states)
    - Email sending via Gmail API
    - Follow-up automation
    - Link verification
    """

    def __init__(
        self,
        gmail_client,
        dataforseo_client,
        exa_client=None,
        tavily_client=None,
        openai_api_key: str = "",
    ):
        self.gmail = gmail_client
        self.dataforseo = dataforseo_client
        self.exa = exa_client
        self.tavily = tavily_client

        self.campaign_tracker = CampaignTracker()
        self.haro_generator = HAROResponseGenerator(
            openai_api_key=openai_api_key,
            exa_client=exa_client,
            tavily_client=tavily_client,
        )
        self.broken_link_builder = BrokenLinkBuilder(
            dataforseo_client=dataforseo_client,
            exa_client=exa_client,
            tavily_client=tavily_client,
        )
        self.guest_post_outreach = GuestPostOutreach(
            exa_client=exa_client,
            tavily_client=tavily_client,
            dataforseo_client=dataforseo_client,
        )
        self.unlinked_mention_monitor = UnlinkedMentionMonitor(
            exa_client=exa_client,
            tavily_client=tavily_client,
            dataforseo_client=dataforseo_client,
        )
        self.link_verifier = LinkVerifier(dataforseo_client=dataforseo_client)
        self.followup_engine = FollowUpEngine(
            campaign_tracker=self.campaign_tracker,
            gmail_client=gmail_client,
        )

    async def run_broken_link_pipeline(
        self,
        niche_keywords: list[str],
        target_domains: Optional[list[str]] = None,
    ) -> dict:
        """
        End-to-end broken link building pipeline.

        Returns:
            Summary of opportunities found and outreach sent.
        """
        # Discover domains if not provided
        if not target_domains:
            for kw in niche_keywords[:1]:
                domains = await self.broken_link_builder.discover_authority_domains(kw)
                target_domains = domains[:10]

        opportunities = []
        for domain in (target_domains or []):
            broken = await self.broken_link_builder.find_broken_links(domain)
            for link in broken:
                opportunities.append(BrokenLinkOpportunity(
                    broken_url=link["broken_url"],
                    found_on=link["found_on"],
                    domain=link["domain_from"],
                    domain_rank=link["domain_rank"],
                ))

        return {
            "opportunities_found": len(opportunities),
            "domains_scanned": len(target_domains or []),
        }

    async def run_guest_post_pipeline(
        self,
        niche: str,
        target_count: int = 50,
    ) -> dict:
        """
        End-to-end guest post outreach pipeline.

        Returns:
            Summary of targets found and pitches sent.
        """
        targets = await self.guest_post_outreach.discover_targets(
            niche=niche,
            count=target_count,
        )

        return {
            "targets_found": len(targets),
            "top_domains": [t.domain for t in targets[:10]],
        }

    async def run_unlinked_mention_pipeline(
        self,
        brand_variants: list[str],
        our_domain: str,
    ) -> dict:
        """
        End-to-end unlinked mention pipeline.

        Returns:
            Summary of unlinked mentions found and outreach sent.
        """
        mentions = await self.unlinked_mention_monitor.find_unlinked_mentions(
            brand_variants=brand_variants,
            our_domain=our_domain,
        )

        return {
            "unlinked_found": len(mentions),
            "top_domains": [m.domain for m in mentions[:10]],
        }

    async def verify_link(self, campaign_id: str) -> dict:
        """Verify that a campaign's link is live."""
        campaign = self.campaign_tracker.get_campaign(campaign_id)
        if not campaign:
            return {"error": "Campaign not found"}

        result = await self.link_verifier.verify_link(
            target_url=campaign.target_url,
            our_domain="",
            our_page_url=campaign.our_page_url,
        )

        if result["status"] == "live":
            self.campaign_tracker.update_status(
                campaign_id,
                CampaignStatus.ACQUIRED,
                verified_at=datetime.utcnow(),
                link_details=result,
            )
        else:
            campaign.verification_failures += 1
            if campaign.verification_failures >= 3:
                self.campaign_tracker.update_status(
                    campaign_id,
                    CampaignStatus.DEAD,
                    death_reason="link_not_placed_after_verification",
                )

        return result

    async def process_followups(self) -> dict:
        """Process all pending follow-ups."""
        return await self.followup_engine.process_followups()

    def get_campaign_stats(self) -> dict:
        """Get campaign statistics."""
        return self.campaign_tracker.get_stats()
