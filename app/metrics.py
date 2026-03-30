from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from starlette.responses import Response


class MetricsService:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests_total = Counter(
            "requests_total",
            "Общее количество запросов к gateway.",
            registry=self.registry,
        )
        self.requests_failed_total = Counter(
            "requests_failed_total",
            "Количество неуспешных запросов к gateway.",
            registry=self.registry,
        )
        self.upstream_openai_latency_ms = Histogram(
            "upstream_openai_latency_ms",
            "Время ответа OpenAI в миллисекундах.",
            registry=self.registry,
        )
        self.upstream_openai_errors_total = Counter(
            "upstream_openai_errors_total",
            "Количество ошибок OpenAI.",
            registry=self.registry,
        )

    def render(self) -> Response:
        return Response(generate_latest(self.registry), media_type=CONTENT_TYPE_LATEST)
