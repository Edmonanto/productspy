"""1688.com (Alibaba China wholesale) via the hosted search/detail endpoints.

- `client`  — HTTP calls and envelope/error handling
- `parser`  — raw JSON -> the normalized models below (pure, fixture-tested)
- `models`  — what the rest of the app sees; nothing outside this package
              touches the raw 1688 payload
"""
from .client import Ali1688Error, fetch_detail, search
from .models import OfferDetail, SearchOffer, SearchPage

SOURCE = "1688"

__all__ = [
    "SOURCE",
    "Ali1688Error",
    "OfferDetail",
    "SearchOffer",
    "SearchPage",
    "fetch_detail",
    "search",
]
