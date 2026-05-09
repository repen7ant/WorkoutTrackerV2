import asyncio
import csv
from pathlib import Path

from sqlalchemy import select

from bot.db.session import AsyncSessionLocal
from bot.models.exercise_muscles import ExerciseMuscle
from bot.models.exercises import Exercise
from bot.models.muscles import Muscle

CSV_PATH = Path(__file__).parent / "Exercises.csv"


async def seed():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(Exercise).limit(1))
            if result.scalar():
                print("Already seeded, skipping")
                return

            muscles: dict[str, Muscle] = {}
            exercises_count = 0

            with CSV_PATH.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row["Name"].strip()
                    muscle_names = [m.strip() for m in row["Muscle"].split(";")]

                    exercise = Exercise(name=name, user_id=None)
                    session.add(exercise)
                    await session.flush()
                    exercises_count += 1

                    for muscle_name in muscle_names:
                        if muscle_name not in muscles:
                            muscle = Muscle(name=muscle_name)
                            session.add(muscle)
                            await session.flush()
                            muscles[muscle_name] = muscle

                        link = ExerciseMuscle(
                            exercise_id=exercise.id,
                            muscle_id=muscles[muscle_name].id,
                        )
                        session.add(link)

            print(f"Seeded {exercises_count} exercises and {len(muscles)} muscles")


asyncio.run(seed())
