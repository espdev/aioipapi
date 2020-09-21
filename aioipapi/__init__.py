# -*- coding: utf-8 -*-

from aioipapi import _logging  # noqa
from aioipapi._constants import FIELDS, LANGS
from aioipapi._client import IpApiClient


__version__ = '0.1.0'

__all__ = [
    '__version__',
    'FIELDS',
    'LANGS',
    'IpApiClient',
]
