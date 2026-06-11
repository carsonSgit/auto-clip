FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fontconfig \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY autoclip ./autoclip
COPY brandkit ./brandkit
COPY scripts ./scripts
COPY tests ./tests

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "autoclip.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
