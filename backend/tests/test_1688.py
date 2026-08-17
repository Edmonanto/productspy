"""1688 provider: signature scheme, response parsing, price derivation."""
import hashlib
import hmac

from app import config
from app.providers.alibaba1688 import Alibaba1688Provider, _sign
from app.providers.registry import enabled_providers


def provider() -> Alibaba1688Provider:
    return Alibaba1688Provider(
        app_key="key", app_secret="secret",
        namespace="com.alibaba.fenxiao.crossborder",
        api_name="product.search.keywordQuery",
    )


# ── signature ───────────────────────────────────────────────────────────────
def test_signature_is_sha1_not_sha256():
    """1688 uses HMAC-SHA1; copying AliExpress's SHA256 silently fails auth."""
    path = "param2/1/ns/api/key"
    params = {"pageNo": "1"}
    expected = hmac.new(
        b"secret", (path + "pageNo1").encode(), hashlib.sha1
    ).hexdigest().upper()
    assert _sign(path, params, "secret") == expected
    assert len(_sign(path, params, "secret")) == 40  # sha1 hex = 40 chars


def test_signature_includes_url_path():
    """The path is part of the signed string — omitting it is a silent 403."""
    params = {"a": "1"}
    assert _sign("param2/1/ns/api/key", params, "s") != _sign("", params, "s")


def test_signature_is_order_independent_and_uppercase():
    a = _sign("p", {"b": "2", "a": "1"}, "s")
    b = _sign("p", {"a": "1", "b": "2"}, "s")
    assert a == b == a.upper()


def test_url_path_shape():
    assert provider()._url_path() == (
        "param2/1/com.alibaba.fenxiao.crossborder/"
        "product.search.keywordQuery/key"
    )


# ── parsing ─────────────────────────────────────────────────────────────────
def test_parses_offers_and_converts_currency(monkeypatch):
    monkeypatch.setattr(config, "CNY_PER_USD", 7.15)
    monkeypatch.setattr(config, "WHOLESALE_MARKUP", 3.0)

    body = {"result": {"offerList": [{
        "offerId": 987654321,
        "subject": "LED 宠物项圈 可充电",
        "price": "14.30",
        "saleQuantity": "3,200",
        "imageUrl": "https://cbu01.alicdn.com/img/1.jpg",
        "categoryName": "宠物用品",
        "detailUrl": "https://detail.1688.com/offer/987654321.html",
    }]}}

    [p] = provider().parse(body)
    assert p.external_id == "987654321"
    assert p.source == "1688"
    assert p.cost_usd == 2.0            # 14.30 CNY / 7.15
    assert p.price_usd == 6.0           # derived retail at 3x
    assert p.orders_count == 3200       # comma stripped
    assert p.category == "宠物用品"


def test_falls_back_to_price_range_when_no_flat_price(monkeypatch):
    monkeypatch.setattr(config, "CNY_PER_USD", 7.15)
    body = {"result": {"offerList": [{
        "offerId": "1", "subject": "Bulk item",
        "priceRange": [{"price": "7.15"}, {"price": "6.00"}],
    }]}}
    [p] = provider().parse(body)
    assert p.cost_usd == 1.0  # takes the first (lowest-qty) tier


def test_builds_detail_url_when_missing():
    body = {"result": {"offerList": [{"offerId": "555", "subject": "X"}]}}
    [p] = provider().parse(body)
    assert p.product_url == "https://detail.1688.com/offer/555.html"


def test_unwraps_nested_image_objects():
    body = {"result": {"offerList": [{
        "offerId": "1", "subject": "X",
        "imageUrl": {"url": "https://cbu01.alicdn.com/img/a.jpg"},
    }]}}
    assert provider().parse(body)[0].image_url.endswith("a.jpg")


def test_error_body_returns_empty_not_exception():
    """The gateway returns errors with HTTP 200 — must not look like success."""
    assert provider().parse(
        {"errorCode": "400", "errorMessage": "Invalid signature"}
    ) == []


def test_skips_items_missing_id_or_title():
    body = {"result": {"offerList": [
        {"subject": "no id"}, {"offerId": "1"}, "not-a-dict",
    ]}}
    assert provider().parse(body) == []


def test_handles_missing_price_without_crashing():
    body = {"result": {"offerList": [{"offerId": "1", "subject": "X"}]}}
    [p] = provider().parse(body)
    assert p.cost_usd is None and p.price_usd is None


# ── registry wiring ─────────────────────────────────────────────────────────
def test_unconfigured_provider_is_skipped():
    assert Alibaba1688Provider(app_key="", app_secret="").configured is False


def test_registry_enables_1688_when_credentials_present(monkeypatch):
    monkeypatch.setattr(config, "ALIBABA1688_APP_KEY", "k")
    monkeypatch.setattr(config, "ALIBABA1688_APP_SECRET", "s")
    monkeypatch.setattr(config, "ALIEXPRESS_APP_KEY", "")
    monkeypatch.setattr(config, "ALIEXPRESS_APP_SECRET", "")
    monkeypatch.setattr(config, "APIFY_TOKEN", "")
    names = [p.name for p in enabled_providers()]
    assert names == ["1688"]
