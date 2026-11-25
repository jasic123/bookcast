FROM node:24-bookworm-slim AS node
FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && useradd --create-home --uid 10001 bookcast && mkdir -p /data /app/generated_audio && chown -R bookcast:bookcast /data /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mcp-servers/package*.json ./mcp-servers/
RUN cd mcp-servers && npm ci --omit=dev && npm cache clean --force
RUN chown -R bookcast:bookcast /app/mcp-servers
COPY --chown=bookcast:bookcast app ./app
COPY --chown=bookcast:bookcast worker.py ./worker.py
USER bookcast
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
