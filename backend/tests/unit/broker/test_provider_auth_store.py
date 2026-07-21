"""Provider streaming/reconnect, encrypted token store, and the auth flow."""

from __future__ import annotations

import asyncio

import pytest
from app.modules.broker.auth import ZerodhaAuth
from app.modules.broker.provider import ZerodhaProvider
from app.modules.broker.reconnect import BackoffPolicy
from app.modules.broker.token_store import Cipher, MemoryTokenStore
from app.modules.market_data.providers.base import ProviderError
from cryptography.fernet import Fernet

from tests.unit.broker.fakes import FakeKiteHttp, FakeKiteTicker, ticker_builder_for


def _provider(ticker: FakeKiteTicker) -> ZerodhaProvider:
    return ZerodhaProvider(
        FakeKiteHttp(),
        ticker_builder_for(ticker),
        api_key="FAKE",
        backoff=BackoffPolicy(base=0.01, jitter=0.0),
    )


async def test_connect_requires_access_token() -> None:
    p = _provider(FakeKiteTicker())
    with pytest.raises(ProviderError, match="access token"):
        await p.connect()


async def test_stream_yields_normalized_quotes() -> None:
    ticker = FakeKiteTicker()
    p = _provider(ticker)
    p.set_access_token("AT")
    await p.connect()
    assert p.is_connected
    await p.fetch_instruments()
    await p.subscribe(["TCS"])
    assert ticker.subscribed == [2953217]

    ticker.emit_ticks([{"instrument_token": 2953217, "last_price": 101.5, "volume_traded": 5}])
    quote = await asyncio.wait_for(p.stream().__anext__(), timeout=1.0)
    assert quote.symbol == "TCS" and float(quote.ltp) == 101.5


async def test_historical_and_health() -> None:
    ticker = FakeKiteTicker()
    p = _provider(ticker)
    p.set_access_token("AT")
    await p.connect()
    candles = await p.fetch_historical_candles("TCS", "1d", _dt(1), _dt(3))
    assert len(candles) == 1 and float(candles[0].close) == 101.0
    assert await p.health_check() is True


async def test_reconnect_on_drop_uses_backoff() -> None:
    ticker = FakeKiteTicker()
    p = _provider(ticker)
    p.set_access_token("AT")
    await p.connect()
    assert p._state.total_reconnects == 1
    ticker.emit_close()  # simulate a disconnect
    await asyncio.sleep(0.05)  # allow the scheduled backoff reconnect to fire
    assert p._state.total_reconnects >= 2


def test_cipher_roundtrip_and_wrong_key() -> None:
    key = Fernet.generate_key().decode()
    cipher = Cipher(key)
    token = cipher.encrypt("secret-access-token")
    assert token != "secret-access-token"
    assert cipher.decrypt(token) == "secret-access-token"
    other = Cipher(Fernet.generate_key().decode())
    with pytest.raises(ValueError, match="decrypt"):
        other.decrypt(token)


def test_cipher_rejects_bad_key() -> None:
    with pytest.raises(ValueError, match="Fernet key"):
        Cipher("not-a-valid-key")


async def test_auth_flow_stores_encrypted_session() -> None:
    http = FakeKiteHttp()
    store = MemoryTokenStore()
    auth = ZerodhaAuth(http, api_secret="SECRET", store=store)
    assert auth.login_url().startswith("https://kite.zerodha.com/connect/login")

    session = await auth.complete_login("REQ123")
    assert session.access_token == "ACCESS-REQ123"
    assert session.kite_user_id == "AB1234"
    assert http.access_token == "ACCESS-REQ123"  # attached for subsequent calls

    current = await auth.current_session()
    assert current is not None and current.is_valid
    await auth.logout()
    assert await auth.current_session() is None


async def test_auth_rejects_missing_token() -> None:
    auth = ZerodhaAuth(FakeKiteHttp(), api_secret="S", store=MemoryTokenStore())
    with pytest.raises(ValueError, match="access_token"):
        await auth.complete_login("bad")  # fake returns {} for "bad"


def _dt(day: int):  # type: ignore[no-untyped-def]
    from datetime import UTC, datetime

    return datetime(2025, 1, day, tzinfo=UTC)
