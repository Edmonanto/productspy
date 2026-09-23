"""Which providers run in an ingestion pass.

Providers are opt-in by credential: set the keys and the source turns on,
so adding a marketplace means adding a class here, not touching the worker.
"""
from . import base
from .aggregator1688 import Aggregator1688Provider
from .alibaba1688 import Alibaba1688Provider
from .aliexpress import AliExpressProvider
from .amazon import AmazonProvider
from .tiktok_shop import TikTokShopProvider


def enabled_providers() -> list[base.Provider]:
    providers: list[base.Provider] = []

    aliexpress = AliExpressProvider()
    if aliexpress.configured:
        providers.append(aliexpress)

    alibaba1688 = Alibaba1688Provider()
    if alibaba1688.configured:
        providers.append(alibaba1688)

    # Aggregator path: same source="1688", no Open Platform approval needed.
    agg1688 = Aggregator1688Provider()
    if agg1688.configured:
        providers.append(agg1688)

    tiktok = TikTokShopProvider()
    if tiktok.configured:
        providers.append(tiktok)

    amazon = AmazonProvider()
    if amazon.configured:
        providers.append(amazon)

    return providers
