"""Domain errors. Messages are short, user-safe and never echo user input."""


class DomainError(Exception):
    status = 400

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Invalid(DomainError):
    status = 422


class NotFound(DomainError):
    status = 404


class Conflict(DomainError):
    status = 409
