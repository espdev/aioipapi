# -*- coding: utf-8 -*-

import pytest

from aioipapi import IpApiClient


@pytest.mark.asyncio
async def test_client_close():
    async with IpApiClient() as client:
        pass
    assert client.closed

    client = IpApiClient()
    await client.close()
    assert client.closed

    with pytest.raises(ValueError):
        await client.location()

    with pytest.raises(ValueError):
        async for _ in client.location_stream(['127.0.0.1']):
            pass


@pytest.mark.asyncio
@pytest.mark.parametrize('query, fields, lang, expected', [
    (None, None, None, {'status': 'success', 'message': 'test_json', 'query': '127.0.0.1'}),
    ('localhost', None, None, {'status': 'success', 'message': 'test_json_query', 'query': 'localhost'}),
    (None, {'lat', 'lon'}, 'ru', {'status': 'success', 'message': 'test_json', 'query': '127.0.0.1', 'lang': 'ru', 'lat': 'test', 'lon': 'test'}),
    ('192.168.0.1', ['isp', 'country'], None, {'status': 'success', 'message': 'test_json_query', 'query': '192.168.0.1', 'country': 'test', 'isp': 'test'}),
    (['192.168.0.1', '192.168.0.2'], None, None, [{'status': 'success', 'message': 'test_batch', 'query': '192.168.0.1'},
                                                  {'status': 'success', 'message': 'test_batch', 'query': '192.168.0.2'}]),
    ([{'query': '192.168.0.1', 'fields': {'lon'}}, '192.168.0.2', {'query': '192.168.0.3', 'lang': 'ru'}], ['lat'], 'de',
     [{'status': 'success', 'message': 'test_batch', 'query': '192.168.0.1', 'lon': 'test', 'lang': 'de'},
      {'status': 'success', 'message': 'test_batch', 'query': '192.168.0.2', 'lat': 'test', 'lang': 'de'},
      {'status': 'success', 'message': 'test_batch', 'query': '192.168.0.3', 'lat': 'test', 'lang': 'ru'}]),
])
async def test_location_local_mock(query, fields, lang, expected, config_local):
    async with IpApiClient(fields=fields, lang=lang) as client:
        res = await client.location(query)
        assert res == expected


sentinel = object()


@pytest.mark.real_service
@pytest.mark.asyncio
@pytest.mark.parametrize('query', [
    sentinel,
    None,
    'google.com',
    'github.com',
    '8.8.8.8',
    ['1.0.0.1', '1.1.1.1', '8.8.4.4'],
])
async def test_location(query):
    fields = ['org', 'lat', 'lon', 'country', 'as']

    async with IpApiClient(fields=fields) as client:
        if query is sentinel:
            result = await client.location()
        else:
            result = await client.location(query)

        if isinstance(result, dict):
            result = [result]

        for res in result:
            assert 'status' in res and res['status'] == 'success'
            assert 'query' in res

            for field in fields:
                assert field in res


@pytest.mark.real_service
@pytest.mark.asyncio
async def test_location_reserved_range():
    async with IpApiClient() as client:
        res = await client.location('127.0.0.1')
        assert 'status' in res and res['status'] == 'fail'
        assert 'message' in res and res['message'] == 'reserved range'


@pytest.mark.real_service
@pytest.mark.asyncio
async def test_location_invalid_query():
    async with IpApiClient() as client:
        res = await client.location('1.2.3.4.5')
        assert 'status' in res and res['status'] == 'fail'
        assert 'message' in res and res['message'] == 'invalid query'


@pytest.mark.real_service
@pytest.mark.asyncio
async def test_location_a_lot_queries():
    ips = ['8.8.8.8'] * 2000
    check_fields = ['org', 'lat', 'lon', 'country', 'as']

    async with IpApiClient() as client:
        async for res in client.location_stream(ips):
            assert 'status' in res and res['status'] == 'success'
            assert 'query' in res

            for field in check_fields:
                assert field in res
