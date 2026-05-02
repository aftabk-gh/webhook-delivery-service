from dataclasses import dataclass


@dataclass(slots=True)
class AppError(Exception):
    message: str
    code: str
    status_code: int

    def __str__(self) -> str:
        return self.message


class AuthenticationError(AppError):
    def __init__(self, message: str, code: str = "AUTHENTICATION_FAILED") -> None:
        super().__init__(message=message, code=code, status_code=401)


class ConflictError(AppError):
    def __init__(self, message: str, code: str = "CONFLICT") -> None:
        super().__init__(message=message, code=code, status_code=409)
