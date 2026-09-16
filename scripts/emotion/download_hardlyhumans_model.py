"""Descarga un snapshot fijo y verifica pesos; no modifica el modelo predeterminado."""
import hashlib
import argparse
import json
import re
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from emotv.config import HARDLYHUMANS_MODEL_DIR
from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.infrastructure.vision.emotion_classifier.hardlyhumans_classifier import canonical_labels

REPO_ID = "HardlyHumans/Facial-expression-detection"
REVISION = EmotionModelCatalog().get("hardlyhumans_vit").version
FILES = ["config.json", "preprocessor_config.json", "model.safetensors", "README.md"]


def download_model(target: Path = HARDLYHUMANS_MODEL_DIR) -> Path:
    target = target.resolve()
    if target.exists():
        raise FileExistsError(f"No se sobrescribe una instalación existente: {target}")
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError as error:
        raise RuntimeError('Instala primero: python -m pip install -e ".[emotion-vit]"') from error
    info = HfApi().model_info(REPO_ID, revision=REVISION, files_metadata=True)
    if info.sha != REVISION:
        raise ValueError("La revisión recibida no coincide con la fijada")
    weights = next(item for item in info.siblings if item.rfilename == "model.safetensors")
    if weights.lfs is None:
        raise ValueError("No se recibió el checksum de pesos")
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="hardlyhumans-download-", dir=target.parent) as temporary:
        staged = Path(temporary) / "snapshot"
        (staged / ".cache" / "huggingface" / "download").mkdir(parents=True)
        snapshot_download(REPO_ID, revision=REVISION, allow_patterns=FILES, local_dir=staged, max_workers=1)
        for filename in FILES:
            if not (staged / filename).is_file():
                raise ValueError(f"Snapshot incompleto: {filename}")
        config = json.loads((staged / "config.json").read_text(encoding="utf-8"))
        if config.get("model_type") != "vit":
            raise ValueError("Arquitectura inesperada")
        canonical_labels(config["id2label"])
        card = (staged / "README.md").read_text(encoding="utf-8")
        normalized_card = card.replace("**", "").replace("`", "")
        if re.search(r"\blicense\s*:\s*mit\b", normalized_card, re.IGNORECASE) is None:
            raise ValueError("La ficha descargada no confirma la declaración MIT revisada")
        with (staged / "model.safetensors").open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest != weights.lfs.sha256 or (staged / "model.safetensors").stat().st_size != weights.lfs.size:
            raise ValueError("Checksum o tamaño incorrecto")
        (staged / "emotv-source.json").write_text(json.dumps(dict(repo_id=REPO_ID, revision=REVISION, weights_sha256=digest, declared_model_license="MIT"), indent=2), encoding="utf-8")
        staged.rename(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--system-ca", action="store_true", help="Usar certificados de confianza del sistema sin desactivar TLS")
    args = parser.parse_args()
    if args.system_ca:
        import truststore
        truststore.inject_into_ssl()
    print(f"Descarga experimental de {REPO_ID}; MIT, no dominio público", flush=True)
    print(download_model())
