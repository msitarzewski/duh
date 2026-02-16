"""Tests for voting protocol, classifier, Vote model, and migration."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config

from duh.consensus.classifier import TaskType, classify_task_type
from duh.consensus.voting import VoteResult, VotingAggregation, run_voting
from duh.memory.models import Vote
from duh.memory.repository import MemoryRepository
from duh.providers.manager import ProviderManager
from tests.fixtures.providers import MockProvider

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Helpers ──────────────────────────────────────────────────────


async def _make_pm(
    *providers: MockProvider,
) -> ProviderManager:
    """Register providers and return a ProviderManager."""
    pm = ProviderManager()
    for p in providers:
        await pm.register(p)
    return pm


def _multi_provider_setup() -> tuple[MockProvider, MockProvider]:
    """Two providers with different costs (cheap + expensive)."""
    cheap = MockProvider(
        provider_id="cheap",
        responses={"small-model": "Cheap answer"},
        input_cost=1.0,
        output_cost=2.0,
    )
    expensive = MockProvider(
        provider_id="expensive",
        responses={"big-model": "Expensive answer"},
        input_cost=10.0,
        output_cost=30.0,
    )
    return cheap, expensive


# ── VoteResult dataclass ─────────────────────────────────────────


class TestVoteResult:
    def test_frozen(self) -> None:
        vr = VoteResult(model_ref="a:b", content="hello")
        with pytest.raises(AttributeError):
            vr.content = "bye"  # type: ignore[misc]

    def test_defaults(self) -> None:
        vr = VoteResult(model_ref="a:b", content="c")
        assert vr.confidence == 0.0

    def test_fields(self) -> None:
        vr = VoteResult(model_ref="x:y", content="answer", confidence=0.9)
        assert vr.model_ref == "x:y"
        assert vr.content == "answer"
        assert vr.confidence == pytest.approx(0.9)


# ── VotingAggregation dataclass ──────────────────────────────────


class TestVotingAggregation:
    def test_frozen(self) -> None:
        va = VotingAggregation(
            votes=(), decision="d", strategy="majority", confidence=0.8
        )
        with pytest.raises(AttributeError):
            va.decision = "x"  # type: ignore[misc]

    def test_fields(self) -> None:
        v = VoteResult(model_ref="a:b", content="c")
        va = VotingAggregation(
            votes=(v,), decision="final", strategy="weighted", confidence=0.75
        )
        assert len(va.votes) == 1
        assert va.decision == "final"
        assert va.strategy == "weighted"
        assert va.confidence == pytest.approx(0.75)


# ── run_voting: parallel execution ──────────────────────────────


class TestRunVotingParallel:
    async def test_all_models_called(self) -> None:
        """All registered models receive the question."""
        cheap, expensive = _multi_provider_setup()
        pm = await _make_pm(cheap, expensive)

        await run_voting("What is 2+2?", pm)

        assert len(cheap.call_log) >= 1
        assert len(expensive.call_log) >= 1

    async def test_no_models_returns_empty(self) -> None:
        pm = ProviderManager()
        result = await run_voting("empty?", pm)

        assert result.votes == ()
        assert result.decision == ""
        assert result.confidence == 0.0


# ── run_voting: single model fallback ────────────────────────────


class TestRunVotingSingleModel:
    async def test_single_model_returns_direct(self) -> None:
        solo = MockProvider(
            provider_id="solo",
            responses={"only-model": "Direct answer"},
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _make_pm(solo)

        result = await run_voting("What?", pm)

        assert result.confidence == pytest.approx(1.0)
        assert result.decision == "Direct answer"
        assert len(result.votes) == 1
        assert result.votes[0].content == "Direct answer"

    async def test_single_model_no_aggregation_call(self) -> None:
        """With one model, no meta-judge call should happen."""
        solo = MockProvider(
            provider_id="solo",
            responses={"one": "Answer"},
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _make_pm(solo)

        await run_voting("Q?", pm)

        # Only 1 call (the vote), no second call for aggregation
        assert len(solo.call_log) == 1


# ── run_voting: majority aggregation ────────────────────────────


class TestRunVotingMajority:
    async def test_majority_uses_strongest_as_judge(self) -> None:
        cheap, expensive = _multi_provider_setup()
        pm = await _make_pm(cheap, expensive)

        result = await run_voting("Best language?", pm, aggregation="majority")

        assert result.strategy == "majority"
        # Expensive model gets called twice: once for vote, once for judging
        assert len(expensive.call_log) == 2

    async def test_majority_returns_decision(self) -> None:
        cheap, expensive = _multi_provider_setup()
        pm = await _make_pm(cheap, expensive)

        result = await run_voting("Test?", pm, aggregation="majority")

        assert result.decision != ""
        assert len(result.votes) == 2

    async def test_majority_confidence(self) -> None:
        cheap, expensive = _multi_provider_setup()
        pm = await _make_pm(cheap, expensive)

        result = await run_voting("Test?", pm, aggregation="majority")

        assert result.confidence == pytest.approx(0.8)


# ── run_voting: weighted aggregation ─────────────────────────────


class TestRunVotingWeighted:
    async def test_weighted_uses_strongest_as_synthesizer(self) -> None:
        cheap, expensive = _multi_provider_setup()
        pm = await _make_pm(cheap, expensive)

        result = await run_voting("Merge?", pm, aggregation="weighted")

        assert result.strategy == "weighted"
        # Expensive model called twice: vote + synthesis
        assert len(expensive.call_log) == 2

    async def test_weighted_returns_decision(self) -> None:
        cheap, expensive = _multi_provider_setup()
        pm = await _make_pm(cheap, expensive)

        result = await run_voting("Merge?", pm, aggregation="weighted")

        assert result.decision != ""
        assert len(result.votes) == 2

    async def test_weighted_confidence(self) -> None:
        cheap, expensive = _multi_provider_setup()
        pm = await _make_pm(cheap, expensive)

        result = await run_voting("Test?", pm, aggregation="weighted")

        assert result.confidence == pytest.approx(0.85)


# ── run_voting: error handling ───────────────────────────────────


class TestRunVotingErrors:
    async def test_failed_vote_excluded(self) -> None:
        """If one model fails, remaining votes still aggregate."""

        class FailProvider(MockProvider):
            async def send(self, *args, **kwargs):  # type: ignore[override]
                raise RuntimeError("model offline")

        fail = FailProvider(
            provider_id="broken",
            responses={"bad-model": ""},
            input_cost=1.0,
            output_cost=1.0,
        )
        good = MockProvider(
            provider_id="good",
            responses={"ok-model": "Good answer"},
            input_cost=2.0,
            output_cost=5.0,
        )
        pm = await _make_pm(fail, good)

        result = await run_voting("Test?", pm)

        # Only one vote succeeds -> single-model fallback
        assert len(result.votes) == 1
        assert result.votes[0].content == "Good answer"
        assert result.confidence == pytest.approx(1.0)

    async def test_all_votes_fail(self) -> None:
        """If all models fail, return empty result."""

        class FailProvider(MockProvider):
            async def send(self, *args, **kwargs):  # type: ignore[override]
                raise RuntimeError("offline")

        fail = FailProvider(
            provider_id="fail",
            responses={"bad": ""},
            input_cost=1.0,
            output_cost=1.0,
        )
        pm = await _make_pm(fail)

        result = await run_voting("Test?", pm)

        assert result.votes == ()
        assert result.decision == ""
        assert result.confidence == 0.0


# ── TaskType classifier ─────────────────────────────────────────


class TestTaskType:
    def test_enum_values(self) -> None:
        assert TaskType.REASONING.value == "reasoning"
        assert TaskType.JUDGMENT.value == "judgment"
        assert TaskType.UNKNOWN.value == "unknown"


class TestClassifyTaskType:
    async def test_reasoning_classification(self) -> None:
        provider = MockProvider(
            provider_id="cls",
            responses={"classifier": '{"task_type": "reasoning"}'},
            input_cost=0.5,
            output_cost=1.0,
        )
        pm = await _make_pm(provider)

        result = await classify_task_type("What is 2+2?", pm)

        assert result == TaskType.REASONING

    async def test_judgment_classification(self) -> None:
        provider = MockProvider(
            provider_id="cls",
            responses={"classifier": '{"task_type": "judgment"}'},
            input_cost=0.5,
            output_cost=1.0,
        )
        pm = await _make_pm(provider)

        result = await classify_task_type("Is Python better than Rust?", pm)

        assert result == TaskType.JUDGMENT

    async def test_fallback_on_parse_error(self) -> None:
        provider = MockProvider(
            provider_id="cls",
            responses={"classifier": "not json at all"},
            input_cost=0.5,
            output_cost=1.0,
        )
        pm = await _make_pm(provider)

        result = await classify_task_type("Q?", pm)

        assert result == TaskType.UNKNOWN

    async def test_fallback_on_invalid_type(self) -> None:
        provider = MockProvider(
            provider_id="cls",
            responses={"classifier": '{"task_type": "creative"}'},
            input_cost=0.5,
            output_cost=1.0,
        )
        pm = await _make_pm(provider)

        result = await classify_task_type("Q?", pm)

        assert result == TaskType.UNKNOWN

    async def test_fallback_on_model_error(self) -> None:
        class FailProvider(MockProvider):
            async def send(self, *args, **kwargs):  # type: ignore[override]
                raise RuntimeError("model down")

        provider = FailProvider(
            provider_id="cls",
            responses={"classifier": ""},
            input_cost=0.5,
            output_cost=1.0,
        )
        pm = await _make_pm(provider)

        result = await classify_task_type("Q?", pm)

        assert result == TaskType.UNKNOWN

    async def test_fallback_on_no_models(self) -> None:
        pm = ProviderManager()

        result = await classify_task_type("Q?", pm)

        assert result == TaskType.UNKNOWN

    async def test_uses_cheapest_model(self) -> None:
        """Classifier should prefer the model with lowest input cost."""
        cheap = MockProvider(
            provider_id="cheap",
            responses={"small": '{"task_type": "reasoning"}'},
            input_cost=0.1,
            output_cost=0.5,
        )
        expensive = MockProvider(
            provider_id="expensive",
            responses={"big": '{"task_type": "judgment"}'},
            input_cost=10.0,
            output_cost=30.0,
        )
        pm = await _make_pm(cheap, expensive)

        await classify_task_type("Q?", pm)

        # Only the cheap provider should have been called
        assert len(cheap.call_log) == 1
        assert len(expensive.call_log) == 0

    async def test_json_mode_requested(self) -> None:
        provider = MockProvider(
            provider_id="cls",
            responses={"model": '{"task_type": "reasoning"}'},
            input_cost=0.5,
            output_cost=1.0,
        )
        pm = await _make_pm(provider)

        await classify_task_type("Q?", pm)

        # Verify response_format was set to "json"
        assert provider.call_log[0]["response_format"] == "json"


# ── Vote model ──────────────────────────────────────────────────


class TestVoteModel:
    def test_table_name(self) -> None:
        assert Vote.__tablename__ == "votes"

    async def test_vote_defaults_after_persist(self, db_session: AsyncSession) -> None:
        from duh.memory.models import Thread

        thread = Thread(question="Test")
        db_session.add(thread)
        await db_session.flush()

        vote = Vote(thread_id=thread.id, model_ref="mock:m", content="answer")
        db_session.add(vote)
        await db_session.commit()

        assert vote.id is not None
        assert len(vote.id) == 36
        assert vote.created_at is not None

    async def test_vote_thread_fk(self, db_session: AsyncSession) -> None:
        from sqlalchemy.exc import IntegrityError

        vote = Vote(thread_id="nonexistent", model_ref="m:a", content="x")
        db_session.add(vote)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_vote_thread_relationship(self, db_session: AsyncSession) -> None:
        from duh.memory.models import Thread

        thread = Thread(question="Q")
        db_session.add(thread)
        await db_session.flush()

        vote = Vote(thread_id=thread.id, model_ref="m:a", content="answer")
        db_session.add(vote)
        await db_session.commit()

        await db_session.refresh(vote, ["thread"])
        assert vote.thread.id == thread.id


# ── Vote repository CRUD ────────────────────────────────────────


class TestVoteRepository:
    async def test_save_vote(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q")
        await db_session.commit()

        vote = await repo.save_vote(thread.id, "mock:m", "answer content")
        await db_session.commit()

        assert vote.id is not None
        assert vote.model_ref == "mock:m"
        assert vote.content == "answer content"

    async def test_get_votes_empty(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q")
        await db_session.commit()

        votes = await repo.get_votes(thread.id)
        assert votes == []

    async def test_get_votes_returns_ordered(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q")
        await db_session.commit()

        await repo.save_vote(thread.id, "a:m1", "first")
        await repo.save_vote(thread.id, "b:m2", "second")
        await db_session.commit()

        votes = await repo.get_votes(thread.id)
        assert len(votes) == 2
        assert votes[0].content == "first"
        assert votes[1].content == "second"

    async def test_get_votes_scoped_to_thread(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        t1 = await repo.create_thread("Q1")
        t2 = await repo.create_thread("Q2")
        await db_session.commit()

        await repo.save_vote(t1.id, "a:m", "for t1")
        await repo.save_vote(t2.id, "b:m", "for t2")
        await db_session.commit()

        votes_t1 = await repo.get_votes(t1.id)
        votes_t2 = await repo.get_votes(t2.id)
        assert len(votes_t1) == 1
        assert votes_t1[0].content == "for t1"
        assert len(votes_t2) == 1
        assert votes_t2[0].content == "for t2"


# ── Migration tests ─────────────────────────────────────────────


@pytest.fixture
def alembic_config(tmp_path):
    """Alembic config for migration tests."""
    db_path = tmp_path / "test.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg, db_path


class TestVoteMigration:
    def test_upgrade_to_003(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "003")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "votes" in tables

    def test_votes_table_schema(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "003")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(votes)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert "id" in columns
        assert "thread_id" in columns
        assert "model_ref" in columns
        assert "content" in columns
        assert "created_at" in columns

    def test_downgrade_003_to_002(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "003")
        command.downgrade(cfg, "002")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "votes" not in tables

    def test_data_survives_002_to_003(self, alembic_config) -> None:
        """Existing data survives upgrade from 002 to 003."""
        cfg, db_path = alembic_config
        command.upgrade(cfg, "002")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO threads (id, question, status, created_at, "
            "updated_at) VALUES ('t1', 'Test Q', 'active', "
            "'2026-01-01', '2026-01-01')"
        )
        conn.commit()
        conn.close()

        command.upgrade(cfg, "003")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT question FROM threads WHERE id='t1'")
        row = cursor.fetchone()
        conn.close()

        assert row[0] == "Test Q"

    def test_upgrade_head_includes_votes(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "head")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "votes" in tables
