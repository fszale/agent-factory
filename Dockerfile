FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

COPY pyproject.toml README.md ./
COPY agent_factory ./agent_factory
COPY twin_seeds ./twin_seeds
COPY twins ./twins
COPY installed_twins ./installed_twins

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["python", "-m", "agent_factory.cli", "serve", "--registry-root", "/app/installed_twins", "--host", "0.0.0.0", "--port", "8080"]
