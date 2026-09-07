"""Ejecuta el MVP completo y registra su resultado como sesión en memoria."""

if __package__:
    from scripts.run_emotional_exercise_test import main
else:
    from run_emotional_exercise_test import main


if __name__ == "__main__":
    main(
        window_name="EMOtv - Session Test",
        console_title="EMOtv - Session Test",
    )
