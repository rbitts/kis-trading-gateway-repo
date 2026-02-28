class RestRateLimitCooldownError(RuntimeError):
    """Raised when REST quote fallback is suppressed due to recent 429 cooldown."""

