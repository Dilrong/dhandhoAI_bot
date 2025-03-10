# dhandho_bot/Dockerfile
FROM python:3.13-slim AS builder

# Poetry 설치
RUN pip install poetry

# Poetry 버전 확인 (디버깅용)
RUN poetry --version

# 작업 디렉토리 설정
WORKDIR /app

# Poetry 설정 파일 복사
COPY pyproject.toml poetry.lock ./

# 복사된 파일 확인 (디버깅용)
RUN ls -la && cat pyproject.toml

# 의존성 설치 (--no-root 포함)
RUN poetry config virtualenvs.create false && poetry install --no-root --no-interaction --no-ansi

# 소스 코드 복사
COPY app/ ./app/

# 실행 스테이지
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /app /app

CMD ["python", "-m", "app.bot"]