"""Which providers run in an ingestion pass.

Providers are opt-in by credential: set the keys and the source turns on.
Adding Keepa or a different vendor later means adding a class here, not
touching the worker.
"""
from . import base
from .alibaba1688 import Alibaba1688Provider
from .aliexpress import AliExpressProvider
from .apify import ApifyProvider
from .. import config


def enabled_providers() -> list[base.Provider]:
    providers: list[base.Provider] = []

    aliexpress = AliExpressProvider()
    if aliexpress.configured:
        providers.append(aliexpress)

    alibaba1688 = Alibaba1688Provider()
    if alibaba1688.configured:
        providers.append(alibaba1688)

    # One Apify actor per source; unset actor ids are simply skipped.
    for actor_id, source in (
        # AliExpress via Apify needs no affiliate approval, and covers the
        # full catalogue rather than the affiliate subset.
        (config.APIFY_ALIEXPRESS_ACTOR, "aliexpress"),
        (config.APIFY_AMAZON_ACTOR, "amazon"),
        (config.APIFY_TIKTOK_ACTOR, "tiktok"),
        (config.APIFY_ADS_ACTOR, "facebook"),
    ):
        if not actor_id:
            continue
        provider = ApifyProvider(actor_id=actor_id, source=source)
        if provider.configured:
            providers.append(provider)

    return providers
