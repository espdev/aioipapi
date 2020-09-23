# -*- coding: utf-8 -*-

from importlib_metadata import version, PackageNotFoundError

from aioipapi import _logging  # noqa
from aioipapi._config import Config, config
from aioipapi._constants import FIELDS, LANGS
from aioipapi._client import IpApiClient
from aioipapi._exceptions import IpApiError, ClientError, HttpError, TooManyRequests, TooLargeBatchSize, AuthError


try:
    __version__ = version(__name__)
except PackageNotFoundError:  # pragma: no cover
    __version__ = '0.0.0.dev'

__all__ = [
    '__version__',
    'Config',
    'config',
    'FIELDS',
    'LANGS',
    'IpApiClient',
    'IpApiError',
    'ClientError',
    'HttpError',
    'TooManyRequests',
    'TooLargeBatchSize',
    'AuthError',
]
