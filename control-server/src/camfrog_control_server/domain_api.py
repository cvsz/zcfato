"""Profile, presence, Cloud Bot, Store, and subscription control-plane routes."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .adapters import cloud_bot_state
from .api import add_audit, get_db, require_admin, require_agent
from .models import (
    Account,
    AccountRuntimeSnapshot,
    Agent,
    AuthStateSnapshot,
    CloudBot,
    CloudBotStatusSnapshot,
    FriendSnapshot,
    PresenceSnapshot,
    ProfileSnapshot,
    PurchaseIntent,
    StoreCatalogItem,
    SubscriptionEntitlement,
    SubscriptionOverlay,
    utcnow,
)
from .presence_provider import PresenceObservation, resolve_presence
from .profile_provider import detect_authenticated_state
from .schemas import (
    AccountRoomState,
    AccountRuntimeRead,
    AccountSnapshotInput,
    AuthenticatedState,
    AuthStateRead,
    ClientProcessState,
    CloudBotCreate,
    CloudBotRead,
    CloudBotStatusInput,
    CloudBotStatusRead,
    EntitlementEvidenceSource,
    FriendSnapshotRead,
    HumanPresence,
    PresenceRead,
    ProfileSnapshotRead,
    PurchaseIntentConfirm,
    PurchaseIntentCreate,
    PurchaseIntentRead,
    StoreCatalogItemCreate,
    StoreCatalogItemRead,
    SubscriptionBaselinePut,
    SubscriptionOverlayCreate,
    SubscriptionOverlayRead,
    SubscriptionRead,
    SubscriptionTier,
)
from .subscriptions import effective_subscription, utc_aware

router = APIRouter()


def _account_or_404(db: Session, account_id: UUID) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    return account


def _profile_read(
    account: Account,
    snapshot: ProfileSnapshot,
    auth_snapshot: AuthStateSnapshot | None = None,
) -> ProfileSnapshotRead:
    return ProfileSnapshotRead(
        account_id=account.id,
        nickname=account.nickname,
        nickname_color=snapshot.nickname_color,
        nickname_flair=snapshot.nickname_flair,
        avatar_id=snapshot.avatar_id,
        alevel=snapshot.alevel,
        age=snapshot.age,
        gender=snapshot.gender,
        country=snapshot.country,
        status_text=snapshot.status_text,
        client_presence=snapshot.client_presence,
        subscription_type=snapshot.subscription_type,
        xp_count=snapshot.xp_count,
        summary=snapshot.summary_json,
        auth_state=auth_snapshot.state if auth_snapshot else AuthenticatedState.unknown,
        observed_at=snapshot.observed_at,
    )


@router.put("/agent/accounts/snapshot", status_code=status.HTTP_204_NO_CONTENT)
def ingest_account_snapshot(
    body: AccountSnapshotInput,
    agent: Annotated[Agent, Depends(require_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    account = db.scalar(
        select(Account)
        .where(
            Account.id == body.account_id, Account.agent_id == agent.id, Account.enabled.is_(True)
        )
        .with_for_update()
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assigned account not found."
        )

    snapshot = db.get(ProfileSnapshot, account.id)
    if snapshot is not None and utc_aware(body.observed_at) < utc_aware(snapshot.observed_at):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Snapshot is older than current data."
        )

    values = body.profile.model_dump(mode="json", exclude={"summary"})
    values["summary_json"] = body.profile.summary.model_dump(mode="json")
    if snapshot is None:
        snapshot = ProfileSnapshot(account_id=account.id, **values, observed_at=body.observed_at)
        db.add(snapshot)
    else:
        for key, value in values.items():
            setattr(snapshot, key, value)
        snapshot.observed_at = body.observed_at

    if body.auth is not None:
        auth_snapshot = db.get(AuthStateSnapshot, account.id)
        if auth_snapshot is not None and utc_aware(body.auth.observed_at) < utc_aware(
            auth_snapshot.observed_at
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Authentication observation is older than current data.",
            )
        state = detect_authenticated_state(
            nav_user_logged=body.auth.nav_user_logged,
            external_data_type=body.auth.external_data_type,
            login_form_visible=body.auth.login_form_visible,
        )
        if auth_snapshot is None:
            auth_snapshot = AuthStateSnapshot(account_id=account.id)
            db.add(auth_snapshot)
        auth_snapshot.state = state
        auth_snapshot.page_type = body.auth.external_data_type
        auth_snapshot.csrf_present = body.auth.csrf_present
        auth_snapshot.observed_at = body.auth.observed_at

    db.merge(
        PresenceSnapshot(
            account_id=account.id,
            state=body.profile.client_presence.value,
            source="profile",
            observed_at=body.observed_at,
        )
    )
    db.execute(delete(FriendSnapshot).where(FriendSnapshot.account_id == account.id))
    for friend in body.friends:
        db.add(
            FriendSnapshot(
                account_id=account.id,
                nickname=friend.nickname,
                display_name=friend.display_name,
                presence=friend.presence.value,
                nickname_color=friend.nickname_color,
                avatar_id=friend.avatar_id,
                alevel=friend.alevel,
                gender=friend.gender,
                observed_at=body.observed_at,
            )
        )
    add_audit(
        db,
        actor_type="agent",
        actor_id=str(agent.id),
        action="account.snapshot_received",
        resource_type="account",
        resource_id=str(account.id),
        details={"friend_count": len(body.friends), "source": "agent_snapshot"},
    )
    db.commit()


@router.get("/accounts/{account_id}/profile", response_model=ProfileSnapshotRead)
def read_profile(
    account_id: UUID,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ProfileSnapshotRead:
    account = _account_or_404(db, account_id)
    snapshot = db.get(ProfileSnapshot, account.id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No profile snapshot is available."
        )
    auth_snapshot = db.get(AuthStateSnapshot, account.id)
    return _profile_read(account, snapshot, auth_snapshot)


@router.get("/accounts/{account_id}/auth-state", response_model=AuthStateRead)
def read_auth_state(
    account_id: UUID,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthStateRead:
    account = _account_or_404(db, account_id)
    snapshot = db.get(AuthStateSnapshot, account_id)
    return AuthStateRead(
        account_id=account.id,
        nickname=account.nickname,
        state=snapshot.state if snapshot else AuthenticatedState.unknown,
        page_type=snapshot.page_type if snapshot else None,
        csrf_present=snapshot.csrf_present if snapshot else False,
        observed_at=snapshot.observed_at if snapshot else None,
    )


@router.get("/accounts/{account_id}/runtime", response_model=AccountRuntimeRead)
def read_account_runtime(
    account_id: UUID,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountRuntimeRead:
    account = _account_or_404(db, account_id)
    snapshot = db.get(AccountRuntimeSnapshot, account_id)
    observed_at = snapshot.observed_at if snapshot else None
    if snapshot is None or utc_aware(snapshot.observed_at) < utc_aware(
        utcnow() - timedelta(seconds=30)
    ):
        return AccountRuntimeRead(
            account_id=account.id,
            nickname=account.nickname,
            process_state=ClientProcessState.unknown,
            room_state=AccountRoomState.unknown,
            observed_at=observed_at,
        )
    return AccountRuntimeRead(
        account_id=account.id,
        nickname=account.nickname,
        process_state=ClientProcessState(snapshot.process_state),
        room_state=AccountRoomState(snapshot.room_state),
        observed_at=observed_at,
    )


@router.get("/accounts/{account_id}/friends", response_model=list[FriendSnapshotRead])
def read_friends(
    account_id: UUID,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    online_only: bool = False,
    limit: int = Query(default=500, ge=1, le=1000),
) -> list[FriendSnapshot]:
    _account_or_404(db, account_id)
    query = select(FriendSnapshot).where(FriendSnapshot.account_id == account_id)
    if online_only:
        query = query.where(FriendSnapshot.presence.in_(["online", "away", "busy"]))
    return list(db.scalars(query.order_by(FriendSnapshot.nickname).limit(limit)).all())


@router.get("/presence/{nickname}", response_model=PresenceRead)
def read_presence(
    nickname: str,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> PresenceRead:
    account = db.scalar(select(Account).where(func.lower(Account.nickname) == nickname.casefold()))
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    snapshot = db.get(PresenceSnapshot, account.id)
    if snapshot is None:
        return PresenceRead(
            account_id=account.id,
            nickname=account.nickname,
            state=HumanPresence.unknown,
            source="unknown",
            observed_at=account.created_at,
        )
    resolved = resolve_presence(
        [PresenceObservation(snapshot.state, snapshot.source, snapshot.observed_at)]
    )
    return PresenceRead(
        account_id=account.id,
        nickname=account.nickname,
        state=HumanPresence(resolved.state),
        source=resolved.source,
        observed_at=resolved.observed_at,
    )


@router.get("/accounts/{account_id}/subscription", response_model=SubscriptionRead)
def read_subscription(
    account_id: UUID,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SubscriptionRead:
    _account_or_404(db, account_id)
    baseline = db.get(SubscriptionEntitlement, account_id)
    overlays = list(
        db.scalars(
            select(SubscriptionOverlay)
            .where(SubscriptionOverlay.account_id == account_id)
            .order_by(SubscriptionOverlay.starts_at)
        ).all()
    )
    tier, source, active = effective_subscription(baseline, overlays)
    return SubscriptionRead(
        account_id=account_id,
        base_tier=baseline.base_tier if baseline else SubscriptionTier.unknown,
        base_term=baseline.base_term if baseline else "unknown",
        evidence_source=baseline.evidence_source if baseline else EntitlementEvidenceSource.unknown,
        evidence_note=baseline.evidence_note if baseline else None,
        observed_at=baseline.observed_at if baseline else None,
        effective_tier=tier,
        effective_source=source,
        active_overlay=SubscriptionOverlayRead.model_validate(active) if active else None,
        overlays=[SubscriptionOverlayRead.model_validate(item) for item in overlays],
    )


@router.put("/accounts/{account_id}/subscription/baseline", response_model=SubscriptionRead)
def set_subscription_baseline(
    account_id: UUID,
    body: SubscriptionBaselinePut,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SubscriptionRead:
    account = db.scalar(select(Account).where(Account.id == account_id).with_for_update())
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    baseline = db.get(SubscriptionEntitlement, account_id)
    if baseline is None:
        baseline = SubscriptionEntitlement(account_id=account_id)
        db.add(baseline)
    baseline.base_tier = body.base_tier.value
    baseline.base_term = body.base_term
    baseline.evidence_source = body.evidence_source.value
    baseline.evidence_note = body.evidence_note
    baseline.observed_at = body.observed_at
    add_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="subscription.baseline_recorded",
        resource_type="account",
        resource_id=str(account_id),
        details={"base_tier": body.base_tier.value, "base_term": body.base_term},
    )
    db.commit()
    return read_subscription(account_id, None, db)  # type: ignore[arg-type]


@router.post(
    "/accounts/{account_id}/subscription/overlays",
    response_model=SubscriptionOverlayRead,
    status_code=status.HTTP_201_CREATED,
)
def add_subscription_overlay(
    account_id: UUID,
    body: SubscriptionOverlayCreate,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SubscriptionOverlay:
    account = db.scalar(select(Account).where(Account.id == account_id).with_for_update())
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    overlap = db.scalar(
        select(SubscriptionOverlay.id)
        .where(
            SubscriptionOverlay.account_id == account_id,
            SubscriptionOverlay.starts_at < body.expires_at,
            SubscriptionOverlay.expires_at > body.starts_at,
        )
        .limit(1)
    )
    if overlap is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subscription overlays cannot overlap; record sequential term dates explicitly.",
        )
    overlay = SubscriptionOverlay(
        account_id=account_id,
        tier=body.tier.value,
        starts_at=body.starts_at,
        expires_at=body.expires_at,
        evidence_source=body.evidence_source.value,
        evidence_note=body.evidence_note,
    )
    db.add(overlay)
    add_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="subscription.overlay_recorded",
        resource_type="account",
        resource_id=str(account_id),
        details={
            "tier": body.tier.value,
            "starts_at": body.starts_at.isoformat(),
            "expires_at": body.expires_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(overlay)
    return overlay


@router.post("/cloud-bots", response_model=CloudBotRead, status_code=status.HTTP_201_CREATED)
def create_cloud_bot(
    body: CloudBotCreate,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CloudBot:
    agent = db.scalar(select(Agent).where(Agent.id == body.agent_id, Agent.revoked_at.is_(None)))
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Active agent not found."
        )
    bot = CloudBot(name=body.name, agent_id=body.agent_id)
    db.add(bot)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bot name or agent already assigned."
        ) from exc
    add_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="cloud_bot.registered",
        resource_type="cloud_bot",
        resource_id=str(bot.id),
        details={"name": bot.name, "agent_id": str(bot.agent_id)},
    )
    db.commit()
    db.refresh(bot)
    return bot


@router.get("/cloud-bots", response_model=list[CloudBotRead])
def list_cloud_bots(
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CloudBot]:
    return list(db.scalars(select(CloudBot).order_by(CloudBot.created_at.desc())).all())


@router.get("/cloud-bots/{cloud_bot_id}/status", response_model=CloudBotStatusRead)
def read_cloud_bot_status(
    cloud_bot_id: UUID,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CloudBotStatusRead:
    bot = db.get(CloudBot, cloud_bot_id)
    if bot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cloud Bot not found.")
    snapshot = db.scalar(
        select(CloudBotStatusSnapshot)
        .where(CloudBotStatusSnapshot.cloud_bot_id == cloud_bot_id)
        .order_by(CloudBotStatusSnapshot.observed_at.desc())
        .limit(1)
    )
    return CloudBotStatusRead(
        cloud_bot_id=cloud_bot_id,
        state=snapshot.state if snapshot else "unknown",
        raw_status=snapshot.raw_status if snapshot else None,
        reason=snapshot.reason if snapshot else None,
        uptime_seconds=snapshot.uptime_seconds if snapshot else None,
        observed_at=snapshot.observed_at if snapshot else None,
    )


@router.post(
    "/agent/cloud-bots/{cloud_bot_id}/status",
    response_model=CloudBotStatusRead,
    status_code=status.HTTP_201_CREATED,
)
def report_cloud_bot_status(
    cloud_bot_id: UUID,
    body: CloudBotStatusInput,
    agent: Annotated[Agent, Depends(require_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> CloudBotStatusRead:
    bot = db.scalar(
        select(CloudBot).where(CloudBot.id == cloud_bot_id, CloudBot.agent_id == agent.id)
    )
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assigned Cloud Bot not found."
        )
    state = cloud_bot_state(body.reason, body.raw_status)
    snapshot = CloudBotStatusSnapshot(
        cloud_bot_id=bot.id,
        state=state,
        raw_status=body.raw_status,
        reason=body.reason,
        uptime_seconds=body.uptime_seconds,
        observed_at=body.observed_at,
    )
    db.add(snapshot)
    add_audit(
        db,
        actor_type="agent",
        actor_id=str(agent.id),
        action="cloud_bot.status_reported",
        resource_type="cloud_bot",
        resource_id=str(bot.id),
        details={"state": state},
    )
    db.commit()
    return CloudBotStatusRead(
        cloud_bot_id=bot.id,
        state=state,
        raw_status=body.raw_status,
        reason=body.reason,
        uptime_seconds=body.uptime_seconds,
        observed_at=body.observed_at,
    )


@router.post(
    "/store/catalog/items",
    response_model=StoreCatalogItemRead,
    status_code=status.HTTP_201_CREATED,
)
def upsert_store_item(
    body: StoreCatalogItemCreate,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> StoreCatalogItem:
    item = db.scalar(
        select(StoreCatalogItem).where(
            StoreCatalogItem.source_item_id == body.source_item_id,
            StoreCatalogItem.item_type == body.item_type.value,
        )
    )
    values = body.model_dump(exclude={"item_type", "metadata"})
    values["item_type"] = body.item_type.value
    values["metadata_json"] = body.metadata
    if item is None:
        item = StoreCatalogItem(**values)
        db.add(item)
    else:
        for key, value in values.items():
            setattr(item, key, value)
    add_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="store.catalog_item_upserted",
        resource_type="store_item",
        resource_id=str(item.id) if item.id else None,
        details={"source_item_id": body.source_item_id, "item_type": body.item_type.value},
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/store/catalog/items", response_model=list[StoreCatalogItemRead])
def list_store_items(
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    available_only: bool = True,
) -> list[StoreCatalogItem]:
    query = select(StoreCatalogItem)
    if available_only:
        query = query.where(StoreCatalogItem.available.is_(True))
    return list(db.scalars(query.order_by(StoreCatalogItem.item_type, StoreCatalogItem.name)).all())


@router.post(
    "/store/purchase-intents",
    response_model=PurchaseIntentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_intent(
    body: PurchaseIntentCreate,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseIntent:
    _account_or_404(db, body.account_id)
    item = db.get(StoreCatalogItem, body.catalog_item_id)
    if item is None or not item.available:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Available catalog item not found."
        )
    now = utcnow()
    intent = PurchaseIntent(
        account_id=body.account_id,
        catalog_item_id=item.id,
        item_name=item.name,
        item_type=item.item_type,
        currency=item.currency,
        price_minor=item.price_minor,
        state="pending_confirmation",
        confirmation_expires_at=now + timedelta(minutes=10),
    )
    db.add(intent)
    db.flush()
    add_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="store.purchase_intent_created",
        resource_type="purchase_intent",
        resource_id=str(intent.id),
        details={"account_id": str(body.account_id), "item_type": item.item_type},
    )
    db.commit()
    db.refresh(intent)
    return intent


@router.get("/store/purchase-intents", response_model=list[PurchaseIntentRead])
def list_purchase_intents(
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=100, ge=1, le=200),
) -> list[PurchaseIntent]:
    return list(
        db.scalars(
            select(PurchaseIntent).order_by(PurchaseIntent.created_at.desc()).limit(limit)
        ).all()
    )


@router.post(
    "/store/purchase-intents/{intent_id}/confirm",
    response_model=PurchaseIntentRead,
)
def confirm_purchase_intent(
    intent_id: UUID,
    body: PurchaseIntentConfirm,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseIntent:
    intent = db.scalar(
        select(PurchaseIntent).where(PurchaseIntent.id == intent_id).with_for_update()
    )
    if intent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Purchase intent not found."
        )
    if intent.state != "pending_confirmation":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Intent is no longer pending."
        )
    now = utcnow()
    if utc_aware(intent.confirmation_expires_at) <= utc_aware(now):
        intent.state = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Purchase confirmation expired."
        )
    item = db.get(StoreCatalogItem, intent.catalog_item_id)
    if item is None or not item.available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Catalog item is no longer available."
        )
    if (
        item.name != intent.item_name
        or item.currency != intent.currency
        or item.price_minor != intent.price_minor
        or body.expected_item_name != intent.item_name
        or body.expected_currency != intent.currency
        or body.expected_price_minor != intent.price_minor
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Catalog or confirmation values changed; create a new intent and review it.",
        )
    intent.state = "confirmed"
    intent.confirmed_at = now
    add_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="store.purchase_intent_confirmed",
        resource_type="purchase_intent",
        resource_id=str(intent.id),
        details={
            "account_id": str(intent.account_id),
            "item_type": intent.item_type,
            "price_minor": intent.price_minor,
            "currency": intent.currency,
        },
    )
    db.commit()
    db.refresh(intent)
    return intent


@router.post("/store/purchase-intents/{intent_id}/cancel", response_model=PurchaseIntentRead)
def cancel_purchase_intent(
    intent_id: UUID,
    _admin: Annotated[None, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseIntent:
    intent = db.scalar(
        select(PurchaseIntent).where(PurchaseIntent.id == intent_id).with_for_update()
    )
    if intent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Purchase intent not found."
        )
    if intent.state != "pending_confirmation":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Only pending intents can be canceled."
        )
    intent.state = "canceled"
    add_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="store.purchase_intent_canceled",
        resource_type="purchase_intent",
        resource_id=str(intent.id),
    )
    db.commit()
    db.refresh(intent)
    return intent
