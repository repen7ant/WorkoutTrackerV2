import asyncio
from decimal import Decimal

import pytest

from bot.catalog.api import ExerciseInfo, match_names
from bot.programs import service
from bot.programs.domain import PlanDay, PlanExercise, ProgramPlan
from bot.programs.repository import StoredDay, StoredExercise, StoredProgram
from bot.workouts.domain import SetEntry

SETS = (SetEntry(Decimal("100.00"), 5),)


def _plan(*days: list[str]) -> ProgramPlan:
    return ProgramPlan(
        days=tuple(
            PlanDay(f"Day {i}", tuple(PlanExercise(n, (SETS,), None) for n in names))
            for i, names in enumerate(days, start=1)
        ),
        weeks=1,
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


def _stored(done=None) -> StoredProgram:
    """Push — обе недели, Pull — только первая."""
    return StoredProgram(
        id=5,
        weeks=2,
        days=[
            StoredDay(
                1, "Push", [StoredExercise(1, "Bench", None, [[*SETS], [*SETS]])]
            ),
            StoredDay(2, "Pull", [StoredExercise(2, "Row", None, [[*SETS], []])]),
        ],
        done=done or {},
    )


@pytest.mark.parametrize(
    ("done", "next_one", "week"),
    [
        ({}, (1, 1), [(1, 1), (1, 2)]),
        # Pull пропустили раньше Push: неделя 1 ждёт Push
        ({(1, 2): True}, (1, 1), [(1, 1)]),
        ({(1, 1): False, (1, 2): True}, (2, 1), [(2, 1)]),
        ({(1, 1): False, (1, 2): False, (2, 1): True}, None, []),
    ],
)
def test_next_session_and_week_sessions(done, next_one, week):
    program = _stored(done)
    assert service.next_session(program) == next_one
    current = next_one[0] if next_one else 2
    assert service.week_sessions(program, current) == week


class FakeRepo:
    def __init__(self, added=True):
        self.program = _stored()
        self.added = added
        self.calls = []

    async def get(self, user_id):
        return self.program

    async def add_session(self, user_id, program_id, week, day_position, skipped):
        self.calls.append((user_id, program_id, week, day_position, skipped))
        if self.added:
            self.program.done[(week, day_position)] = skipped
        return self.added


def _complete(monkeypatch, repo, **kwargs):
    monkeypatch.setattr(service, "ProgramRepository", lambda session: repo)
    session = FakeSession()
    result = asyncio.run(service.complete_session(session, 42, 5, 1, 2, **kwargs))
    return session, result


def test_complete_session_returns_program_after_mark(monkeypatch):
    repo = FakeRepo()
    session, result = _complete(monkeypatch, repo, skipped=True)
    assert repo.calls == [(42, 5, 1, 2, True)]
    assert session.committed
    assert result.done == {(1, 2): True}


def test_complete_session_of_replaced_program(monkeypatch):
    repo = FakeRepo(added=False)
    session, result = _complete(monkeypatch, repo)
    assert result is None
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
