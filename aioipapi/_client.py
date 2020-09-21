# -*- coding: utf-8 -*-

import asyncio
from collections import abc
from ipaddress import IPv4Address, IPv6Address
from typing import Optional, Sequence, Set, Union, Type, Iterable, AsyncIterable, AsyncGenerator
from types import TracebackType

from aiohttp import ClientSession
import yarl

from aioipapi import _constants as constants
from aioipapi._logging import logger


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

        self._x_rl = constants.MAX_RATE
        self._x_ttl = 0

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

        if not self._key and self._x_rl == 0:
            logger.debug("Waiting for %d seconds by rate limit", self._x_ttl)
            await asyncio.sleep(self._x_ttl)

        fields = fields or self._fields
        lang = lang or self._lang
        url = self._make_url(endpoint, fields, lang, self._key)

        if batch:
            data = ip
            method = 'POST'
        else:
            data = None
            method = 'GET'

        async with self._session.request(method, url, json=data) as resp:
            assert resp.status == 200, resp.status
            result = await resp.json()

        return result

    async def locator(self, ips: _IPsType):
        """Return async generator for locating IPs
        """

        raise NotImplementedError

    def _make_url(self, endpoint, fields, lang, key) -> str:
        url = self._base_url / endpoint

        if fields:
            fields = set(fields) | constants.SERVICE_FIELDS
            url %= {'fields': ','.join(fields)}
        if lang:
            url %= {'lang': lang}
        if key:
            url = url.with_scheme('https')
            url %= {'key': key}

        return url


async def main():
    async with IpApiClient(lang='ru') as client:
        res = await client.location()

    print(res)

if __name__ == '__main__':
    asyncio.run(main())
