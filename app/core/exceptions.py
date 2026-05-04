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


class BadRequestError(AppError):
    def __init__(self, message: str, code: str = "BAD_REQUEST") -> None:
        super().__init__(message=message, code=code, status_code=400)


class ConflictError(AppError):
    def __init__(self, message: str, code: str = "CONFLICT") -> None:
        super().__init__(message=message, code=code, status_code=409)


class NotFoundError(AppError):
    def __init__(self, message: str, code: str = "NOT_FOUND") -> None:
        super().__init__(message=message, code=code, status_code=404)


class NotImplementedAppError(AppError):
    def __init__(self, message: str, code: str = "NOT_IMPLEMENTED") -> None:
        super().__init__(message=message, code=code, status_code=501)
