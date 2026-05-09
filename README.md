# Модели БД

## users

- id BIGINT (telegram user id)

## exercises

- id SERIAL PK
- name VARCHAR(128)
- user_id BIGINT FK → users.id -- кастомные упражнения пользователя

## muscles

- id SERIAL PK
- name VARCHAR(64) -- "грудь", "трицепс", "квадрицепс"

## exercise_muscles -- many-to-many

- exercise_id INT FK → exercises.id
- muscle_id INT FK → muscles.id

## workouts

- id SERIAL PK
- user_id BIGINT FK → users.id
- date DATE
- notes TEXT nullable

## workout_exercises -- какие упражнения были на тренировке

- id SERIAL PK
- workout_id INT FK → workouts.id
- exercise_id INT FK → exercises.id
- position SMALLINT -- порядок упражнений в тренировке

## sets -- конкретный подход

- id SERIAL PK
- workout_exercise_id INT FK → workout_exercises.id
- reps SMALLINT -- количество повторений
- weight NUMERIC(5,2) nullable -- NULL = bodyweight
