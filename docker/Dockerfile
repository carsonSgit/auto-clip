FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fontconfig \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies against a stub package first so the heavy dependency layer
# (opencv, faster-whisper, ...) stays cached when only application source changes.
COPY pyproject.toml README.md ./
RUN mkdir autoclip && touch autoclip/__init__.py \
    && pip install --no-cache-dir .

# Now overlay the real source and reinstall just our package (fast, deps unchanged).
COPY autoclip ./autoclip
RUN pip install --no-cache-dir --no-deps .

COPY brandkit ./brandkit
COPY scripts ./scripts
COPY tests ./tests

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "autoclip.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
