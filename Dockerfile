FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY aivisibility ./aivisibility
ENV PATH="/app/.venv/bin:$PATH" MLFLOW_DISABLE_AGENT_HINT=1

# Default command is the model API; docker-compose overrides it for MLflow.
CMD ["uvicorn", "aivisibility.classifier.serve:app", "--host", "0.0.0.0", "--port", "8000"]
