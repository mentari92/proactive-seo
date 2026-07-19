import uuid

from proactive_core.agent_tasks import INPUT_MODELS, executor, run_agent
from proactive_core.agents.implementations import AGENTS


def test_all_agents_have_registered_task_inputs() -> None:
    assert set(INPUT_MODELS) == set(AGENTS)


def test_worker_entry_point_returns_serializable_agent_result() -> None:
    context = {
        "org_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "trace_id": "worker-test",
        "dry_run": True,
    }
    result = run_agent(
        "forge",
        {
            "google_signals": {"title_optimization": 100},
            "ai_signals": {"question_answer_format": 100},
        },
        context,
    )
    assert result["agent"] == "forge"
    assert result["status"] == "completed"
    executed = executor.run({"type": "notify", "payload": {}}, context)
    assert executed["output"]["status"] == "dry_run"
