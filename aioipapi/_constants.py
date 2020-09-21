# -*- coding: utf-8 -*-

import sys


BASE_URL = 'http://ip-api.com/'

JSON_ENDPOINT = 'json'
XML_ENDPOINT = 'xml'
CSV_ENDPOINT = 'csv'
NEWLINE_ENDPOINT = 'line'
BATCH_ENDPOINT = 'batch'

FIELDS = {
    'continent',
    'continentCode',
    'country',
    'countryCode',
    'region',
    'regionName',
    'city',
    'district',
    'zip',
    'lat',
    'lon',
    'timezone',
    'offset',
    'currency',
    'isp',
    'org',
    'as',
    'asname',
    'reverse',
    'mobile',
    'proxy',
    'hosting',
}

SERVICE_FIELDS = {
    'status',
    'message',
    'query',
}

LANGS = {
    'en',
    'de',
    'es',
    'pt-BP',
    'fr',
    'ja',
    'zh-CN',
    'ru',
}

BATCH_SIZE = 100
REQUEST_TIMEOUT = 60

MAX_RATE = sys.maxsize
