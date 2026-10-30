"""Product photos stored by us (see app/winners/photos.py). Public: picks are
shown on the landing page too, and the URL carries the product id only."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.winners import photos

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/{product_id}.jpg")
async def product_image(product_id: str) -> Response:
    try:
        uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    got = await photos.get(product_id)
    if got is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    data, ctype = got
    # The URL changes (?v=) whenever the photo does, so it can be cached for good.
    return Response(content=data, media_type=ctype,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})
