"""Errors safe to present in the local UI and CLI."""


class APIError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
