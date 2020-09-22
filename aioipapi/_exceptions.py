# -*- coding: utf-8 -*-

class IpApiError(Exception):
    pass


class ClientError(IpApiError):
    pass


class TooManyRequests(IpApiError):
    pass


class TooLargeBatchSize(IpApiError):
    pass


class AuthError(IpApiError):
    pass


class HttpError(IpApiError):
    def __init__(self, *args: object, status: int) -> None:
        super().__init__(*args)
        self.status = status
