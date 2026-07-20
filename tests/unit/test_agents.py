import uuid

import httpx
import pytest
from proactive_core.agents.base import Agent, AgentContext, RunStatus
from proactive_core.agents.implementations import (
    ActionExecutorAgent,
    ActionInput,
    CompetitorAgent,
    CompetitorInput,
    ContentAuditInput,
    CrawlInput,
    DecisionEngineAgent,
    DecisionInput,
    ForgeAgent,
    OutreachAgent,
    OutreachInput,
    RankInput,
    ScoutAgent,
    SentinelAgent,
    TechnicalAgent,
    TechnicalInput,
)
from pydantic import BaseModel


@pytest.fixture
def context() -> AgentContext:
    return AgentContext(org_id=uuid.uuid4(), project_id=uuid.uuid4(), trace_id="trace-test")


@pytest.mark.asyncio
async def test_forge_dual_scoring(context: AgentContext) -> None:
    all_google = {
        "title_optimization": 100,
        "meta_description": 100,
        "heading_structure": 100,
        "content_depth": 100,
        "keyword_usage": 100,
        "internal_linking": 100,
        "image_optimization": 100,
        "eeat_signals": 100,
        "url_structure": 100,
        "mobile_readability": 100,
        "schema_markup": 100,
        "page_speed_correlation": 100,
    }
    all_ai = {
        "question_answer_format": 100,
        "structured_data": 100,
        "entity_clarity": 100,
        "citation_worthiness": 100,
        "conversational_tone": 100,
        "featured_snippet_ready": 100,
        "passage_independence": 100,
        "freshness_signals": 100,
        "source_authority": 100,
        "ai_crawlability": 100,
    }
    result = await ForgeAgent().run(ContentAuditInput(google_signals=all_google, ai_signals=all_ai), context)
    assert result.status == RunStatus.COMPLETED
    assert result.output is not None
    assert result.output.google_score == 100
    assert result.output.ai_readiness_score == 100


@pytest.mark.asyncio
async def test_technical_rules_and_schema(context: AgentContext) -> None:
    result = await TechnicalAgent().run(TechnicalInput(url="https://example.com", title=None, lcp_ms=4000), context)
    assert result.output is not None
    assert {issue.type for issue in result.output.issues} >= {"missing_title", "missing_meta", "poor_lcp"}
    assert result.output.structured_data["@type"] == "WebPage"


@pytest.mark.asyncio
async def test_decision_priority_formula(context: AgentContext) -> None:
    result = await DecisionEngineAgent().run(
        DecisionInput(impact=10, urgency=10, confidence=1, effort=1, risk=0.1), context
    )
    assert result.output is not None
    assert result.output.score == 100
    assert result.output.priority == "P0"
    assert result.output.approval_required is False


@pytest.mark.asyncio
async def test_outreach_sequence_and_reply_stop(context: AgentContext) -> None:
    agent = OutreachAgent()
    planned = await agent.run(
        OutreachInput(
            campaign_type="haro",
            recipient="journalist@example.com",
            subject="Source response",
            body="Evidence-led response",
        ),
        context,
    )
    assert planned.output is not None
    assert planned.output.action == "draft"
    assert len(planned.output.follow_ups) == 3
    stopped = await agent.run(
        OutreachInput(
            campaign_type="haro",
            recipient="journalist@example.com",
            subject="Source response",
            body="Evidence-led response",
            replied=True,
        ),
        context,
    )
    assert stopped.output is not None
    assert stopped.output.action == "stop"


@pytest.mark.asyncio
async def test_competitor_trigger_and_executor_gate(context: AgentContext) -> None:
    competitor = await CompetitorAgent().run(
        CompetitorInput(own_positions={"a": 8, "b": 9, "c": 10}, competitor_positions={"a": 2, "b": 3, "c": 4}),
        context,
    )
    assert competitor.output is not None and competitor.output.overtake_triggered
    execution = await ActionExecutorAgent().run(
        ActionInput(type="send_email", payload={"draft_id": "draft-1"}), context
    )
    assert execution.output is not None
    assert execution.output.status == "approval_required"


@pytest.mark.asyncio
async def test_scout_executor_and_decision_branches(context: AgentContext) -> None:
    ranked = await ScoutAgent().run(
        RankInput(
            keyword="agentic seo",
            domain="example.com",
            results=[
                {"type": "featured_snippet", "url": "https://other.example/a", "rank_absolute": 1},
                {"type": "organic", "url": "https://www.example.com/page", "rank_absolute": 4},
            ],
        ),
        context,
    )
    assert ranked.output is not None
    assert ranked.output.position == 4
    assert ranked.output.features == ["featured_snippet"]

    for score_input, priority in (
        (DecisionInput(impact=5, urgency=5, confidence=0.5, effort=10, risk=1), "P3"),
        (DecisionInput(impact=8, urgency=8, confidence=0.8, effort=8, risk=1), "P1"),
    ):
        decision = await DecisionEngineAgent().run(score_input, context)
        assert decision.output is not None and decision.output.priority == priority

    dry_run = await ActionExecutorAgent().run(ActionInput(type="notify", payload={"message": "done"}), context)
    assert dry_run.output is not None and dry_run.output.status == "dry_run"
    live_context = context.model_copy(update={"dry_run": False})
    executed = await ActionExecutorAgent().run(ActionInput(type="send_email", payload={}, approved=True), live_context)
    assert executed.output is not None and executed.output.status == "executed"


@pytest.mark.asyncio
async def test_sentinel_bounded_crawl_and_http_failure(context: AgentContext, monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __init__(self, status_code: int, text: str = "") -> None:
            self.status_code = status_code
            self.text = text
            self.headers = {"content-type": "text/html"}

    class Client:
        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, url: str) -> Response:
            if url.endswith("/missing"):
                raise httpx.ConnectError("offline")
            return Response(
                200, "<title>Home</title><a href='/missing'>Missing</a><a href='https://other.test'>Away</a>"
            )

    monkeypatch.setattr("proactive_core.agents.implementations.httpx.AsyncClient", lambda **kwargs: Client())
    result = await SentinelAgent().run(
        CrawlInput(url="https://example.com", max_pages=2, allow_private_networks=True), context
    )
    assert result.output is not None
    assert result.output.pages[0].title == "Home"
    assert result.output.broken_links == ["https://example.com/missing"]


class FailureInput(BaseModel):
    value: str


class FailureOutput(BaseModel):
    value: str


class FailureAgent(Agent[FailureInput, FailureOutput]):
    key = "failure"

    async def execute(self, input_data: FailureInput, context: AgentContext) -> FailureOutput:
        raise RuntimeError("deterministic failure")


@pytest.mark.asyncio
async def test_agent_failure_is_isolated(context: AgentContext) -> None:
    result = await FailureAgent().run(FailureInput(value="input"), context)
    assert result.status == RunStatus.FAILED
    assert result.error == "deterministic failure"
