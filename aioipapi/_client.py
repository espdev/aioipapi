# -*- coding: utf-8 -*-

import asyncio
from collections import abc
from ipaddress import IPv4Address, IPv6Address
from http import HTTPStatus
from typing import Optional, Sequence, Set, List, Dict, Any, Union, Type, Iterable, AsyncIterable
from types import TracebackType

import aiohttp
import aiohttp.helpers
import yarl
import aioitertools
import tenacity

from aioipapi._logging import logger
from aioipapi import _constants as constants
from aioipapi._utils import chunker
from aioipapi._exceptions import ClientError, TooManyRequests, TooLargeBatchSize, AuthError, HttpError


_IPType = Union[IPv4Address, IPv6Address, str]
_QueryType = Union[_IPType, dict]
_IPsType = Union[Iterable[_QueryType], AsyncIterable[_QueryType]]
_FieldsType = Optional[Union[Sequence[str], Set[str]]]


class IpApiClient:
    """IP-API asynchronous http client to perform geo-location

    Asynchronous http client for https://ip-api.com/ web-service.

    """

    def __init__(self,
                 *,
                 fields: _FieldsType = None,
                 lang: Optional[str] = None,
                 key: Optional[str] = None,
                 session: Optional[aiohttp.ClientSession] = None,
                 retry_attempts: int = constants.RETRY_ATTEMPTS,
                 retry_delay: float = constants.RETRY_DELAY,
                 ) -> None:

        if fields and not isinstance(fields, (abc.Sequence, abc.Set)):
            raise TypeError("'fields' argument must be a sequence or set")
        if lang and not isinstance(lang, str):
            raise TypeError(f"'lang' argument must be a string")
        if key and not isinstance(key, str):
            raise TypeError("'key' argument must be a string")
        if session and not isinstance(session, aiohttp.ClientSession):
            raise TypeError(f"'session' argument must be an instance of {aiohttp.ClientSession}")

        if session:
            own_session = False
        else:
            session = aiohttp.ClientSession()
            own_session = True

        self._session = session
        self._own_session = own_session

        self._base_url = yarl.URL(constants.BASE_URL)

        self._fields = fields
        self._lang = lang
        self._key = key

        self._json_rl = constants.JSON_RATE_LIMIT
        self._json_ttl = 0
        self._batch_rl = constants.BATCH_RATE_LIMIT
        self._batch_ttl = 0

        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay

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
                       lang: Optional[str] = None,
                       timeout: Union[aiohttp.ClientTimeout, int, float, object] = aiohttp.helpers.sentinel
                       ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Locate IP/domain or a batch of IPs
        """

        batch = False
        endpoint = None

        if not ip:
            endpoint = constants.JSON_ENDPOINT
        elif isinstance(ip, (str, IPv4Address, IPv6Address)):
            endpoint = f'{constants.JSON_ENDPOINT}/{ip}'
        elif isinstance(ip, (abc.Iterable, abc.AsyncIterable)):
            batch = True
        else:
            raise TypeError(f"'ip' argument has an invalid type: {type(ip)}")

        if fields and not isinstance(fields, (abc.Sequence, abc.Set)):
            raise TypeError("'fields' argument must be a sequence or set")
        if lang and not isinstance(lang, str):
            raise TypeError(f"'lang' argument must be a string")

        if batch:
            return await aioitertools.list(self.locator(
                ip, fields=fields, lang=lang, timeout=timeout))

        fields = fields or self._fields
        lang = lang or self._lang
        url = self._make_url(endpoint, fields, lang)

        return await self._fetch_result(self._fetch_json, url, timeout)

    async def locator(self,
                      ips: _IPsType,
                      *,
                      fields: _FieldsType = None,
                      lang: Optional[str] = None,
                      timeout: Union[aiohttp.ClientTimeout, int, float, object] = aiohttp.helpers.sentinel,
                      ) -> AsyncIterable[Dict[str, Any]]:
        """Async generator for locating IPs from iterable or async iterable

        The method always uses batch API: https://ip-api.com/docs/api:batch

        Parameters:

        :param ips: The iterable or async iterable of IPs or dicts with additional info (see API docs)
        :param fields: The sequence or set of returned fields in the result
        :param lang: The language of the result
        :param timeout: The timeout of the whole request to API
        :return: async generator of results for every IP
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

        async for ips_batch in chunker(ips, chunk_size=constants.BATCH_SIZE):
            results = await self._fetch_result(self._fetch_batch, url, ips_batch, timeout)
            async for result in aioitertools.iter(results):
                yield result

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
            await asyncio.sleep(ttl + constants.TTL_HOLD)

    @staticmethod
    def _get_rl_ttl(headers):
        if 'X-Rl' not in headers or 'X-Ttl' not in headers:
            return None, None

        rl = int(headers['X-Rl'])
        ttl = int(headers['X-Ttl'])

        return rl, ttl

    def _check_http_status(self, resp):
        rl, ttl = self._get_rl_ttl(resp.headers)
        status = resp.status

        if status == HTTPStatus.OK:
            return True, rl, ttl
        elif status == HTTPStatus.TOO_MANY_REQUESTS:
            if self._key:
                raise TooManyRequests("Too many requests with using API key")
            return False, rl, ttl
        elif status == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise TooLargeBatchSize(f"Batch size is too large ({status})")
        elif status == HTTPStatus.FORBIDDEN:
            raise AuthError(f"Forbidden ({status}). Please check your API key")
        else:
            raise HttpError(f"HTTP {status} error occurred", status=status)

    async def _fetch_json(self, url, timeout):
        await self._wait_for_rate_limit(self._json_rl, self._json_ttl)

        async with self._session.get(url, timeout=timeout) as resp:
            is_ok, self._json_rl, self._json_ttl = self._check_http_status(resp)
            if is_ok:
                return await resp.json()
            return None

    async def _fetch_batch(self, url, ips_batch, timeout):
        await self._wait_for_rate_limit(self._batch_rl, self._batch_ttl)

        async with self._session.post(url, json=ips_batch, timeout=timeout) as resp:
            is_ok, self._batch_rl, self._batch_ttl = self._check_http_status(resp)
            if is_ok:
                return await resp.json()
            return None

    async def _fetch_result(self, fetch_coro, *args):
        retrying = tenacity.AsyncRetrying(
            reraise=True,
            retry=tenacity.retry_if_exception_type(ClientError),
            stop=tenacity.stop_after_attempt(self._retry_attempts),
            wait=tenacity.wait_fixed(self._retry_delay)
        )

        async for attempt in retrying:
            with attempt:
                try:
                    while True:  # retrying loop when "too many requests" without API key
                        result = await fetch_coro(*args)
                        if result:
                            return result
                except aiohttp.ClientError as err:
                    raise ClientError(f"Client error: {repr(err)}") from err


async def main():
    async with IpApiClient(lang='ru') as client:
        res = await client.location('5.18.247.243')
        print(res)

        async for res in client.locator(['5.18.247.243'] * 200):
            print(res)
        #     pass

if __name__ == '__main__':
    asyncio.run(main())
