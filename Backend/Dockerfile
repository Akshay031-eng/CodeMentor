# CodeMentor backend: FastAPI API + code judge for Python, Java, C++ and C.
#
# Build & run locally:
#   docker build -t codementor-api .
#   docker run --env-file .env -p 8002:10000 codementor-api
#
# On Render: Runtime = Docker, Root Directory = Backend (see DEPLOY.md).

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Toolchains used to compile and run student code (JDK 17, gcc, g++),
# plus util-linux for `prlimit` (limits applied before user code starts).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-jdk-headless \
        gcc \
        g++ \
        libc6-dev \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so Docker can cache this layer between code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Untrusted code runs as this separate, unprivileged user. The API process
# itself stays root inside the container ONLY so it can drop to this user
# for every compile/run. A different user cannot kill the server, read its
# memory or /proc files (where the API keys live), or write to /app, and
# its total process count is capped (fork bombs).
RUN useradd --system --no-create-home --uid 10002 --shell /usr/sbin/nologin sandbox \
    && chmod -R go-w /app

# Defaults tuned for small free instances (0.1 CPU / 512 MB on Render free).
# Override any of them in the hosting dashboard.
ENV PORT=10000 \
    SANDBOX_USER=sandbox \
    SANDBOX_MAX_PROCESSES=256 \
    SUBMISSION_MODE=inline \
    MAX_PARALLEL_TESTS=2 \
    MEMORY_LIMIT_MB=192 \
    RUN_TIMEOUT_SECONDS=10 \
    COMPILE_TIMEOUT_SECONDS=60

EXPOSE 10000

HEALTHCHECK --interval=60s --timeout=10s --start-period=120s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '10000'), timeout=5)" || exit 1

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
