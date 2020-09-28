# -*- coding: utf-8 -*-

import operator

import aioitertools


async def chunker(iterable, chunk_size: int):
    """Asynchronous chunks generator
    """

    aiterable = aioitertools.enumerate(iterable)
    args = [aiterable] * chunk_size

    async for chunk in aioitertools.zip_longest(*args, fillvalue=None):
        chunk = tuple(filter(None, chunk))
        if chunk:
            chunk = tuple([v for _, v in sorted(chunk, key=operator.itemgetter(0))])
            yield chunk
