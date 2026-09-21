"""Muestra si los modelos faciales pueden usarse desde la API web."""

from emotv.infrastructure.vision.emotion_classifier.model_admission import ServerModelAdmission


def main() -> None:
    admission = ServerModelAdmission()
    for model_id in ("ferplus_onnx", "hardlyhumans_vit"):
        result = admission.evaluate(model_id)
        reasons = "; ".join(result["reasons"]) or "sin restricciones"
        weights, report = admission.paths[model_id]
        print(f"{model_id}: {result['state']} — {reasons}")
        try:
            print(f"  pesos: {'sí' if weights.is_file() else 'no'}; benchmark: {'sí' if report.is_file() else 'no'}")
        except OSError:
            print("  No se pudo inspeccionar los archivos con los permisos actuales.")


if __name__ == "__main__":
    main()
