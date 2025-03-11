# dhandho_bot/Dockerfile
FROM python:3.13-slim AS builder

RUN pip install poetry

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false && poetry install --no-root --no-interaction --no-ansi

COPY app/ ./app/

FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /app /app

CMD ["python", "-m", "app.main"]