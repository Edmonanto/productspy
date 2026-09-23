"""Match scoring — pure functions, no I/O.

Links a retail listing (real price, no cost) to a supplier listing (real
cost, no retail) so margin can come from two observed numbers.

The governing constraint: **a wrong match is worse than no match.** It would
report a confident margin on a product pairing that does not exist, and a
subscriber could order against it. So v1 is built to under-claim:

  * price ratio is a **veto**, never evidence of a match on its own,
  * a match needs shared *distinctive* tokens, not just any overlap,
  * confidence is hard-capped below the auto-confirm threshold, so every v1
    match lands in a review queue rather than silently changing a margin.
"""
import math
import re
from dataclasses import dataclass, field
from typing import Any

# Auto-confirm needs image evidence, which v1 does not have. The cap makes
# that structural rather than a matter of tuning: no v1 match can confirm.
CONFIRM_THRESHOLD = 0.85
V1_CONFIDENCE_CAP = 0.75
# The floor only decides what reaches the review queue — nothing here applies
# a margin automatically — so it is set to surface plausible pairs for a human
# rather than to be a correctness gate. Provisional until measured on real data.
CANDIDATE_FLOOR = 0.50

# Retail/cost ratios outside this band are implausible for the same product.
MIN_PRICE_RATIO = 1.5
MAX_PRICE_RATIO = 15.0
# The band where a dropshipping markup normally sits.
IDEAL_RATIO_LOW = 2.0
IDEAL_RATIO_HIGH = 8.0

# Two shared tokens is not evidence: "pet bed" vs "pet bed" overlaps
# perfectly and means nothing, because both are category words.
MIN_SHARED_TOKENS = 3
# A title with fewer content tokens than this cannot discriminate at all.
MIN_TITLE_TOKENS = 3
# A token carried by more than this share of the supplier corpus is a
# category word, not an identifier. Derived from the corpus rather than a
# hand-curated list, so it stays correct as the catalogue changes.
#
# Document frequency needs a real corpus to mean anything: across 8 suppliers
# a 20% threshold marks any token in two of them as generic, which strips the
# very words that identify the product. Hence a high bar and a minimum corpus.
GENERIC_TOKEN_DF = 0.35
MIN_CORPUS_FOR_DF = 25
MIN_DISTINCTIVE_TOKENS = 2
# Document frequency only tells us something when the common tokens are a
# minority. In a narrow catalogue — every supplier is a cat bed — nearly the
# whole vocabulary looks common, and stripping it would silently match
# nothing at all. Past this share, the signal is treated as uninformative.
MAX_GENERIC_SHARE = 0.60
# When every shared token is a category word, heavy overlap is still weak
# evidence — eight shared words beats two, even generic ones. Allowed above
# this count, but penalised so it cannot outrank a distinctive match.
FALLBACK_SHARED_TOKENS = 5
GENERIC_ONLY_PENALTY = 0.65

# Words that appear across most listings and so carry no matching signal.
STOPWORDS = frozenset("""
a an the and or for with without of in on at to from by is are this that
new hot sale free shipping premium quality high best top super ultra pro
plus max mini large small size color style type set pack pcs piece pieces
item items product products style1 style2 cm mm inch inches kg g ml
men women unisex kids adult universal portable multi multifunctional
""".split())


@dataclass
class MatchResult:
    confidence: float
    method: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.confidence >= CONFIRM_THRESHOLD:
            return "confirmed"
        if self.confidence >= CANDIDATE_FLOOR:
            return "candidate"
        return "rejected"


def tokenize(title: str | None) -> set[str]:
    """Content tokens: lowercased, de-punctuated, stopwords and noise removed."""
    if not title:
        return set()
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {
        w for w in words
        if len(w) > 2 and w not in STOPWORDS and not w.isdigit()
    }


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def price_ratio_score(retail_usd: float | None, cost_usd: float | None) -> float | None:
    """0-1 plausibility of this retail/cost pair, or None to veto outright.

    None means "these cannot be the same product" and stops the match dead;
    a low score only weakens it.
    """
    if not retail_usd or not cost_usd or retail_usd <= 0 or cost_usd <= 0:
        return None
    ratio = retail_usd / cost_usd
    if ratio < MIN_PRICE_RATIO or ratio > MAX_PRICE_RATIO:
        return None
    if IDEAL_RATIO_LOW <= ratio <= IDEAL_RATIO_HIGH:
        return 1.0
    # Taper linearly out to the veto boundaries.
    if ratio < IDEAL_RATIO_LOW:
        return (ratio - MIN_PRICE_RATIO) / (IDEAL_RATIO_LOW - MIN_PRICE_RATIO)
    return max(0.0, (MAX_PRICE_RATIO - ratio) / (MAX_PRICE_RATIO - IDEAL_RATIO_HIGH))


