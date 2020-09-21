# -*- coding: utf-8 -*-

from collections import abc

import aioitertools


async def chunker(iterable, chunk_size: int):
    """Asynchronous chunks generator
    """

    if not isinstance(iterable, abc.AsyncIterable):
        aiterable = aioitertools.iter(iterable)
    else:
        aiterable = iterable

    args = [aiterable] * chunk_size

    async for chunk in aioitertools.zip_longest(*args, fillvalue=None):
        chunk = tuple(filter(None, chunk))
        if chunk:
            yield chunk
