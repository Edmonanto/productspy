"""Unit economics — known test cases (backend/app/winners/economics.py, mirrored in src/lib/profit.ts)."""
from app.winners.economics import Inputs, compute, cpa_sensitivity, for_product, price_sensitivity, scenarios


def test_known_case():
    # $40 price, $8 cost, $5 shipping, $0.50 packaging, 3% + $0.30 fees, 5% returns, $12 CPA
    r = compute(Inputs(price_usd=40, product_cost_usd=8, cpa_usd=12))
    assert r.complete
    assert r.fees_usd == 1.5                       # 1.20 + 0.30
    assert r.returns_usd == 2.0
    assert r.variable_costs_usd == 17.0            # 8 + 5 + 0.5 + 1.5 + 2
    assert r.gross_profit_usd == 32.0
    assert r.contribution_before_ads_usd == 23.0
    assert r.contribution_margin_pct == 57.5
    assert r.break_even_cpa_usd == 23.0
    assert r.break_even_roas == round(40 / 23, 2)  # 1.74
    assert r.contribution_after_ads_usd == 11.0
    assert r.margin_after_ads_pct == 27.5
    assert r.roas_at_cpa == round(40 / 12, 2)
    assert r.markup == 5.0


def test_missing_inputs_are_incomplete_not_guessed():
    r = compute(Inputs(price_usd=30))
    assert not r.complete and "product cost" in r.missing
    assert r.contribution_before_ads_usd is None
    r2 = compute(Inputs(price_usd=30, product_cost_usd=5))
    assert r2.complete and r2.contribution_after_ads_usd is None
    assert "ad cost per order (CPA)" in r2.missing


def test_no_room_for_ads():
    r = compute(Inputs(price_usd=10, product_cost_usd=8))
    assert r.contribution_before_ads_usd < 0
    assert r.break_even_roas is None and r.break_even_cpa_usd == 0


def test_scenarios_order():
    s = scenarios(Inputs(price_usd=40, product_cost_usd=8, cpa_usd=12))
    c, b, o = (s[k]["contribution_after_ads_usd"] for k in ("conservative", "base", "optimistic"))
    assert c < b < o and b == 11.0


def test_sensitivity_tables():
    i = Inputs(price_usd=40, product_cost_usd=8)
    rows = cpa_sensitivity(i)
    assert any(r["cpa_usd"] == 23.0 and r["contribution_after_ads_usd"] == 0 for r in rows)
    prices = price_sensitivity(i)
    assert [p["price_usd"] for p in prices] == [32.0, 36.0, 40.0, 44.0, 48.0]
    assert prices[0]["contribution_before_ads_usd"] < prices[-1]["contribution_before_ads_usd"]


def test_for_product_defaults():
    assert for_product(None, 5).complete is False
    assert for_product(30, 6).contribution_before_ads_usd == round(30 - 6 - 5 - 0.5 - 1.2 - 1.5, 2)
