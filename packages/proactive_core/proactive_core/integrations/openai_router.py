"""Role-aware OpenAI Responses API router with structured Pydantic outputs."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, TypeVar

from openai import AsyncOpenAI
from openai.types.shared_params import Reasoning
from pydantic import BaseModel

OutputT = TypeVar("OutputT", bound=BaseModel)


class ModelRole(StrEnum):
    """Quality, latency, and cost roles used by agents."""

    EXTRACTION = "extraction"
    ROUTINE = "routine"
    HIGH_IMPACT = "high_impact"
    CODE_REPAIR = "code_repair"


class ModelRoute(BaseModel):
    """One model and preserved reasoning policy."""

    model: str
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]


ROUTES = {
    ModelRole.EXTRACTION: ModelRoute(model="gpt-5.6-luna", reasoning_effort="none"),
    ModelRole.ROUTINE: ModelRoute(model="gpt-5.6-terra", reasoning_effort="low"),
    ModelRole.HIGH_IMPACT: ModelRoute(model="gpt-5.6-sol", reasoning_effort="high"),
    ModelRole.CODE_REPAIR: ModelRoute(model="gpt-5.3-codex", reasoning_effort="high"),
}
LEGACY_MODELS = {"gpt-4o": {"enabled": False, "reason": "legacy alias disabled by policy"}}


class OpenAIRouter:
    """Run typed Responses calls while preserving each workload's model role."""

    def __init__(self, api_key: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate(
        self,
        *,
        role: ModelRole,
        developer_prompt: str,
        user_input: str,
        output_type: type[OutputT],
    ) -> OutputT:
        """Parse one strict structured response into its Pydantic contract."""
        route = ROUTES[role]
        response = await self.client.responses.parse(
            model=route.model,
            reasoning=Reasoning(effort=route.reasoning_effort),
            input=[
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": user_input},
            ],
            text_format=output_type,
        )
        if response.output_parsed is None:
            raise RuntimeError("OpenAI response did not satisfy the structured output contract")
        return response.output_parsed