def common_tokens(titles: list[str | None], threshold: float = GENERIC_TOKEN_DF) -> set[str]:
    """Tokens appearing in more than `threshold` of the corpus.

    These are category words — 'pet', 'bed', 'cable' — which overlap across
    unrelated listings and so cannot identify a specific product.
    """
    # Distinct titles only: a corpus of near-duplicates would mark every
    # token as 100% frequent and strip the vocabulary down to nothing.
    unique = {t for t in titles if t}
    present = [tokenize(t) for t in unique]
    present = [tokens for tokens in present if tokens]
    if len(present) < MIN_CORPUS_FOR_DF:   # too small to infer anything
        return set()
    counts: dict[str, int] = {}
    for tokens in present:
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
    limit = threshold * len(present)
    generic = {token for token, n in counts.items() if n > limit}

    # A corpus too homogeneous to discriminate: fall back to no filtering and
    # let the shared-token minimum and depth carry the decision instead.
    if counts and len(generic) / len(counts) > MAX_GENERIC_SHARE:
        return set()
    return generic


def score_pair(
    retail_title: str,
    supplier_title_en: str | None,
    retail_usd: float | None,
    cost_usd: float | None,
    generic: set[str] | None = None,
) -> MatchResult:
    """Score one retail/supplier pair.

    `supplier_title_en` is the translated 1688 title; an untranslated supplier
    cannot be matched on text, and text is the only positive signal in v1.
    `generic` are corpus-derived category words that don't count as evidence.
    """
    price = price_ratio_score(retail_usd, cost_usd)
    if price is None:
        return MatchResult(
            0.0, "price-veto",
            {"reason": "retail/cost ratio outside plausible band",
             "retail_usd": retail_usd, "cost_usd": cost_usd},
        )

    retail_tokens = tokenize(retail_title)
    supplier_tokens = tokenize(supplier_title_en)

    # A two-word title matches other two-word titles perfectly and tells us
    # nothing, so short titles are refused outright rather than scored.
    if min(len(retail_tokens), len(supplier_tokens)) < MIN_TITLE_TOKENS:
        return MatchResult(
            0.0, "title",
            {"reason": "title too short to discriminate",
             "retail_tokens": len(retail_tokens),
             "supplier_tokens": len(supplier_tokens)},
        )

    shared = retail_tokens & supplier_tokens
    if len(shared) < MIN_SHARED_TOKENS:
        return MatchResult(
            0.0, "title",
            {"reason": f"only {len(shared)} shared token(s); need {MIN_SHARED_TOKENS}",
             "shared": sorted(shared)},
        )

    distinctive = shared - (generic or set())
    penalty = 1.0
    if len(distinctive) < MIN_DISTINCTIVE_TOKENS:
        # Every shared token is a category word. Reject unless the overlap is
        # broad enough to mean something on its own, and penalise it either
        # way so it never outranks a genuinely distinctive match.
        if len(shared) < FALLBACK_SHARED_TOKENS:
            return MatchResult(
                0.0, "title",
                {"reason": "shared tokens are all category words",
                 "shared": sorted(shared), "distinctive": sorted(distinctive)},
            )
        penalty = GENERIC_ONLY_PENALTY
        distinctive = shared

    overlap = jaccard(retail_tokens, supplier_tokens)
    # Absolute evidence, weighted above the ratio: a perfect overlap of two
    # generic tokens must never outrank five specific ones.
    depth = min(1.0, math.log(len(distinctive) + 1) / math.log(6))

    raw = (0.30 * overlap + 0.55 * depth + 0.15 * price) * penalty
    confidence = round(min(raw, V1_CONFIDENCE_CAP), 2)

    return MatchResult(
        confidence,
        "title+price",
        {
            "jaccard": round(overlap, 3),
            "shared_tokens": sorted(shared),
            "distinctive_tokens": sorted(distinctive),
            "shared_count": len(shared),
            "price_score": round(price, 3),
            "price_ratio": round(retail_usd / cost_usd, 2),
            "supplier_title_en": supplier_title_en,
            "generic_only": penalty != 1.0,
            "capped_at": V1_CONFIDENCE_CAP,
        },
    )


def best_matches(
    retail: dict[str, Any],
    suppliers: list[dict[str, Any]],
    limit: int = 3,
) -> list[tuple[dict[str, Any], MatchResult]]:
    """Top candidate suppliers for one retail product, best first.

    Returns only results at or above CANDIDATE_FLOOR — anything weaker is
    noise that would bury the review queue.
    """
    # Category words are derived from this supplier corpus, so the notion of
    # "generic" tracks the catalogue instead of a hand-maintained list.
    generic = common_tokens([s.get("title_en") for s in suppliers])

    scored = []
    for supplier in suppliers:
        result = score_pair(
            retail.get("title", ""),
            supplier.get("title_en"),
            retail.get("price_usd"),
            supplier.get("cost_usd"),
            generic=generic,
        )
        if result.confidence >= CANDIDATE_FLOOR:
            scored.append((supplier, result))

    scored.sort(key=lambda pair: pair[1].confidence, reverse=True)
    return scored[:limit]
