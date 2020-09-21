# -*- coding: utf-8 -*-

import asyncio
from collections import abc
from ipaddress import IPv4Address, IPv6Address
from http import HTTPStatus
from typing import Optional, Sequence, Set, Union, Type, Iterable, AsyncIterable, AsyncGenerator
from types import TracebackType

from aiohttp import ClientSession, ClientError
import yarl
import aioitertools

from aioipapi._logging import logger
from aioipapi import _constants as constants
from aioipapi._utils import chunker
from aioipapi._exceptions import IpApiError


_IPType = Union[IPv4Address, IPv6Address, str]
_QueryType = Union[_IPType, dict]
_IPsType = Union[Iterable[_QueryType], AsyncIterable[_QueryType]]
_FieldsType = Optional[Union[Sequence[str], Set[str]]]


class IpApiClient:
    """
    """

    def __init__(self,
                 *,
                 fields: _FieldsType = None,
                 lang: Optional[str] = None,
                 key: Optional[str] = None,
                 session: Optional[ClientSession] = None
                 ) -> None:

        if fields and not isinstance(fields, (abc.Sequence, abc.Set)):
            raise TypeError("'fields' argument must be a sequence or set")
        if lang and not isinstance(lang, str):
            raise TypeError(f"'lang' argument must be a string")
        if key and not isinstance(key, str):
            raise TypeError("'key' argument must be a string")
        if session and not isinstance(session, ClientSession):
            raise TypeError(f"'session' argument must be an instance of {ClientSession}")

        self._base_url = yarl.URL(constants.BASE_URL)

        self._fields = fields
        self._lang = lang
        self._key = key

        if session:
            own_session = False
        else:
            session = ClientSession()
            own_session = True

        self._session = session
        self._own_session = own_session

        self._json_rl = constants.JSON_RATE_LIMIT
        self._json_ttl = 0
        self._batch_rl = constants.BATCH_RATE_LIMIT
        self._batch_ttl = 0

    def __enter__(self) -> None:
        raise TypeError("Use 'async with' statement instead")

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> None:
        pass  # pragma: no cover

    async def __aenter__(self) -> 'IpApiClient':
        return self

    async def __aexit__(self,
                        exc_type: Optional[Type[BaseException]],
                        exc_val: Optional[BaseException],
                        exc_tb: Optional[TracebackType]) -> None:
        await self.close()

    async def close(self):
        """Close client and own session
        """

        if self._own_session and self._session:
            await self._session.close()

    async def location(self,
                       ip: Optional[Union[_IPType, _IPsType]] = None,
                       *,
                       fields: _FieldsType = None,
                       lang: Optional[str] = None):
        """Locate IP/domain or a batch of IPs
        """

        batch = False

        if not ip:
            endpoint = constants.JSON_ENDPOINT
        elif isinstance(ip, (str, IPv4Address, IPv6Address)):
            endpoint = f'{constants.JSON_ENDPOINT}/{ip}'
        elif isinstance(ip, (abc.Iterable, abc.AsyncIterable)):
            endpoint = constants.BATCH_ENDPOINT
            batch = True
        else:
            raise TypeError(f"'ip' argument has an invalid type: {type(ip)}")

        if fields and not isinstance(fields, (abc.Sequence, abc.Set)):
            raise TypeError("'fields' argument must be a sequence or set")
        if lang and not isinstance(lang, str):
            raise TypeError(f"'lang' argument must be a string")

        if batch:
            rl = self._batch_rl
            ttl = self._batch_ttl
            data = ip
            method = 'POST'
        else:
            rl = self._json_rl
            ttl = self._json_ttl
            data = None
            method = 'GET'

        if not self._key and rl == 0:
            logger.debug("Waiting for %d seconds by rate limit", ttl)
            await asyncio.sleep(ttl)

        fields = fields or self._fields
        lang = lang or self._lang
        url = self._make_url(endpoint, fields, lang)

        async with self._session.request(method, url, json=data) as resp:
            headers = resp.headers
            rl = int(headers['X-Rl'])
            ttl = int(headers['X-Ttl'])

            if batch:
                self._batch_rl = rl
                self._batch_ttl = ttl
            else:
                self._json_rl = rl
                self._json_ttl = ttl

            assert resp.status == 200, resp.status
            result = await resp.json()

        return result

    async def locator(self,
                      ips: _IPsType,
                      *,
                      fields: _FieldsType = None,
                      lang: Optional[str] = None):
        """Return async generator for IPs location
        """

        if not isinstance(ips, (abc.Iterable, abc.AsyncIterable)):
            raise TypeError("'ips' argument must be an iterable or async iterable")

        if fields and not isinstance(fields, (abc.Sequence, abc.Set)):
            raise TypeError("'fields' argument must be a sequence or set")

        if lang and not isinstance(lang, str):
            raise TypeError(f"'lang' argument must be a string")

        fields = fields or self._fields
        lang = lang or self._lang

        url = self._make_url(constants.BATCH_ENDPOINT, fields, lang)
        batch_size = constants.BATCH_SIZE

        async for ips_batch in chunker(ips, chunk_size=constants.BATCH_SIZE):
            while True:
                # TODO: use tenacity based retrying
                await self._wait_for_rate_limit(self._batch_rl, self._batch_ttl)

                try:
                    async with self._session.post(url, json=ips_batch) as resp:
                        self._batch_rl, self._batch_ttl = self.get_rl_ttl(
                            resp.headers, max_rl=constants.BATCH_RATE_LIMIT)

                        status = resp.status

                        if status == HTTPStatus.OK:
                            results = await resp.json()
                            async for result in aioitertools.iter(results):
                                yield result
                            break
                        elif status == HTTPStatus.TOO_MANY_REQUESTS:
                            logger.error("Too many requests (%d)", status)
                            continue
                        elif status == HTTPStatus.UNPROCESSABLE_ENTITY:
                            raise IpApiError(f"Batch size {batch_size} is too large (HTTP {status})")
                        else:
                            raise IpApiError(f"HTTP {status} error occurred")

                except ClientError as err:
                    raise IpApiError(f"Client connection error: {repr(err)}") from err

    def _make_url(self, endpoint, fields, lang) -> str:
        url = self._base_url / endpoint

        if fields:
            fields = set(fields) | constants.SERVICE_FIELDS
            url %= {'fields': ','.join(fields)}
        if lang:
            url %= {'lang': lang}
        if self._key:
            url = url.with_scheme('https')
            url %= {'key': self._key}

        return url

    async def _wait_for_rate_limit(self, rl, ttl):
        if self._key:
            return
        if rl == 0:
            logger.warning("API limit is reached. Waiting for %d seconds by rate limit.", ttl)
            await asyncio.sleep(ttl)

    @staticmethod
    def get_rl_ttl(headers, max_rl):
        rl = int(headers.get('X-Rl', f'{max_rl}'))
        ttl = int(headers.get('X-Ttl', '0'))

        return rl, ttl


async def main():
    async with IpApiClient(lang='ru') as client:
        async for res in client.locator(['5.18.247.243'] * 5):
            print(res)

if __name__ == '__main__':
    asyncio.run(main())
