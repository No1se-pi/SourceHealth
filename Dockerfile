FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-server.lock ./
RUN pip install --no-cache-dir -r requirements-server.lock
COPY pyproject.toml README.md LICENSE alembic.ini ./
COPY sourcehealth ./sourcehealth
COPY migrations ./migrations
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home app
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "sourcehealth.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
