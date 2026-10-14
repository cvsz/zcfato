"""Allowlisted projection of browser-extracted Camfrog profile state.

Callers pass only the in-memory ``external_data`` object and DOM marker booleans. The result
contains a small normalized summary; it never returns the source object or any secret fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PRESENCE_VALUES = {"online", "away", "busy", "offline"}
PRIVATE_PAGE_TYPES = {"profile", "settings"}


def normalize_presence(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized = value.strip().casefold()
    return normalized if normalized in PRESENCE_VALUES else "unknown"


def detect_authenticated_state(
    *,
    nav_user_logged: bool,
    external_data_type: Any,
    login_form_visible: bool,
) -> str:
    page_type = external_data_type.casefold() if isinstance(external_data_type, str) else ""
    if page_type == "public":
        return "public"
    if nav_user_logged and page_type in PRIVATE_PAGE_TYPES:
        return "authenticated"
    if not nav_user_logged and login_form_visible and not page_type:
        return "login_required"
    return "unknown"


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0 or value != value or value in {float("inf"), float("-inf")}:
        return None
    return value


def _count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, list):
        return len(value)
    if isinstance(value, Mapping):
        count = value.get("count")
        return max(0, count) if isinstance(count, int) and not isinstance(count, bool) else None
    return None


def _summary(data: Mapping[str, Any]) -> dict[str, Any]:
    balance_data = data.get("balance")
    balance_data = balance_data if isinstance(balance_data, Mapping) else {}
    balance = {
        key: number
        for key in (
            "points",
            "coins",
            "rewards",
            "next_level_remain",
            "next_level_difference",
        )
        if (number := _number(balance_data.get(key))) is not None
    }
    if (coins_amount := _number(data.get("coins_amount"))) is not None:
        balance["coins"] = coins_amount

    reward_data = data.get("reward_program")
    reward_data = reward_data if isinstance(reward_data, Mapping) else {}
    reward_status = reward_data.get("status")
    reward_status = reward_status if isinstance(reward_status, Mapping) else {}
    engine = reward_data.get("engine")
    reward_balance = _number(reward_data.get("balance"))
    reward = {
        "engine": engine[:32] if isinstance(engine, str) else None,
        "enabled": reward_status.get("enabled")
        if isinstance(reward_status.get("enabled"), bool)
        else None,
        "show": reward_data.get("show") if isinstance(reward_data.get("show"), bool) else None,
        "balance": reward_balance,
        "streak_count": _count(reward_data.get("streaks")),
        "activity_count": _count(reward_data.get("active_activities")),
    }

    gifts_data = data.get("gifts")
    gifts_data = gifts_data if isinstance(gifts_data, Mapping) else {}
    friends_data = data.get("friends")
    friends_data = friends_data if isinstance(friends_data, Mapping) else {}
    return {
        "balance": balance,
        "reward_program": reward,
        "gift_count": _count(gifts_data.get("items")),
        "xpback_count": _count(gifts_data.get("xpbacks")),
        "friend_counts": {
            "all": _count(friends_data.get("all")),
            "online": _count(friends_data.get("online")),
            "added": _count(friends_data.get("added")),
        },
        "have_room": data.get("have_room") if isinstance(data.get("have_room"), bool) else None,
        "notifications_count": _count(data.get("notifications_count")),
    }


def normalize_friend_entries(response: Any) -> list[dict[str, Any]]:
    """Project observed friend-entry fields without retaining URLs or source payloads."""
    if isinstance(response, list):
        entries = response
    elif isinstance(response, Mapping):
        if response.get("redirect") or response.get("error"):
            return []
        entries = response.get("friends", response.get("items"))
        if not isinstance(entries, list):
            raise ValueError("Friend response envelope is not recognized.")
    else:
        raise ValueError("Friend response must be an array or object.")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in entries[:1000]:
        if not isinstance(item, Mapping):
            continue
        nickname = item.get("original_nick", item.get("nickname"))
        if not isinstance(nickname, str):
            continue
        nickname = nickname.strip()
        if not nickname or len(nickname) > 256 or any(ord(char) < 32 for char in nickname):
            continue
        identity = nickname.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        client_status = item.get("client_status")
        if isinstance(client_status, list):
            client_status = next((value for value in client_status if isinstance(value, str)), None)
        color = item.get("color")
        display_name = item.get("display_name")
        normalized.append(
            {
                "nickname": nickname,
                "display_name": display_name[:256] if isinstance(display_name, str) else None,
                "presence": normalize_presence(client_status),
                "nickname_color": color[:24] if isinstance(color, str) else None,
                "avatar_id": item.get("avatar_id")
                if isinstance(item.get("avatar_id"), int)
                else None,
                "alevel": item.get("alevel_id") if isinstance(item.get("alevel_id"), int) else None,
                "gender": item.get("gender") if isinstance(item.get("gender"), int) else None,
            }
        )
    return normalized


def project_external_data(
    external_data: Mapping[str, Any],
    *,
    nav_user_logged: bool,
    login_form_visible: bool = False,
) -> dict[str, Any]:
    """Return only fields accepted by the agent snapshot API; discard secrets by construction."""
    page_type = external_data.get("type")
    normalized_type = (
        page_type
        if isinstance(page_type, str) and page_type in {*PRIVATE_PAGE_TYPES, "public"}
        else None
    )
    csrf_value = external_data.get("csrf")
    csrf_present = isinstance(csrf_value, str) and bool(csrf_value.strip())
    auth = {
        "nav_user_logged": bool(nav_user_logged),
        "login_form_visible": bool(login_form_visible),
        "external_data_type": normalized_type,
        "csrf_present": csrf_present,
    }

    profile = {
        "nickname_color": external_data.get("nickname_color"),
        "nickname_flair": external_data.get("nickname_flair"),
        "avatar_id": external_data.get("avatar_id", external_data.get("avatar")),
        "alevel": external_data.get("alevel"),
        "age": external_data.get("age"),
        "gender": external_data.get("gender"),
        "country": external_data.get("country"),
        "client_presence": normalize_presence(external_data.get("client_status")),
        "subscription_type": external_data.get("subscription_type"),
        "xp_count": external_data.get("xp_count"),
        "summary": _summary(external_data),
    }
    return {
        "auth": auth,
        "profile": profile,
        # Friends are refreshed through their separately parsed endpoint response.
        "friends": [],
    }
