class GatewayError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class UnauthorizedError(GatewayError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(status_code=401, code="unauthorized", message=message)


class BadRequestError(GatewayError):
    def __init__(self, message: str, code: str = "bad_request") -> None:
        super().__init__(status_code=400, code=code, message=message)


class RateLimitError(GatewayError):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(status_code=429, code="rate_limit_exceeded", message=message)


class UpstreamError(GatewayError):
    def __init__(self, message: str = "OpenAI returned an invalid response") -> None:
        super().__init__(status_code=502, code="upstream_invalid_response", message=message)


class UpstreamTimeoutError(GatewayError):
    def __init__(self, message: str = "OpenAI request timed out") -> None:
        super().__init__(status_code=504, code="upstream_timeout", message=message)
