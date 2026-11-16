import asyncio
from decimal import Decimal

import pytest

from bot.catalog.api import ExerciseInfo, match_names
from bot.programs import service
from bot.programs.domain import PlanDay, PlanExercise, ProgramPlan
from bot.programs.repository import StoredDay, StoredProgram
from bot.workouts.domain import SetEntry

SETS = (SetEntry(Decimal("100.00"), 5),)


def _plan(*days: list[str]) -> ProgramPlan:
    return ProgramPlan(
        days=tuple(
            PlanDay(f"Day {i}", tuple(PlanExercise(n, SETS, None) for n in names))
            for i, names in enumerate(days, start=1)
        )
    )


class FakeSession:
    committed = False

    async def commit(self):
        self.committed = True


def test_match_names_ignores_case():
    catalog = [ExerciseInfo(1, "Bench Press"), ExerciseInfo(2, "Жим гантелей")]
    assert match_names(["bench press", "ЖИМ ГАНТЕЛЕЙ", "Squat"], catalog) == {
        "bench press": ExerciseInfo(1, "Bench Press"),
        "ЖИМ ГАНТЕЛЕЙ": ExerciseInfo(2, "Жим гантелей"),
    }


def test_unmatched_names_unique_in_order():
    plan = _plan(["Squat", "Bench Press", "Lunge"], ["squat", "Row", "Lunge"])
    found = {"Bench Press": ExerciseInfo(1, "Bench Press")}
    assert service.unmatched_names(plan, found) == ["Squat", "Lunge", "Row"]


class FakeRepo:
    def __init__(self, program_id=5, moved=True):
        self.program = StoredProgram(
            id=program_id,
            next_position=1,
            days=[StoredDay(i, f"Day {i}", []) for i in (1, 2, 3)],
        )
        self.moved = moved
        self.calls = []

    async def get(self, user_id):
        return self.program

    async def set_next_position(self, user_id, program_id, position):
        self.calls.append((user_id, program_id, position))
        return self.moved


def _advance(monkeypatch, repo, done_position):
    monkeypatch.setattr(service, "ProgramRepository", lambda session: repo)
    session = FakeSession()
    asyncio.run(service.advance(session, 42, 5, done_position))
    return session


def test_advance_commits_next_position(monkeypatch):
    repo = FakeRepo()
    session = _advance(monkeypatch, repo, done_position=3)
    assert repo.calls == [(42, 5, 1)]
    assert session.committed


def test_advance_skips_replaced_program(monkeypatch):
    repo = FakeRepo(program_id=6)
    session = _advance(monkeypatch, repo, done_position=1)
    assert repo.calls == []
    assert not session.committed


def test_advance_program_replaced_meanwhile(monkeypatch):
    repo = FakeRepo(moved=False)
    session = _advance(monkeypatch, repo, done_position=1)
    assert repo.calls == [(42, 5, 2)]
    assert not session.committed


class FakeCatalog:
    def __init__(self, session):
        pass

    async def get_visible_many(self, exercise_ids, user_id):
        visible = {1: "Bench Press", 2: "Back Squat"}
        return {i: ExerciseInfo(i, visible[i]) for i in exercise_ids if i in visible}


class RecordingRepo:
    def __init__(self):
        self.replaced = None

    async def replace(self, user_id, plan, exercises):
        self.replaced = (user_id, plan, exercises)


def _import(monkeypatch, plan, exercise_ids):
    repo = RecordingRepo()
    monkeypatch.setattr(service, "ProgramRepository", lambda session: repo)
    monkeypatch.setattr(service, "Catalog", FakeCatalog)
    session = FakeSession()
    asyncio.run(service.import_program(session, 42, plan, exercise_ids))
    return session, repo


def test_import_saves_catalog_names(monkeypatch):
    plan = _plan(["bench press", "Squat"])
    session, repo = _import(monkeypatch, plan, {"bench press": 1, "squat": 2})
    assert repo.replaced == (
        42,
        plan,
        {
            "bench press": ExerciseInfo(1, "Bench Press"),
            "squat": ExerciseInfo(2, "Back Squat"),
        },
    )
    assert session.committed


@pytest.mark.parametrize(
    "exercise_ids",
    [
        {"bench press": 1},  # у Squat нет упражнения
        {"bench press": 1, "squat": 99},  # удалено или чужое
    ],
)
def test_import_rejects_unavailable_exercise(monkeypatch, exercise_ids):
    with pytest.raises(service.ExerciseNotAvailable):
        _import(monkeypatch, _plan(["Bench Press", "Squat"]), exercise_ids)
