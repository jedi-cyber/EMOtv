"""DIAGNÓSTICO LOCAL, FUERA DEL PRODUCTO.

Ejecuta el flujo completo con la webcam de este equipo (OpenCV) y registra el
resultado como sesión en memoria. La API nunca abre una cámara: en EMOtv la
captura ocurre en el navegador.
"""

if __package__:
    from scripts.run_emotional_exercise_test import main
else:
    from run_emotional_exercise_test import main


if __name__ == "__main__":
    main(
        window_name="EMOtv - Session Test",
        console_title="EMOtv - Session Test",
    )
