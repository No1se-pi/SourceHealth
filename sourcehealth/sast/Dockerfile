# Сборка из корня SourceHealth:
# docker build -f sourcehealth/sast/Dockerfile -t sourcehealth-sast .
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir /workspace && chown 10001:10001 /workspace
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 \
    GIT_ALLOW_PROTOCOL=https GIT_LFS_SKIP_SMUDGE=1 HOME=/tmp
WORKDIR /app
# Копируем только код инструмента, не тесты, temp и содержимое .git.
COPY sourcehealth /app/sourcehealth
RUN echo /app > /usr/local/lib/python3.11/site-packages/sourcehealth.pth
USER 10001:10001
ENTRYPOINT ["python", "-I", "-m", "sourcehealth.sast"]
# -I исключает cwd и PYTHONPATH; пакет устанавливается через доверенный .pth.
