FROM python:3.12-slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libmupdf-dev \
        gcc \
        libc6-dev && \
    rm -rf /var/lib/apt/lists/*

FROM base AS builder
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --upgrade pip --no-cache-dir && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runner
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libmupdf-dev && \
    rm -rf /var/lib/apt/lists/*

RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

COPY --from=builder /install /usr/local
COPY backend/ .
COPY templates/ /app/templates/
COPY templates/ /templates/

RUN mkdir -p /app/storage /app/results && \
    chown -R appuser:appgroup /app/storage /app/results

USER appuser
EXPOSE 8001

# --timeout-graceful-shutdown: SIGTERM 후 in-flight 요청(동기 파이프라인 ~60초) 완료 대기
# (k8s terminationGracePeriodSeconds 120s 안에서 동작)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2", "--timeout-graceful-shutdown", "90"]
