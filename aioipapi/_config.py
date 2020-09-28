# -*- coding: utf-8 -*-

from pydantic import BaseModel, HttpUrl, conint, confloat


class Config(BaseModel):
    """The configuration of the ip-api.com service

    Some of these parameters can be changed in the future by the service.
    Therefore some of these parameters can be changed by a user if necessary.
    """

    base_url: HttpUrl = 'http://ip-api.com/'
    pro_url: HttpUrl = 'https://pro.ip-api.com/'
    json_endpoint: str = 'json'
    batch_endpoint: str = 'batch'
    batch_size: conint(strict=True, ge=1) = 100
    json_rate_limit: conint(strict=True, ge=1) = 45
    batch_rate_limit: conint(strict=True, ge=1) = 15
    retry_attempts: conint(strict=True, ge=1) = 3
    retry_delay: confloat(strict=True, ge=0.0) = 1.0
    ttl_hold: confloat(strict=True, ge=0.0) = 3.0


config = Config()
