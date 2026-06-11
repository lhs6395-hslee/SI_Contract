"""OpenTelemetry 초기화 — AWS X-Ray 연동."""

import os
import logging

logger = logging.getLogger("si-contract")

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "si-contract-backend")


def init_telemetry(app):
    """FastAPI 앱에 OpenTelemetry 계측 적용. OTEL_ENABLED=true일 때만 활성화."""
    if not OTEL_ENABLED:
        logger.info("OpenTelemetry disabled (OTEL_ENABLED != true)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.propagators.aws import AwsXRayPropagator
        from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
        from opentelemetry import propagate

        resource = Resource.create({"service.name": SERVICE_NAME})
        provider = TracerProvider(
            resource=resource,
            id_generator=AwsXRayIdGenerator(),
        )
        exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        propagate.set_global_textmap(AwsXRayPropagator())

        FastAPIInstrumentor.instrument_app(app)
        BotocoreInstrumentor().instrument()

        logger.info("OpenTelemetry initialized: endpoint=%s, service=%s", OTEL_ENDPOINT, SERVICE_NAME)
    except Exception as e:
        logger.warning("OpenTelemetry init failed (non-blocking): %s", e)
