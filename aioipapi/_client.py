# -*- coding: utf-8 -*-

import asyncio
from collections import abc
from ipaddress import IPv4Address, IPv6Address
from http import HTTPStatus
from typing import Optional, Sequence, Set, List, Dict, Any, Union, Type, Iterable, AsyncIterable
from types import TracebackType

from pydantic import BaseModel, Field, ValidationError, validator
import aiohttp
import aiohttp.helpers
import yarl
import aioitertools
import tenacity

from aioipapi._logging import logger
from aioipapi import _constants as constants
from aioipapi._config import config
from aioipapi._utils import chunker
from aioipapi._exceptions import ClientError, HttpError, TooManyRequests, TooLargeBatchSize, AuthError


_IPType = Union[str, IPv4Address, IPv6Address]
_QueryType = Union[_IPType, Dict[str, str]]
_IPsType = Union[Iterable[_QueryType], AsyncIterable[_QueryType]]
_FieldsType = Optional[Union[Sequence[str], Set[str]]]
_TimeoutType = Union[aiohttp.ClientTimeout, int, float, object]


class _IpAddr(BaseModel):
    """IP address validation model
    """

    v: Union[IPv4Address, IPv6Address]


class _Fields(BaseModel):
    """Fields validation model
    """

    v: Union[Sequence[str], Set[str]]


class _QueryInfo(BaseModel):
    """Validation model for IPs query with additional info
    """

    query: str
    fields_: Optional[str] = Field(alias='fields')
    lang: Optional[str]

    class Config:
        extra = 'forbid'

    @validator('query', pre=True)
    def query_validator(cls, v):
        try:
            _IpAddr(v=v)
        except ValidationError as err:
            raise ValueError(f"IP address '{v}' is invalid: {err}") from err
        return str(v)

    @validator('fields_', pre=True)
    def fields_validator(cls, v):
        try:
            _Fields(v=v)
        except ValidationError:
            raise ValueError(f"'fields' must be a sequence or set of strings")
        fields = set(v)
        supported_fields = constants.FIELDS | constants.SERVICE_FIELDS
        if not fields.issubset(supported_fields):
            logger.warning("%s field set is not a subset of supported field set %s",
                           fields, supported_fields)
        return ','.join(fields | constants.SERVICE_FIELDS)

    @validator('lang', pre=True)
    def lang_validator(cls, v):
        if not isinstance(v, str):
            raise ValueError("'lang' must be a string")
        if v not in constants.LANGS:
            logger.warning("'%s' lang is not in supported language set: %s",
                           v, constants.LANGS)
        return v


