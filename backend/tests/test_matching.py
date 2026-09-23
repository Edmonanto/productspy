"""Cross-platform matching v1.

Most of these assert what the matcher *refuses* to do. A wrong match reports
a confident margin on a pairing that doesn't exist, and a subscriber could
order against it — so under-claiming is the design goal, not a limitation.
"""
import pytest

from app.matching import matcher
from app.matching.matcher import (
    CANDIDATE_FLOOR, CONFIRM_THRESHOLD, V1_CONFIDENCE_CAP,
    jaccard, price_ratio_score, score_pair, tokenize,
)

# A realistic pair: a TikTok listing and the translated 1688 supplier title.
RETAIL = "Cute Fuzzy Plush Pet Tunnel Bed with Ball for Cats"
SUPPLIER_EN = "plush pet tunnel bed cat cave with hanging ball"


# ── the safety property ─────────────────────────────────────────────────────
def test_v1_can_never_auto_confirm():
    """Auto-confirm needs image evidence, which v1 does not have. The cap makes
    that structural, so no amount of title overlap can silently change margin."""
    assert V1_CONFIDENCE_CAP < CONFIRM_THRESHOLD

    result = score_pair(RETAIL, RETAIL, 30.0, 8.0)  # identical titles
    assert result.confidence <= V1_CONFIDENCE_CAP
    assert result.status == "candidate"
    assert result.status != "confirmed"


def test_every_plausible_match_is_a_candidate_not_a_fact():
    result = score_pair(RETAIL, SUPPLIER_EN, 31.19, 6.72)
    assert result.confidence >= CANDIDATE_FLOOR
    assert result.status == "candidate"


# ── price ratio is a veto, never evidence ───────────────────────────────────
@pytest.mark.parametrize("retail,cost", [
    (100.0, 1.0),    # 100x — not the same product
    (10.0, 9.5),     # 1.05x — no dropship margin exists here
    (0.0, 5.0),
    (30.0, 0.0),
    (None, 5.0),
    (30.0, None),
])
def test_implausible_price_ratio_vetoes_the_match(retail, cost):
    """Even with perfectly matching titles."""
    result = score_pair(RETAIL, RETAIL, retail, cost)
    assert result.confidence == 0.0
    assert result.status == "rejected"


def test_price_alone_never_produces_a_match():
    """A perfect 3x ratio with unrelated titles must score nothing."""
    result = score_pair("Wireless Bluetooth Earbuds", "stainless steel cookware", 30.0, 10.0)
    assert result.confidence == 0.0


def test_price_score_peaks_in_the_dropship_band():
    assert price_ratio_score(30.0, 10.0) == 1.0     # 3x
    assert price_ratio_score(60.0, 10.0) == 1.0     # 6x
    edge = price_ratio_score(160.0, 10.0)           # 16x -> vetoed
    assert edge is None
    tapering = price_ratio_score(120.0, 10.0)       # 12x -> weak but allowed
    assert 0.0 < tapering < 1.0


# ── shared tokens must be distinctive ───────────────────────────────────────
def test_generic_overlap_is_not_a_match():
    """'pet' and 'bed' appear on thousands of listings."""
    result = score_pair("Premium Pet Bed for Sale", "new pet bed free shipping", 30.0, 8.0)
    assert result.confidence == 0.0
    assert result.status == "rejected"
    assert result.evidence.get("reason")   # rejection is always explained


def test_single_shared_token_is_rejected():
    result = score_pair("Cat Tunnel Toy", "dog leash cat", 30.0, 8.0)
    assert result.confidence == 0.0


def test_stopwords_are_stripped():
    tokens = tokenize("The Premium New Hot Sale Best Quality Cat Tunnel Bed")
    assert "cat" in tokens and "tunnel" in tokens
    for noise in ("the", "premium", "new", "hot", "sale", "best", "quality"):
        assert noise not in tokens


def test_tokenize_drops_short_and_numeric_noise():
    tokens = tokenize("Cat Bed 50cm 2024 XL")
    assert "cat" in tokens
    assert "2024" not in tokens and "xl" not in tokens


# ── scoring behaviour ───────────────────────────────────────────────────────
def test_more_shared_tokens_scores_higher():
    weak = score_pair("cat tunnel bed", "cat tunnel steel rack", 30.0, 8.0)
    strong = score_pair(RETAIL, SUPPLIER_EN, 30.0, 8.0)
    assert strong.confidence > weak.confidence


def test_untranslated_supplier_cannot_match():
    """Text is the only positive signal in v1, so a Chinese title scores nothing."""
    result = score_pair(RETAIL, "猫窝保暖防寒窝小型犬狗狗贝壳冬天半封闭式", 31.19, 6.72)
    assert result.confidence == 0.0

    assert score_pair(RETAIL, None, 31.19, 6.72).confidence == 0.0


def test_evidence_explains_the_match():
    """A bad margin months later has to be debuggable."""
    result = score_pair(RETAIL, SUPPLIER_EN, 31.19, 6.72)
    for key in ("jaccard", "shared_tokens", "price_ratio", "supplier_title_en"):
        assert key in result.evidence
    assert result.evidence["shared_tokens"]


