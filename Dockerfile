FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/mcp

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 mcp

WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY server.py settings.example.json smoke_test.py ./
COPY toolbox ./toolbox
RUN mkdir -p /home/mcp/Documents/Codex /app/.state \
    && chown -R mcp:mcp /home/mcp /app

USER mcp
ENTRYPOINT ["python", "/app/server.py"]
