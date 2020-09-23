# -*- coding: utf-8 -*-

import pytest

from aioipapi import IpApiClient


@pytest.mark.asyncio
@pytest.mark.parametrize('query, fields, lang, expected', [
    (None, None, None, {'status': 'success', 'message': 'test_json', 'query': '127.0.0.1'}),
    ('localhost', None, None, {'status': 'success', 'message': 'test_json_query', 'query': 'localhost'}),
    (None, {'lat', 'lon'}, 'ru', {'status': 'success', 'message': 'test_json', 'query': '127.0.0.1', 'lang': 'ru', 'lat': 'test', 'lon': 'test'}),
    ('192.168.0.1', ['isp', 'country'], None, {'status': 'success', 'message': 'test_json_query', 'query': '192.168.0.1', 'country': 'test', 'isp': 'test'}),
    (['192.168.0.1', '192.168.0.2'], None, None, [{'status': 'success', 'message': 'test_batch', 'query': '192.168.0.1'},
                                                  {'status': 'success', 'message': 'test_batch', 'query': '192.168.0.2'}]),
    ([{'query': '192.168.0.1', 'fields': {'lon'}}, '192.168.0.2', {'query': '192.168.0.3', 'lang': 'ru'}], ['lat'], 'de', [{'status': 'success', 'message': 'test_batch', 'query': '192.168.0.1', 'lon': 'test', 'lang': 'de'},
                                                                                                                           {'status': 'success', 'message': 'test_batch', 'query': '192.168.0.2', 'lat': 'test', 'lang': 'de'},
                                                                                                                           {'status': 'success', 'message': 'test_batch', 'query': '192.168.0.3', 'lat': 'test', 'lang': 'ru'}]),
])
async def test_location(query, fields, lang, expected, config_local):
    ipapi_client = IpApiClient(fields=fields, lang=lang)
    res = await ipapi_client.location(query)
    assert res == expected