class IpApiClient:
    """IP-API asynchronous http client to perform geo-location

    Asynchronous http client for https://ip-api.com/ geo-location web-service.

    :param fields: The sequence or set of returned fields in the result
    :param lang: The language of the result
    :param key: The API key for pro unlimited access
    :param session: Existing aiohttp.ClientSession istance
    :param retry_attempts: The number of attempts of fetch result from the service
    :param retry_delay: The delay in seconds between retry attempts

    """

    def __init__(self,
                 *,
                 fields: _FieldsType = None,
                 lang: Optional[str] = None,
                 key: Optional[str] = None,
                 session: Optional[aiohttp.ClientSession] = None,
                 retry_attempts: Optional[int] = None,
                 retry_delay: Optional[float] = None,
                 ) -> None:

        if fields and not isinstance(fields, (abc.Sequence, abc.Set)):
            raise TypeError("'fields' argument must be a sequence or set")
        if lang and not isinstance(lang, str):
            raise TypeError(f"'lang' argument must be a string")
        if key and not isinstance(key, str):
            raise TypeError("'key' argument must be a string")
        if session and not isinstance(session, aiohttp.ClientSession):
            raise TypeError(f"'session' argument must be an instance of {aiohttp.ClientSession}")

        if retry_attempts is None:
            retry_attempts = config.retry_attempts
        if retry_delay is None:
            retry_delay = config.retry_delay

        if session:
            own_session = False
        else:
            session = aiohttp.ClientSession()
            own_session = True

        self._session: Optional[aiohttp.ClientSession] = session
        self._own_session = own_session

        self._base_url = yarl.URL(config.base_url)

        self._fields = fields
        self._lang = lang
        self._key = key

        self._json_rl = config.json_rate_limit
        self._json_ttl = 0
        self._batch_rl = config.batch_rate_limit
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

    @property
    def closed(self) -> bool:
        """Returns True if the client is closed
        """
        return self._session is None

    async def close(self):
        """Close client and own session
        """

        if self._own_session and not self.closed:
            await self._session.close()
        self._session = None

    async def location(self,
                       ip: Optional[Union[_IPType, _IPsType]] = None,
                       *,
                       fields: _FieldsType = None,
                       lang: Optional[str] = None,
                       timeout: _TimeoutType = aiohttp.helpers.sentinel
                       ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Locate IP/domain or a batch of IPs

        :param ip: None or IP/domain or iterable or async iterable of IPs or dicts with additional info (see API docs)
        :param fields: The sequence or set of returned fields in the result
        :param lang: The language of the result
        :param timeout: The timeout of the whole request to the service
        :return: The dict with result for None/IP/domain or the list of dictionaries for IPs
        """

        if self.closed:
            raise ValueError('The client session is already closed')

        batch = False
        endpoint = None

        if not ip:
            endpoint = config.json_endpoint
        elif isinstance(ip, (str, IPv4Address, IPv6Address)):
            endpoint = f'{config.json_endpoint}/{ip}'
        elif isinstance(ip, (abc.Iterable, abc.AsyncIterable)):
            batch = True
        else:
            raise TypeError(f"'ip' argument has an invalid type: {type(ip)}")

        if fields and not isinstance(fields, (abc.Sequence, abc.Set)):
            raise TypeError("'fields' argument must be a sequence or set")
        if lang and not isinstance(lang, str):
            raise TypeError(f"'lang' argument must be a string")

        if batch:
            return await aioitertools.list(self.location_stream(
                ips=ip,
                fields=fields,
                lang=lang,
                timeout=timeout
            ))

        fields = fields or self._fields
        lang = lang or self._lang

        url = self._make_url(endpoint, fields, lang)

        return await self._fetch_result(self._fetch_json, url, timeout)

    async def location_stream(self,
                              ips: _IPsType,
                              *,
                              fields: _FieldsType = None,
                              lang: Optional[str] = None,
                              timeout: _TimeoutType = aiohttp.helpers.sentinel
                              ) -> AsyncIterable[Dict[str, Any]]:
        """Returns async generator for locating IPs from iterable or async iterable

        The method always uses batch API: https://ip-api.com/docs/api:batch

        Parameters:

        :param ips: The iterable or async iterable of IPs or dicts with additional info (see API docs)
        :param fields: The sequence or set of returned fields in the result
        :param lang: The language of the result
        :param timeout: The timeout of the whole request to API
        :return: async generator of results for every IP
        """

        if self.closed:
            raise ValueError('The client session is already closed')

        if not isinstance(ips, (abc.Iterable, abc.AsyncIterable)):
            raise TypeError("'ips' argument must be an iterable or async iterable")
        if fields and not isinstance(fields, (abc.Sequence, abc.Set)):
            raise TypeError("'fields' argument must be a sequence or set")
        if lang and not isinstance(lang, str):
            raise TypeError(f"'lang' argument must be a string")

        fields = fields or self._fields
        lang = lang or self._lang

        url = self._make_url(config.batch_endpoint, fields, lang)

        async for ips_batch in chunker(ips, chunk_size=config.batch_size):
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
            ttl += config.ttl_hold
            logger.warning("API rate limit is reached. Waiting for %d seconds by rate limit...", ttl)
            await asyncio.sleep(ttl)

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
                raise TooManyRequests(
                    f"(HTTP {status}) Too many requests with using API key", status=status)
            return False, rl, ttl
        elif status == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise TooLargeBatchSize(
                f"(HTTP {status}) Batch size is too large", status=status)
        elif status == HTTPStatus.FORBIDDEN:
            raise AuthError(
                f"(HTTP {status}) Forbidden. Please check your API key", status=status)
        else:
            raise HttpError(
                f"HTTP {status} error occurred", status=status)

    async def _fetch_json(self, url, timeout):
        await self._wait_for_rate_limit(self._json_rl, self._json_ttl)

        async with self._session.get(url, timeout=timeout) as resp:
            is_ok, self._json_rl, self._json_ttl = self._check_http_status(resp)
            if not self._key:
                logger.debug("JSON API rate limit: rl=%d, ttl=%d", self._json_rl, self._json_ttl)
            if is_ok:
                return await resp.json()
            logger.debug("JSON API rate limit is reached")
            return None

    async def _fetch_batch(self, url, ips_batch, timeout):
        ips_batch = list(ips_batch)

        for i, ip in enumerate(ips_batch):
            try:
                if isinstance(ip, abc.Mapping):
                    ips_batch[i] = _QueryInfo(**ip).dict(by_alias=True, exclude_none=True)
                else:
                    _IpAddr(v=ip)
            except ValidationError as err:
                raise ValueError(f"Invalid query {ip}: {err}") from err

        await self._wait_for_rate_limit(self._batch_rl, self._batch_ttl)

        async with self._session.post(url, json=ips_batch, timeout=timeout) as resp:
            is_ok, self._batch_rl, self._batch_ttl = self._check_http_status(resp)
            if not self._key:
                logger.debug("BATCH API rate limit: rl=%d, ttl=%d", self._batch_rl, self._batch_ttl)
            if is_ok:
                return await resp.json()
            logger.debug("BATCH API rate limit is reached")
            return None

    async def _fetch_result(self, fetch_coro, *coro_args):
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
                        result = await fetch_coro(*coro_args)
                        if result:
                            return result
                except aiohttp.ClientError as err:
                    raise ClientError(f"Client error: {repr(err)}") from err


async def location(ip: Optional[Union[_IPType, _IPsType]] = None,
                   *,
                   fields: _FieldsType = None,
                   lang: Optional[str] = None,
                   key: Optional[str] = None,
                   session: Optional[aiohttp.ClientSession] = None,
                   timeout: _TimeoutType = aiohttp.helpers.sentinel,
                   retry_attempts: Optional[int] = None,
                   retry_delay: Optional[float] = None,
                   ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Locate IP/domain or batch of IPs

    The shortcut function to get geo-location of IP/domain/IPs.

    Parameters:

    :param ip: None or IP/domain or iterable or async iterable of IPs or dicts with additional info (see API docs)
    :param fields: The sequence or set of returned fields in the result
    :param lang: The language of the result
    :param key: The API key for pro unlimited access
    :param session: Existing aiohttp.ClientSession istance
    :param timeout: The timeout of the whole request to the service
    :param retry_attempts: The number of attempts of fetch result from the service
    :param retry_delay: The delay in seconds between retry attempts
    :return: The dict with result for None/IP/domain or the list of dictionaries for IPs

    """

    client = IpApiClient(
        fields=fields,
        lang=lang,
        key=key,
        session=session,
        retry_attempts=retry_attempts,
        retry_delay=retry_delay
    )

    try:
        result = await client.location(ip, timeout=timeout)
    finally:
        await client.close()

    return result


async def location_stream(ips: _IPsType,
                          *,
                          fields: _FieldsType = None,
                          lang: Optional[str] = None,
                          key: Optional[str] = None,
                          session: Optional[aiohttp.ClientSession] = None,
                          timeout: _TimeoutType = aiohttp.helpers.sentinel,
                          retry_attempts: Optional[int] = None,
                          retry_delay: Optional[float] = None
                          ) -> AsyncIterable[Dict[str, Any]]:
    """Returns async generator for locating IPs from iterable or async iterable

    The shortcut function to get geo-location of batch of IPs in streaming manner.

    Parameters:

    :param ips: The iterable or async iterable of IPs or dicts with additional info (see API docs)
    :param fields: The sequence or set of returned fields in the result
    :param lang: The language of the result
    :param key: The API key for pro unlimited access
    :param session: Existing aiohttp.ClientSession istance
    :param timeout: The timeout of the whole request to the service
    :param retry_attempts: The number of attempts of fetch result from the service
    :param retry_delay: The delay in seconds between retry attempts
    :return: Async generator for locating IPs

    """

    client = IpApiClient(
        fields=fields,
        lang=lang,
        key=key,
        session=session,
        retry_attempts=retry_attempts,
        retry_delay=retry_delay
    )

    try:
        async for result in client.location_stream(ips, timeout=timeout):
            yield result
    finally:
        await client.close()
