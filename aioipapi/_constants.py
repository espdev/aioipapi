# -*- coding: utf-8 -*-

BASE_URL = 'http://ip-api.com/'

JSON_ENDPOINT = 'json'
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
REQUEST_TIMEOUT = 30

JSON_RATE_LIMIT = 45
BATCH_RATE_LIMIT = 15

RETRY_ATTEMPTS = 3
RETRY_DELAY = 1.0

TTL_HOLD = 5
