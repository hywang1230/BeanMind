"""外汇局公开中间价客户端。

只负责 HTTP、超时和原始行解析，不写入账本、不依赖仓储。
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SAFE_FX_URL = "http://m.safe.gov.cn/AppStructured/hlw/jsonRmb.do"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_LOOKBACK_DAYS = 10


class SafeFxClient:
    """按日请求外汇局牌价，返回第一个非空 JSON 数组。"""

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def fetch_first_quote_day(
        self,
        start_date: date,
        *,
        max_lookback_days: int = DEFAULT_MAX_LOOKBACK_DAYS,
    ) -> tuple[date, list[Any]] | None:
        for offset in range(max_lookback_days + 1):
            day = start_date - timedelta(days=offset)
            rows = self._fetch_day(day)
            if rows:
                return day, rows
        return None

    def _fetch_day(self, day: date) -> list[Any] | None:
        params = {"date": day.isoformat()}
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
                cookies=httpx.Cookies(),
            ) as client:
                response = client.get(SAFE_FX_URL, params=params)
        except httpx.HTTPError as exc:
            logger.warning("safe_fx date=%s error=%s", day.isoformat(), type(exc).__name__)
            return None

        logger.info("safe_fx date=%s status=%s", day.isoformat(), response.status_code)
        if response.status_code != 200:
            return None
        try:
            payload = json.loads(
                response.content.decode("utf-8"),
                parse_int=Decimal,
                parse_float=Decimal,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return None
        if not isinstance(payload, list) or not payload:
            return None
        return payload
