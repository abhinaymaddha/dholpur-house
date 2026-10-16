class AdapterError(RuntimeError):
    """A provider adapter failed in a way worth showing the user (rate limit, refusal, bad JSON, ...)."""
