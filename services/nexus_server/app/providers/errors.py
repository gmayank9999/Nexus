class ProviderError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ProviderConfigurationError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__("PROVIDER_CONFIGURATION_ERROR", message, retryable=False)
