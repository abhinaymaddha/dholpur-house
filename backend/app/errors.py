"""Error hierarchy. Routes catch AppError subclasses and turn them into HTTP responses with readable messages."""


class AppError(Exception):
    """Base for every error the app raises on purpose."""

    status_code = 500


class ConfigError(AppError):
    """models.toml / sources.toml / environment is missing something or is invalid."""

    status_code = 500


class ProviderError(AppError):
    """An LLM provider call failed in a way worth showing the user (rate limit, refusal, bad JSON, ...)."""

    status_code = 502


class InterviewError(AppError):
    """The interview can't proceed with the current request (no topic chosen, no open question, ...)."""

    status_code = 400


class IngestRunning(AppError):
    """An ingest was requested while another one is still running."""

    status_code = 409
