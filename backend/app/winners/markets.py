"""
Target markets a user can pick.

meta_countries   -> ISO codes sent to the Facebook Ad Library (API or web)
meta_api_ok      -> the official Ad Library API only returns *commercial* ads
                    that were delivered in the EU (DSA). Outside the EU we
                    fall back to the web scraper or Apify.
tiktok_region    -> region code used by TikTok Creative Center (Top Ads)
proxy_env        -> optional env var holding a residential proxy for this
                    country (TikTok organic results are geo-dependent)
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Market:
    code: str
    name: str
    flag: str
    currency: str
    language: str
    meta_countries: tuple[str, ...]
    tiktok_regions: tuple[str, ...]
    meta_api_ok: bool = False
    search_terms: tuple[str, ...] = field(default_factory=tuple)

    @property
    def proxy_env(self) -> str:
        return f"PROXY_URL_{self.code}"


# Ad copy that almost only appears on e-commerce product ads. The Ad Library
# has no "category = ecommerce" filter, so we search by these phrases.
_EN_TERMS = (
    "free shipping", "50% off", "shop now", "limited stock", "order now",
    "tiktok made me buy it", "best seller", "get yours",
)
_FR_TERMS = (
    "livraison gratuite", "-50%", "commandez maintenant", "stock limité",
    "offre spéciale", "paiement à la livraison",
)
_DE_TERMS = ("kostenloser versand", "jetzt bestellen", "nur heute", "-50%")
_AR_TERMS = ("free delivery", "cash on delivery", "توصيل مجاني", "الدفع عند الاستلام")


MARKETS: dict[str, Market] = {
    "US": Market("US", "United States", "🇺🇸", "USD", "en", ("US",), ("US",), False, _EN_TERMS),
    "UK": Market("UK", "United Kingdom", "🇬🇧", "GBP", "en", ("GB",), ("GB",), False, _EN_TERMS),
    "EU": Market(
        "EU", "Europe (all EU)", "🇪🇺", "EUR", "en",
        ("FR", "DE", "IT", "ES", "NL", "BE", "PL", "SE", "PT", "AT"),
        ("FR", "DE", "IT", "ES", "NL"), True, _EN_TERMS + _FR_TERMS + _DE_TERMS,
    ),
    "FR": Market("FR", "France", "🇫🇷", "EUR", "fr", ("FR",), ("FR",), True, _FR_TERMS),
    "DE": Market("DE", "Germany", "🇩🇪", "EUR", "de", ("DE",), ("DE",), True, _DE_TERMS),
    "CA": Market("CA", "Canada", "🇨🇦", "CAD", "en", ("CA",), ("CA",), False, _EN_TERMS + _FR_TERMS),
    "AU": Market("AU", "Australia", "🇦🇺", "AUD", "en", ("AU",), ("AU",), False, _EN_TERMS),
    "AE": Market("AE", "UAE / Dubai", "🇦🇪", "AED", "en", ("AE",), ("AE",), False, _AR_TERMS + _EN_TERMS),
    "SA": Market("SA", "Saudi Arabia", "🇸🇦", "SAR", "ar", ("SA",), ("SA",), False, _AR_TERMS),
}

DEFAULT_MARKET = "US"


def get_market(code: str) -> Market:
    code = (code or "").upper()
    if code not in MARKETS:
        raise KeyError(f"Unknown market '{code}'. Choose from: {', '.join(MARKETS)}")
    return MARKETS[code]


def market_public(m: Market) -> dict:
    return {
        "code": m.code,
        "name": m.name,
        "flag": m.flag,
        "currency": m.currency,
        "meta_official_api": m.meta_api_ok,
    }
