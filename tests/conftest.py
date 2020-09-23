# -*- coding: utf-8 -*-

import asyncio

import pytest
from aiohttp.test_utils import TestServer, TestClient
from aiohttp import web

from aioipapi import config


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


def update_data(data, request_query):
    if 'fields' in request_query:
        fields = request_query['fields'].split(',')
        for field in fields:
            data[field] = 'test'
    if 'lang' in request_query:
        data['lang'] = request_query['lang']


async def get_json(request):
    data = {}
    update_data(data, request.query)
    data.update({'status': 'success', 'message': 'test_json', 'query': '127.0.0.1'})

    return web.json_response(data=data)


async def get_json_query(request):
    data = {}
    update_data(data, request.query)
    query = request.match_info['query']
    data.update({'status': 'success', 'message': 'test_json_query', 'query': query})

    return web.json_response(data=data)


async def post_batch(request):
    data = []
    json_data = await request.json()

    for item in json_data:
        item_data = {}

        if isinstance(item, str):
            query = item
            update_data(item_data, request.query)
        else:
            query = item['query']
            if 'fields' not in item and 'fields' in request.query:
                item['fields'] = request.query['fields']
            if 'lang' not in item and 'lang' in request.query:
                item['lang'] = request.query['lang']
            update_data(item_data, item)

        item_data.update({'status': 'success', 'message': 'test_batch', 'query': query})
        data.append(item_data)

    return web.json_response(data=data)


@pytest.fixture(scope='session')
async def ipapi_server():
    app = web.Application()

    app.router.add_get('/json', get_json)
    app.router.add_get('/json/{query}', get_json_query)
    app.router.add_post('/batch', post_batch)

    server = TestServer(app)

    await server.start_server()
    yield server
    await server.close()


@pytest.fixture(scope='session')
async def client_session(ipapi_server):
    client = TestClient(ipapi_server)
    yield client.session
    await client.close()


@pytest.fixture
async def config_local(ipapi_server):
    base_url = config.base_url
    config.base_url = str(ipapi_server.make_url(''))
    yield config
    config.base_url = base_url
