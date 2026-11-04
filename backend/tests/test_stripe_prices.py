"""Stripe checkout survives an archived or replaced price."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import config
from app.billing import stripe_provider as sp


class FakeStripe:
    def __init__(self, active_ids, lookup_hit=None, price_meta=None, amount=6999):
        self.active = set(active_ids)
        self.lookup_hit, self.sessions, self.modified = lookup_hit, [], []
        self.price_meta = {"productspy_plan": "pro"} if price_meta is None else price_meta
        self.amount = amount
        outer = self

        class Session:
            @staticmethod
            def create(**params):
                pid = params["line_items"][0]["price"]
                outer.sessions.append(pid)
                if pid not in outer.active:
                    raise Exception("The price specified is inactive. This field only accepts active prices.")
                return SimpleNamespace(url=f"https://checkout.stripe/{pid}")

        class Price:
            @staticmethod
            def list(lookup_keys, active, limit):
                assert lookup_keys == ["productspy_pro_monthly_6999"]
                return SimpleNamespace(data=[SimpleNamespace(id=outer.lookup_hit)] if outer.lookup_hit else [])

            @staticmethod
            def retrieve(pid):
                return {"id": pid, "metadata": outer.price_meta, "unit_amount": outer.amount, "product": "prod_1"}

            @staticmethod
            def modify(pid, active):
                outer.modified.append(("price", pid))
                outer.active.add(pid)

        class Product:
            @staticmethod
            def modify(pid, active):
                outer.modified.append(("product", pid))

        self.checkout = SimpleNamespace(Session=Session)
        self.Price, self.Product = Price, Product


@pytest.fixture(autouse=True)
def _cfg(monkeypatch):
    monkeypatch.setitem(config.STRIPE_PRICE_IDS, "pro", "price_OLD")


def _use(monkeypatch, fake):
    monkeypatch.setattr(sp, "_client", lambda: fake)
    return fake


async def test_uses_the_active_price_with_our_lookup_key(monkeypatch):
    f = _use(monkeypatch, FakeStripe({"price_NEW"}, lookup_hit="price_NEW"))
    assert await sp.create_checkout("u", "a@b.c", "pro", None) == "https://checkout.stripe/price_NEW"
    assert f.sessions == ["price_OLD", "price_NEW"] and f.modified == []


async def test_reactivates_our_archived_price(monkeypatch):
    f = _use(monkeypatch, FakeStripe(set()))
    assert await sp.create_checkout("u", "a@b.c", "pro", None) == "https://checkout.stripe/price_OLD"
    assert ("price", "price_OLD") in f.modified and ("product", "prod_1") in f.modified


async def test_never_reactivates_a_price_that_isnt_this_plan(monkeypatch):
    for fake in (FakeStripe(set(), price_meta={}), FakeStripe(set(), amount=4900)):
        f = _use(monkeypatch, fake)
        with pytest.raises(HTTPException) as e:
            await sp.create_checkout("u", "a@b.c", "pro", None)
        assert e.value.status_code == 502 and "PayPal" in e.value.detail and f.modified == []


async def test_working_price_is_used_directly(monkeypatch):
    f = _use(monkeypatch, FakeStripe({"price_OLD"}))
    assert await sp.create_checkout("u", "", "pro", None) == "https://checkout.stripe/price_OLD"
    assert f.sessions == ["price_OLD"]
