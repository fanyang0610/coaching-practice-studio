# Always-on deployment for Render, Fly.io, Railway, Cloud Run or any Docker host.
# Configure with environment variables (see README): OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL,
# DATABASE_URL (Postgres), STUDIO_SECRET_KEY, STUDIO_ADMIN_EMAIL, STUDIO_ADMIN_PASSWORD.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_ANALYTICS_ENABLED=False

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home coach && chown -R coach /app
USER coach

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"7860\")}/ping', timeout=4)"
CMD ["python", "web_app.py"]
