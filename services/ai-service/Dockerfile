# ai-service 이미지 — 빌드 컨텍스트는 repo ROOT (backend/services/ai_core.py 공유 복사).
#   docker build -f services/ai-service/Dockerfile -t <img> .
FROM python:3.12-slim AS builder
WORKDIR /app
COPY services/ai-service/requirements.txt .
RUN pip install --upgrade pip --no-cache-dir && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app

RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

COPY --from=builder /install /usr/local
# ai-service HTTP 어댑터 + backend와 공유하는 AI 코어(동일 코드로 동작 일치)
COPY services/ai-service/main.py .
COPY backend/services/ai_core.py .

USER appuser
EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
