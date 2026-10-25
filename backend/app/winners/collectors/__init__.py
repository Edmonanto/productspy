"""
Collector registry. Paid (Apify) collectors replace their free equivalent
when USE_APIFY=1 and APIFY_TOKEN is set.
"""
from .base import AdRecord, Collector
from .meta_ads import MetaAdLibraryCollector
from .tiktok_ads import TikTokCreativeCenterCollector
from .tiktok_organic import TikTokOrganicCollector
from .apify import ApifyMetaCollector, ApifyTikTokCollector, ApifyTikTokAdsCollector


def active_collectors() -> list[Collector]:
    pairs = [
        (ApifyMetaCollector(), MetaAdLibraryCollector()),
        (ApifyTikTokAdsCollector(), TikTokCreativeCenterCollector()),
        (ApifyTikTokCollector(), TikTokOrganicCollector()),
    ]
    chosen: list[Collector] = []
    for paid, free in pairs:
        if paid.enabled():
            chosen.append(paid)
        elif free.enabled():
            chosen.append(free)
    return chosen


__all__ = ["AdRecord", "Collector", "active_collectors"]
