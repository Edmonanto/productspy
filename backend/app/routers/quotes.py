"""/quotes — customers ask for an exact price; admins answer.

The profit calculator on a Daily Winners product works from estimates (the
store price, the supplier or AI cost estimate, a weight-based shipping
guess). When a customer wants a firm number — unit cost at their quantity,
shipping to their country — they request a quote. Admins
(ADMIN_EMAILS) see every request and reply with a unit price, a shipping
price and a message.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import config, repository
from ..auth import CurrentUser, current_user
from ..schemas import Quote, QuoteCreate, QuoteList, QuoteReply

router = APIRouter(prefix="/quotes", tags=["quotes"])

# Generous for a real buyer; stops a script filling the admin queue.
DAILY_QUOTE_LIMIT = 20


def is_admin(user: CurrentUser) -> bool:
    return user.email.lower() in config.ADMIN_EMAILS


def _to_quote(row) -> Quote:
    money = lambda v: float(v) if v is not None else None  # noqa: E731
    return Quote(
        id=str(row["id"]),
        user_email=row["user_email"],
        product_id=str(row["product_id"]) if row["product_id"] else None,
        product_title=row["product_title"],
        quantity=row["quantity"],
        destination_country=row["destination_country"],
        target_price_usd=money(row["target_price_usd"]),
        notes=row["notes"],
        status=row["status"],
        quoted_unit_usd=money(row["quoted_unit_usd"]),
        quoted_shipping_usd=money(row["quoted_shipping_usd"]),
        reply=row["reply"],
        created_at=row["created_at"],
        replied_at=row["replied_at"],
    )


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


@router.post("/", response_model=Quote, status_code=status.HTTP_201_CREATED)
async def request_quote(body: QuoteCreate, user: CurrentUser = Depends(current_user)) -> Quote:
    if not _valid_uuid(body.product_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    title = await repository.product_title(body.product_id)
    if title is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")

    if await repository.quotes_created_today(user.id) >= DAILY_QUOTE_LIMIT:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You can request up to {DAILY_QUOTE_LIMIT} quotes a day.",
        )

    row = await repository.create_quote(
        user_id=user.id,
        user_email=user.email,
        product_id=body.product_id,
        product_title=title,
        quantity=body.quantity,
        destination_country=body.destination_country.strip(),
        target_price_usd=body.target_price_usd,
        notes=body.notes.strip(),
    )
    return _to_quote(row)


@router.get("/", response_model=QuoteList)
async def list_quotes(
    all: bool = Query(False, description="admins: every customer's quotes"),
    user: CurrentUser = Depends(current_user),
) -> QuoteList:
    admin = is_admin(user)
    rows = await repository.list_quotes(None if (all and admin) else user.id)
    return QuoteList(quotes=[_to_quote(r) for r in rows], is_admin=admin)


@router.post("/{quote_id}/reply", response_model=Quote)
async def reply_to_quote(
    quote_id: str, body: QuoteReply, user: CurrentUser = Depends(current_user)
) -> Quote:
    if not is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only admins can reply to quotes")
    if body.status == "quoted" and body.quoted_unit_usd is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A quote needs a unit price"
        )
    if not _valid_uuid(quote_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Quote not found")

    row = await repository.reply_quote(
        quote_id, body.status, body.quoted_unit_usd, body.quoted_shipping_usd, body.reply.strip()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Quote not found")
    return _to_quote(row)
