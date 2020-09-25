# aioipapi

[![PyPI version](https://img.shields.io/pypi/v/aioipapi.svg)](https://pypi.python.org/pypi/aioipapi)
[![Build status](https://travis-ci.org/espdev/aioipapi.svg?branch=master)](https://travis-ci.org/espdev/aioipapi)
[![Coverage Status](https://coveralls.io/repos/github/espdev/aioipapi/badge.svg?branch=master)](https://coveralls.io/github/espdev/aioipapi?branch=master)
![Supported Python versions](https://img.shields.io/pypi/pyversions/aioipapi.svg)
[![License](https://img.shields.io/pypi/l/aioipapi.svg)](LICENSE)

Asynchronous asyncio/aiohttp based client for https://ip-api.com IP geolocation API.

**ip-api.com** is a fast, accurate, reliable API service for IP geolocation, 
free for non-commercial use.

**aioipapi** package provides asynchronous API to use ip-api.com service in free and pro. 
The package features:

- Support JSON API [endpoint](https://ip-api.com/docs/api:json)
- Support Batch JSON API [endpoint](https://ip-api.com/docs/api:batch)
- Acces to [pro service](https://members.ip-api.com/) with API key
- Free API rate limits control
- Customizable retrying when networking problems

**You must not use aioipapi package for commercial purposes without API key.**


## Installing

Use pip for installing:

```
pip install -U aioipapi
```

## Usage Examples

_All examples are provided for Python 3.7 and above._

Use `location` coroutine to locate your own IP:

```python
import asyncio
from aioipapi import location

print(asyncio.run(location()))
```
```
{'status': 'success', 'country': 'United States', 'countryCode': 'US', 'region': 'CA', 'regionName': 'California', 'city': 'Santa Clara', 'zip': '95051', 'lat': 37.3417, 'lon': -121.9753, 'timezone': 'America/Los_Angeles', 'isp': 'DigitalOcean, LLC', 'org': 'Digital Ocean', 'as': 'AS14061 DigitalOcean, LLC', 'query': 'XXX.XX.XXX.XXX'}
```

Use `location` coroutine to locate a domain name:

```python
print(asyncio.run(location('github.com')))
```
```
{'status': 'success', 'country': 'Netherlands', 'countryCode': 'NL', 'region': 'NH', 'regionName': 'North Holland', 'city': 'Amsterdam', 'zip': '1012', 'lat': 52.3667, 'lon': 4.89454, 'timezone': 'Europe/Amsterdam', 'isp': 'GitHub, Inc.', 'org': 'GitHub, Inc.', 'as': 'AS36459 GitHub, Inc.', 'query': '140.82.118.3'}
```

A domain location is supported only in JSON endpoint. Currently, batch JSON endpoint does not support domain names as query. 
In other words, you cannot locate a list of domain names per time. 

Use `location` coroutine to locate an IP with cusomized result fields and language:

```python
print(asyncio.run(location('8.8.8.8', fields=['continent', 'region', 'country'], lang='de')))
```
```
{'status': 'success', 'continent': 'Nordamerika', 'country': 'Vereinigte Staaten', 'region': 'VA', 'query': '8.8.8.8'}
```

Use `location` coroutine to locate a list of IPs:

```python
print(asyncio.run(location(['1.0.0.1', '1.1.1.1', '8.8.4.4', '8.8.8.8'], fields=['lat', 'lon', 'org'])))
```
```
[
  {'status': 'success', 'lat': -27.4766, 'lon': 153.0166, 'org': 'APNIC and Cloudflare DNS Resolver project', 'query': '1.0.0.1'}, 
  {'status': 'success', 'lat': -27.4766, 'lon': 153.0166, 'org': 'APNIC and Cloudflare DNS Resolver project', 'query': '1.1.1.1'}, 
  {'status': 'success', 'lat': 39.03, 'lon': -77.5, 'org': 'Google Public DNS', 'query': '8.8.4.4'}, 
  {'status': 'success', 'lat': 39.03, 'lon': -77.5, 'org': 'Google Public DNS', 'query': '8.8.8.8'}
]
```

You can customize the result fields and lang for each IP in the query list:

```python
ips = [
    '77.88.55.66',
    {'query': '1.1.1.1', 'fields': ['lat', 'lon', 'country'], 'lang': 'de'},
    {'query': '8.8.8.8', 'fields': ['continent', 'country'], 'lang': 'ru'},
]

print(asyncio.run(location(ips, fields=['region', 'isp', 'org'])))
```
```
[
  {'status': 'success', 'region': 'MOW', 'isp': 'Yandex LLC', 'org': 'Yandex enterprise network', 'query': '77.88.55.66'},
  {'status': 'success', 'country': 'Australien', 'lat': -27.4766, 'lon': 153.0166, 'query': '1.1.1.1'}, 
  {'status': 'success', 'continent': 'Северная Америка', 'country': 'США', 'query': '8.8.8.8'}
]
```

In these cases the package uses Batch JSON API endpoint.

Use `location_stream` async generator to locate IPs from an iterable or async iterable:

```python
import asyncio
from aioipapi import location_stream

async def locate():
    async for res in location_stream(['1.0.0.1', '1.1.1.1', '8.8.4.4', '8.8.8.8']):
        print(res)

asyncio.run(locate())
```

`location_stream` also supports `fields` and `lang` options. 
`location_stream` always uses Batch JSON API endpoint.

Use `IpApiClient` class:

```python
import asyncio
from aioipapi import IpApiClient

async def locate():
    async with IpApiClient() as client:
        print(await client.location())

asyncio.run(locate())
```

`IpApiClient` provides `location` and `location_stream` methods similar to the corresponding non-member coroutines.

Use `IpApiClient` class with existing `aiohttp.ClientSession` instead of client own session:

```python
import asyncio
import aiohttp
from aioipapi import IpApiClient

async def locate():
    async with aiohttp.ClientSession() as session:
        async with IpApiClient(session=session) as client:
            print(await client.location())

asyncio.run(locate())
```

Usage of existing session also supported in `location` and `location_stream` non-member coroutines.

If you want to use unlimited pro ip-api service you can use your API key in `location`, `location_stream` functions and `IpApiClient`:

```python

async with IpApiClient(key='your-api-key') as client:
    ...
```

When API key is set, the package always uses HTTPS for connection with ip-api service.

## Free API Rate Limit Control

ip-api service has rate limits in free API (without key). 
Currently, there are 45 requests per minute for JSON endpoint and 15 requests per minute for Batch JSON endpoint.

The package controls the rate limits using `X-Rl` and `X-Ttl` response headers. 
In other words, you should never get 429 HTTP error when using free API.

Let's locate a lot of IPs for example:

```python
import asyncio
import sys
import logging

logging.basicConfig(
    format='[%(levelname)s] - %(message)s',
    level=logging.DEBUG,
    stream=sys.stderr,
)

from aioipapi import location

asyncio.run(location(['8.8.8.8'] * 2000))
```
```
[DEBUG] - BATCH API rate limit: rl=14, ttl=60
[DEBUG] - BATCH API rate limit: rl=13, ttl=59
[DEBUG] - BATCH API rate limit: rl=12, ttl=59
...
[DEBUG] - BATCH API rate limit: rl=2, ttl=58
[DEBUG] - BATCH API rate limit: rl=1, ttl=58
[DEBUG] - BATCH API rate limit: rl=0, ttl=58
[WARNING] - API rate limit is reached. Waiting for 58 seconds by rate limit.
[DEBUG] - BATCH API rate limit: rl=14, ttl=60
[DEBUG] - BATCH API rate limit: rl=13, ttl=59
[DEBUG] - BATCH API rate limit: rl=12, ttl=59
[DEBUG] - BATCH API rate limit: rl=11, ttl=59
[DEBUG] - BATCH API rate limit: rl=10, ttl=59
```

# License

[MIT](https://choosealicense.com/licenses/mit/)
