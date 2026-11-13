"""저장소 계층.

SupabaseStore : 실제 서비스용. 여러 사용자가 같은 선반을 공유하고 영구 저장됩니다.
DemoStore     : 개발용 임시 저장. 서버 프로세스 메모리에만 있어 재시작하면 사라집니다.
두 클래스는 같은 메서드를 가지므로 app.py는 어느 쪽인지 신경 쓰지 않습니다.
"""
from __future__ import annotations

import re
import secrets
import threading
from datetime import datetime, timezone

SLOTS = 20
ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")


def new_shelf_id() -> str:
    return secrets.token_urlsafe(8)  # 11자, 추측하기 어려운 링크용 ID


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_unique_violation(exc: Exception) -> bool:
    text = str(exc).lower()
    return getattr(exc, "code", None) == "23505" or "23505" in text or "duplicate key" in text


class DemoStore:
    persistent = False

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._shelves: dict[str, dict] = {}
        self._gifts: dict[str, dict[int, dict]] = {}

    def create_shelf(self, owner_name: str) -> str:
        with self._lock:
            sid = new_shelf_id()
            self._shelves[sid] = {"id": sid, "owner_name": owner_name, "created_at": _now()}
            self._gifts[sid] = {}
            return sid

    def get_shelf(self, shelf_id: str):
        return self._shelves.get(shelf_id)

    def list_gifts(self, shelf_id: str) -> dict[int, dict]:
        with self._lock:
            return dict(self._gifts.get(shelf_id, {}))

    def add_gift(self, shelf_id, slot, sender_name, container_type,
                 container_color, flowers, message) -> str:
        with self._lock:
            gifts = self._gifts.get(shelf_id)
            if gifts is None:
                raise KeyError("shelf not found")
            if slot in gifts:
                return "taken"
            gifts[slot] = {
                "shelf_id": shelf_id, "slot_number": slot, "sender_name": sender_name,
                "container_type": container_type, "container_color": container_color,
                "flowers": list(flowers), "message": message, "created_at": _now(),
            }
            return "ok"


class SupabaseStore:
    persistent = True

    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client  # 데모 모드에서는 설치되어 있지 않아도 됨

        self.client = create_client(url, key)

    def create_shelf(self, owner_name: str) -> str:
        sid = new_shelf_id()
        self.client.table("shelves").insert({"id": sid, "owner_name": owner_name}).execute()
        return sid

    def get_shelf(self, shelf_id: str):
        res = (self.client.table("shelves").select("*")
               .eq("id", shelf_id).limit(1).execute())
        return res.data[0] if res.data else None

    def list_gifts(self, shelf_id: str) -> dict[int, dict]:
        res = (self.client.table("gifts").select("*")
               .eq("shelf_id", shelf_id).order("slot_number").execute())
        return {g["slot_number"]: g for g in res.data}

    def add_gift(self, shelf_id, slot, sender_name, container_type,
                 container_color, flowers, message) -> str:
        row = {
            "shelf_id": shelf_id, "slot_number": slot, "sender_name": sender_name,
            "container_type": container_type, "container_color": container_color,
            "flowers": list(flowers), "message": message,
        }
        try:
            self.client.table("gifts").insert(row).execute()
        except Exception as exc:  # (shelf_id, slot_number) UNIQUE 충돌 = 동시에 같은 칸을 고른 경우
            if _is_unique_violation(exc):
                return "taken"
            raise
        return "ok"
