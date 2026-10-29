"""Payment setup command: .env writing, PayPal plan bodies, Stripe idempotency (fake SDK)."""
import sys
import types

from app import config
from app.billing import setup


def test_env_writer_updates_in_place(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=x\nSTRIPE_PRICE_PRO=old\n# comment\n")
    monkeypatch.setattr(setup, "ENV", env)
    setup.write_env({"STRIPE_PRICE_PRO": "price_new", "PAYPAL_WEBHOOK_ID": "WH-1"})
    text = env.read_text()
    assert "DATABASE_URL=x" in text and "STRIPE_PRICE_PRO=price_new" in text and "old" not in text
    assert text.count("PAYPAL_WEBHOOK_ID=WH-1") == 1 and "# comment" in text
    assert setup.read_env()["PAYPAL_WEBHOOK_ID"] == "WH-1"
    assert setup.mask("sk_live_1234567890abcdef") == "sk_live_…cdef"


def test_paypal_partner_plan_bills_month_one_at_minus_25():
    regular = setup._plan_body("PROD-1", "starter", partner=False)
    partner = setup._plan_body("PROD-1", "starter", partner=True)
    assert regular["billing_cycles"][0]["pricing_scheme"]["fixed_price"]["value"] == "29.00"
    first, rest = partner["billing_cycles"]
    assert first["tenure_type"] == "TRIAL" and first["total_cycles"] == 1
    assert first["pricing_scheme"]["fixed_price"]["value"] == "21.75"
    assert rest["sequence"] == 2 and rest["pricing_scheme"]["fixed_price"]["value"] == "29.00"
    assert "partner" in partner["name"] and partner["name"] != regular["name"]


def test_stripe_setup_reuses_existing_objects(monkeypatch):
    created = []

    class Obj(dict):
        __getattr__ = dict.get

    class Lst:
        def __init__(self, data): self.data = data

    existing_prices = {}

    class Price:
        @staticmethod
        def list(lookup_keys, active, limit):
            return Lst([existing_prices[k] for k in lookup_keys if k in existing_prices])

        @staticmethod
        def create(**kw):
            p = Obj(id=f"price_{kw['lookup_key']}", **kw)
            existing_prices[kw["lookup_key"]] = p
            created.append("price")
            return p

    class Product:
        @staticmethod
        def create(**kw):
            created.append("product")
            return Obj(id="prod_1")

    hooks = []

    class WebhookEndpoint:
        @staticmethod
        def list(limit): return Lst(hooks)
        @staticmethod
        def create(**kw):
            h = Obj(id="we_1", secret="whsec_abc", **kw); hooks.append(h); created.append("hook"); return h
        @staticmethod
        def modify(i, **kw): created.append("hook-mod")
        @staticmethod
        def delete(i): hooks.clear()

    class Configuration:
        @staticmethod
        def list(limit): return Lst([Obj(active=True)] if "portal" in created else [])
        @staticmethod
        def create(**kw): created.append("portal")

    fake = types.SimpleNamespace(Price=Price, Product=Product, WebhookEndpoint=WebhookEndpoint,
                                 billing_portal=types.SimpleNamespace(Configuration=Configuration), api_key=None)
    monkeypatch.setitem(sys.modules, "stripe", fake)
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "")
    out = setup.setup_stripe()
    assert out["STRIPE_PRICE_STARTER"] == "price_productspy_starter_monthly_2900"
    assert out["STRIPE_WEBHOOK_SECRET"] == "whsec_abc"
    assert created.count("price") == 3 and "portal" in created
    created.clear()
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "whsec_abc")
    out2 = setup.setup_stripe()                          # second run: nothing new
    assert "price" not in created and "hook" not in created and "STRIPE_WEBHOOK_SECRET" not in out2