def test_jaccard_bounds():
    assert jaccard(set(), {"a"}) == 0.0
    assert jaccard({"a"}, {"a"}) == 1.0
    assert 0 < jaccard({"a", "b"}, {"b", "c"}) < 1


# ── ranking ─────────────────────────────────────────────────────────────────
def test_best_matches_orders_by_confidence_and_drops_weak_pairs():
    retail = {"title": RETAIL, "price_usd": 31.19}
    suppliers = [
        {"id": "weak", "title_en": "steel kitchen rack", "cost_usd": 6.0},
        {"id": "good", "title_en": SUPPLIER_EN, "cost_usd": 6.72},
        {"id": "mid", "title_en": "plush pet bed", "cost_usd": 7.0},
    ]
    results = matcher.best_matches(retail, suppliers)
    ids = [s["id"] for s, _ in results]

    assert "weak" not in ids                    # below the floor, discarded
    assert ids[0] == "good"                     # strongest first
    assert all(r.confidence >= CANDIDATE_FLOOR for _, r in results)


def test_best_matches_respects_the_limit():
    """A realistic corpus: varied products, several plausible tunnel beds."""
    retail = {"title": RETAIL, "price_usd": 31.19}
    suppliers = [
        {"id": "t1", "title_en": "plush pet tunnel bed cat cave hanging ball", "cost_usd": 6.7},
        {"id": "t2", "title_en": "fuzzy cat tunnel bed collapsible ball toy", "cost_usd": 7.1},
        {"id": "t3", "title_en": "plush tunnel cat bed with dangling ball", "cost_usd": 6.4},
        {"id": "t4", "title_en": "soft fuzzy tunnel bed for cats ball", "cost_usd": 8.0},
        {"id": "x1", "title_en": "stainless steel kitchen rack", "cost_usd": 6.0},
        {"id": "x2", "title_en": "bamboo cutting board set", "cost_usd": 5.5},
        {"id": "x3", "title_en": "ceramic coffee mug gift box", "cost_usd": 4.2},
        {"id": "x4", "title_en": "silicone phone case clear", "cost_usd": 2.1},
    ]
    results = matcher.best_matches(retail, suppliers, limit=3)
    assert len(results) == 3
    assert all(s["id"].startswith("t") for s, _ in results)  # no kitchenware


def test_near_duplicate_corpus_does_not_strip_the_whole_vocabulary():
    """A homogeneous supplier set would otherwise mark every token generic,
    silently matching nothing at all."""
    retail = {"title": RETAIL, "price_usd": 31.19}
    identical = [
        {"id": str(i), "title_en": SUPPLIER_EN, "cost_usd": 6.72} for i in range(10)
    ]
    assert matcher.best_matches(retail, identical), "identical corpus matched nothing"


def test_generic_detection_needs_a_real_corpus():
    """Below the minimum, document frequency is noise — a token in 2 of 6
    listings is not a category word — so no filtering is applied at all."""
    small = [f"pet bed {w}" for w in
             ("rattan", "memory foam", "heated", "wicker", "orthopedic", "bamboo")]
    assert matcher.common_tokens(small) == set()


def test_genuinely_generic_tokens_are_stripped_in_a_large_corpus():
    """Across 30 distinct pet listings, 'pet' and 'bed' stop being evidence
    while the material words that identify each product survive."""
    materials = ("rattan", "foam", "heated", "wicker", "orthopedic", "bamboo",
                 "ceramic", "linen", "velvet", "mesh", "canvas", "leather",
                 "acrylic", "denim", "cork", "jute", "silk", "wool", "nylon",
                 "rubber", "marble", "walnut", "copper", "glass", "suede",
                 "satin", "tweed", "hemp", "cedar", "brass")
    corpus = [f"pet bed {m} cushion" for m in materials]
    generic = matcher.common_tokens(corpus)
    assert "pet" in generic and "bed" in generic
    assert not (set(materials) & generic), "material words must stay distinctive"


def test_no_suppliers_yields_no_matches():
    assert matcher.best_matches({"title": RETAIL, "price_usd": 30.0}, []) == []


def test_broad_generic_overlap_is_allowed_but_penalised():
    """Eight shared category words is weak evidence, but not nothing — and it
    must never outrank a match with distinctive tokens."""
    generic = {"plush", "pet", "tunnel", "bed", "cat", "cave", "hanging", "ball"}
    broad = score_pair(RETAIL, "plush pet tunnel bed cat cave hanging ball",
                       31.19, 6.72, generic=generic)
    distinctive = score_pair(RETAIL, SUPPLIER_EN, 31.19, 6.72, generic=set())

    assert broad.confidence > 0
    assert broad.evidence["generic_only"] is True
    assert broad.confidence < distinctive.confidence


def test_narrow_generic_overlap_is_still_rejected():
    """Two category words stays rejected — that's the dangerous case."""
    result = score_pair("Cat Bed Soft Warm", "pet cat bed cozy",
                        30.0, 8.0, generic={"cat", "bed", "pet"})
    assert result.confidence == 0.0
