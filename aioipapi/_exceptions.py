# -*- coding: utf-8 -*-

class IpApiError(Exception):
    pass


class ClientError(IpApiError):
    pass


class HttpError(IpApiError):
    def __init__(self, *args: object, status: int) -> None:
        super().__init__(*args)
        self.status = status


class TooManyRequests(HttpError):
    pass


class TooLargeBatchSize(HttpError):
    pass


class AuthError(HttpError):
    pass
