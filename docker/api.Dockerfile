# syntax=docker/dockerfile:1

# --- Etapa 0: almacén de CA (agrega las CA opcionales de docker/certs/*.crt) ---
FROM python:3.12-slim AS certs
COPY docker/certs/ /usr/local/share/ca-certificates/emotv/
RUN update-ca-certificates


# --- Etapa 1: dependencias de Python ---
FROM python:3.12-slim AS deps

COPY --from=certs /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
# Solo pyproject y un paquete mínimo: la capa se reutiliza mientras no cambien
# las dependencias, aunque cambie el código.
COPY pyproject.toml ./
RUN mkdir -p src/emotv && touch src/emotv/__init__.py \
    && pip install . \
    # emotv se ejecuta desde /app/src: config.py calcula BASE_DIR desde su
    # propia ubicación y necesita ver models/, docs/ y migrations/ en /app.
    && pip uninstall -y emotv


# --- Etapa 2: runtime ---
FROM python:3.12-slim AS runtime

# Mismo almacén de CA: el servicio models descarga pesos por HTTPS.
COPY --from=certs /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

# Librerías del sistema verificadas con ldd:
#   cv2 -> libGL.so.1 (libgl1), libglib-2.0.so.0 (libglib2.0-0)
#   mediapipe/tasks/c/libmediapipe.so -> libEGL.so.1 (libegl1), libGLESv2.so.2 (libgles2)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libegl1 libgles2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Falla el build si falta alguna librería nativa (libmediapipe.so se carga
# de forma diferida al crear PoseLandmarker, por eso se abre explícitamente).
RUN python -c "import ctypes, pathlib, cv2, mediapipe, onnxruntime; \
ctypes.CDLL(str(pathlib.Path(mediapipe.__file__).parent / 'tasks' / 'c' / 'libmediapipe.so')); \
print('cv2', cv2.__version__, '| mediapipe', mediapipe.__version__, '| onnxruntime', onnxruntime.__version__)"

# Home propio y escribible: matplotlib (dependencia de mediapipe) y onnxruntime guardan caché allí.
RUN groupadd --system emotv \
    && useradd --system --gid emotv --create-home --home-dir /home/emotv --shell /usr/sbin/nologin emotv

WORKDIR /app
COPY alembic.ini pyproject.toml ./
COPY migrations ./migrations
COPY src ./src
COPY scripts ./scripts
COPY docs/consent-demo.md ./docs/consent-demo.md
COPY docker/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh

# El volumen emotv_models hereda este dueño la primera vez que se crea.
RUN mkdir -p models/weights && chown -R emotv:emotv models \
    && chmod 0755 /usr/local/bin/api-entrypoint.sh

USER emotv
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/api-entrypoint.sh"]
