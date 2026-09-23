"""Amazon provider — real captured responses from US, UK and DE.

The locale handling is the point of this file. Amazon returns display strings
rather than numbers, formatted per marketplace, and the German format inverts
the meaning of '.' and ','.
"""
import json
import pathlib

import pytest

from app import config
from app.providers.amazon import AmazonProvider, parse_number, to_usd

F = pathlib.Path(__file__).parent / "fixtures"
SEARCH = {s: json.loads((F / f"amazon_search_{s}.json").read_text()) for s in ("US","UK","DE")}
DETAIL = {s: json.loads((F / f"amazon_detail_{s}.json").read_text()) for s in ("US","UK","DE")}


@pytest.fixture(autouse=True)
def rates(monkeypatch):
    monkeypatch.setattr(config, "USD_PER_GBP", 1.27)
    monkeypatch.setattr(config, "USD_PER_EUR", 1.08)


def provider():
    return AmazonProvider(base_url="https://x/v1", token="t",
                          keywords=["usb c cable"], sites=["US","UK","DE"])


# ── the locale trap ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,site,expected", [
    # US / UK: '.' decimal, ',' thousands
    ("$8.99",      "US", 8.99),
    ("£11.99",     "UK", 11.99),
    ("(75,618)",   "US", 75618),
    ("(287)",      "UK", 287),
    # K/M suffixes
    ("(11.9K)",    "US", 11900),
    ("(1.2K)",     "UK", 1200),
    ("(2.5M)",     "US", 2_500_000),
    # DE: ',' decimal, '.' thousands — the inversion
    ("10,99 €",    "DE", 10.99),
    ("229,99€",    "DE", 229.99),
    ("(36.976)",   "DE", 36976),
    ("(20.893)",   "DE", 20893),
    ("(1809)",     "DE", 1809),
    # ratings
    ("4.5 out of 5 stars", "US", 4.5),
    ("4,6 von 5 Sternen",  "DE", 4.6),
    # junk
    ("",           "US", None),
    ("N/A",        "US", None),
    (None,         "US", None),
])
def test_parse_number_is_site_aware(text, site, expected):
    assert parse_number(text, site) == expected


def test_german_thousands_separator_is_not_read_as_a_decimal():
    """The 1000x bug: '36.976' is 36,976 reviews in DE, not 36.976."""
    assert parse_number("(36.976)", "DE") == 36976
    assert parse_number("(36.976)", "US") == 36.976   # same string, other site
    assert parse_number("(36.976)", "DE") != parse_number("(36.976)", "US")


# ── currency ────────────────────────────────────────────────────────────────
def test_converts_each_currency_to_usd():
    assert to_usd(10.0, "USD") == 10.0
    assert to_usd(10.0, "GBP") == 12.7
    assert to_usd(10.0, "EUR") == 10.8


def test_unknown_currency_drops_the_price():
    """An unconverted price is worse than none — margin would read it as USD."""
    assert to_usd(229.0, "JPY") is None
    assert to_usd(229.0, None) is None
    assert to_usd(None, "USD") is None


# ── search parsing, per marketplace ─────────────────────────────────────────
@pytest.mark.parametrize("site", ["US", "UK", "DE"])
def test_parses_every_marketplace(site):
    products = provider().parse_search(SEARCH[site])
    assert products, f"{site} yielded nothing"
    for p in products:
        assert p.source == "amazon"
        assert p.external_id.startswith(f"{site}:")
        assert p.price_usd is None or p.price_usd > 0


def test_asin_is_namespaced_by_site():
    """The same ASIN exists on several marketplaces; without the site in the
    identity, US and DE rows collide on (source, external_id)."""
    us = provider().parse_detail(DETAIL["US"])
    de = provider().parse_detail(DETAIL["DE"])
    assert us.external_id != de.external_id
    assert us.external_id.endswith(de.external_id.split(":")[1])  # same ASIN


def test_german_prices_are_converted_not_taken_at_face_value():
    de = provider().parse_detail(DETAIL["DE"])
    raw = parse_number(DETAIL["DE"]["data"]["data"]["price_text"], "DE")
    assert de.price_usd == round(raw * 1.08, 2)
    assert de.price_usd != raw


def test_prices_are_plausible_across_sites():
    """A locale bug shows up as an absurd number, so bound them."""
    for site in ("US", "UK", "DE"):
        for p in provider().parse_search(SEARCH[site]):
            if p.price_usd is not None:
                assert 0.5 < p.price_usd < 5000, f"{site} {p.external_id}: {p.price_usd}"


def test_ratings_are_within_range():
    for site in ("US", "UK", "DE"):
        for p in provider().parse_search(SEARCH[site]):
            if p.rating is not None:
                assert 0 <= p.rating <= 5, f"{site}: rating {p.rating}"


# ── what Amazon deliberately does not provide ───────────────────────────────
def test_orders_count_is_never_invented():
    """Amazon publishes no sales count. Review count is a popularity proxy,
    not units sold, so substituting it would fabricate demand."""
    for site in ("US", "UK", "DE"):
        for p in provider().parse_search(SEARCH[site]):
            assert p.orders_count is None


def test_cost_is_never_invented():
    for p in provider().parse_search(SEARCH["US"]):
        assert p.cost_usd is None


# ── robustness ──────────────────────────────────────────────────────────────
def test_error_body_returns_empty():
    assert provider().parse_search({"code": "error", "msg": "fail"}) == []


def test_missing_items_key_does_not_raise():
    assert provider().parse_search({"code": "success", "data": {"site": "US"}}) == []


def test_skips_entries_without_asin_or_title():
    body = {"code": "success", "data": {"site": "US", "data": {"items": [
        {"title": "no asin"}, {"asin": "B1"}, "junk",
    ]}}}
    assert provider().parse_search(body) == []


def test_builds_marketplace_specific_url_when_link_absent():
    body = {"code": "success", "data": {"site": "DE", "data": {"items": [
        {"asin": "B09G9FPHY6", "title": "iPad"},
    ]}}}
    [p] = provider().parse_search(body)
    assert p.product_url == "https://www.amazon.de/dp/B09G9FPHY6"


# ── configuration ───────────────────────────────────────────────────────────
def test_requires_token_keywords_and_sites():
    mk = lambda **kw: AmazonProvider(base_url="u", token="t", keywords=["k"], sites=["US"], **kw)
    assert mk().configured is True
    assert AmazonProvider(base_url="u", token="", keywords=["k"], sites=["US"]).configured is False
    assert AmazonProvider(base_url="u", token="t", keywords=[], sites=["US"]).configured is False
    assert AmazonProvider(base_url="u", token="t", keywords=["k"], sites=[]).configured is False
