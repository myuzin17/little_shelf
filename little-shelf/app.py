"""Little Shelf — 친구들이 채워주는 나만의 작은 식물 선반."""
from __future__ import annotations

import html
import logging
import os
import re
import threading
import time

import streamlit as st

import art
from db import ID_RE, SLOTS, DemoStore, SupabaseStore

st.set_page_config(
    page_title="Little Shelf",
    page_icon="🌷",
    layout="centered",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Jua&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Gowun Dodum', sans-serif; }
h1, h2, h3, .ls-title { font-family: 'Jua', sans-serif !important; color: #57483F; font-weight: 400; }
[data-testid="stSidebar"], [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] { display: none; }
.block-container { padding-top: 2rem; max-width: 640px; }

.ls-title { font-size: 2.1rem; text-align: center; margin: 0; line-height: 1.2; }
.ls-sub { text-align: center; color: #8A7667; margin: 2px 0 18px; }
.ls-count { text-align: center; font-family: 'Jua', sans-serif; font-size: 1.3rem; color: #57483F; margin: 10px 0 14px; }
.ls-count b { color: #7C9A74; }

.ls-shelf { background: #F6EADB; border: 10px solid #C69C75; border-radius: 18px;
            padding: 12px 10px 2px; box-shadow: inset 0 4px 14px rgba(87,72,63,.14), 0 6px 0 #A9825E; }
.ls-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
.ls-plank { height: 14px; margin: 0 -10px 12px; border-radius: 3px;
            background: linear-gradient(#D6AF8A, #C69C75); box-shadow: 0 3px 0 rgba(87,72,63,.2); }
a.ls-slot { display: block; aspect-ratio: 1 / 1; border-radius: 12px; text-decoration: none !important; }
a.ls-slot img { width: 100%; height: 100%; object-fit: contain; display: block; transition: transform .15s ease; }
a.ls-slot:hover img { transform: translateY(-4px) scale(1.05); }
a.ls-empty { display: flex; align-items: center; justify-content: center; font-family: 'Jua', sans-serif;
             font-size: 26px; color: rgba(87,72,63,.35); border: 2px dashed rgba(87,72,63,.2); }
a.ls-empty:hover { background: rgba(245,213,220,.55); color: #57483F; }

.ls-card { background: #fff; border: 1px solid #EBDCCB; border-radius: 16px; padding: 16px 20px;
           color: #57483F; margin: 12px 0; }
.ls-msg { font-size: 1.1rem; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.ls-from { text-align: right; color: #8A7667; margin-top: 8px; }
.ls-preview { background: #F6EADB; border-radius: 18px; padding: 8px; text-align: center; }
.ls-preview img { width: 100%; max-width: 300px; }
.ls-samples { display: flex; justify-content: center; gap: 4px; margin: 6px 0 14px; }
.ls-samples img { width: 22%; max-width: 120px; }
a.ls-back { color: #7C9A74 !important; text-decoration: none; font-size: .95rem; }
.stButton > button[kind="primary"] { border-radius: 999px; padding: .5rem 1.4rem; }
</style>
"""

CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


# ---------- 설정 / 저장소 ----------
def _secret(name: str):
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return value or os.environ.get(name)


@st.cache_resource
def get_store():
    url, key = _secret("SUPABASE_URL"), _secret("SUPABASE_SERVICE_KEY")
    if url and key:
        return SupabaseStore(url, key)
    return DemoStore()


@st.cache_resource
def _rate_state():
    return {"lock": threading.Lock(), "events": {}}


def _client_id() -> str:
    try:
        h = st.context.headers
        return h.get("X-Forwarded-For", "").split(",")[0].strip() or h.get("X-Real-Ip", "") or "local"
    except Exception:
        return "local"


def allow(action: str, limit: int, window: int = 3600, min_gap: float = 3.0) -> bool:
    """서버 메모리 기반의 간단한 등록 남용 방지(접속자별 횟수·간격 제한)."""
    state, now = _rate_state(), time.time()
    key = (action, _client_id())
    with state["lock"]:
        if len(state["events"]) > 5000:
            state["events"] = {k: [t for t in v if now - t < window] for k, v in state["events"].items()}
            state["events"] = {k: v for k, v in state["events"].items() if v}
        events = [t for t in state["events"].get(key, []) if now - t < window]
        ok = not (events and now - events[-1] < min_gap) and len(events) < limit
        if ok:
            events.append(now)
        state["events"][key] = events
        return ok


def share_url(shelf_id: str) -> str:
    base = _secret("APP_URL")
    if not base:
        try:
            base = st.context.url.split("?")[0]
        except Exception:
            base = ""
    return f"{base.rstrip('/')}/?shelf={shelf_id}" if base else f"?shelf={shelf_id}"


# ---------- 도우미 ----------
def clean(text: str, limit: int) -> str:
    return CTRL.sub("", (text or "")).strip()[:limit]


def esc(text) -> str:
    return html.escape(str(text), quote=True)


@st.cache_data(show_spinner=False, max_entries=1000)
def plant_uri(container: str, color: str, flowers: tuple, size: int) -> str:
    return art.plant_data_uri(container, color, flowers, size)


def go(shelf_id: str | None = None, slot: int | None = None):
    st.query_params.clear()
    if shelf_id:
        st.query_params["shelf"] = shelf_id
    if slot:
        st.query_params["slot"] = str(slot)
    st.rerun()


def header():
    st.markdown('<p class="ls-title">🌷 Little Shelf</p>'
                '<p class="ls-sub">친구들의 작은 마음이 모이는 곳</p>', unsafe_allow_html=True)


def back_link(shelf_id: str, text: str = "← 선반으로 돌아가기"):
    st.markdown(f'<a class="ls-back" href="?shelf={shelf_id}" target="_self">{text}</a>',
                unsafe_allow_html=True)


def shelf_html(shelf_id: str, gifts: dict) -> str:
    rows = []
    for r in range(4):
        cells = []
        for c in range(5):
            n = r * 5 + c + 1
            href = f"?shelf={shelf_id}&amp;slot={n}"
            gift = gifts.get(n)
            if gift:
                uri = plant_uri(gift["container_type"], gift["container_color"],
                                tuple(gift["flowers"]), 140)
                label = esc(f'{n}번 칸 · {gift["sender_name"]}님의 선물')
                cells.append(f'<a class="ls-slot" href="{href}" target="_self" title="{label}">'
                             f'<img src="{uri}" alt="{label}"></a>')
            else:
                cells.append(f'<a class="ls-slot ls-empty" href="{href}" target="_self" '
                             f'title="{n}번 칸 · 비어 있어요">+</a>')
        rows.append('<div class="ls-row">' + "".join(cells) + '</div><div class="ls-plank"></div>')
    return '<div class="ls-shelf">' + "".join(rows) + "</div>"


# ---------- 화면 ----------
def page_home(store):
    header()
    samples = [("basic_pot", "pink", ("tulip", "daisy")), ("glass_vase", "sky", ("rose", "babys_breath", "leaf")),
               ("striped_pot", "cream", ("cactus",)), ("ribbon_vase", "lavender", ("sunflower", "leaf", "daisy"))]
    imgs = "".join(f'<img src="{plant_uri(c, col, f, 160)}" alt="">' for c, col, f in samples)
    st.markdown(f'<div class="ls-samples">{imgs}</div>', unsafe_allow_html=True)
    st.markdown("친구들이 직접 꾸민 화분과 꽃병이 모여, 나만의 작은 선반이 채워져요. "
                "이름만 적으면 바로 시작할 수 있어요.")

    with st.form("create_shelf"):
        name = st.text_input("내 이름 또는 닉네임", max_chars=15, placeholder="예: 유진")
        submitted = st.form_submit_button("🌱 내 선반 만들기", type="primary")
    if submitted:
        owner = clean(name, 15)
        if not owner:
            st.error("이름이나 닉네임을 입력해 주세요.")
        elif not allow("create_shelf", limit=5, min_gap=2):
            st.warning("선반을 너무 많이 만들었어요. 잠시 후 다시 시도해 주세요.")
        else:
            go(store.create_shelf(owner))
    st.caption("공개 링크를 아는 사람은 누구나 선반과 메시지를 볼 수 있어요. 개인정보는 적지 말아주세요.")


def page_shelf(store, shelf, gifts):
    sid = shelf["id"]
    header()
    st.markdown(f'<h2 style="text-align:center;margin:0">{esc(shelf["owner_name"])}님의 작은 선반</h2>',
                unsafe_allow_html=True)

    flash = st.session_state.pop("flash", None)
    if flash:
        st.toast(flash, icon="🌱")

    filled = len(gifts)
    st.markdown(f'<div class="ls-count"><b>{filled}</b> / {SLOTS} 칸이 채워졌어요</div>', unsafe_allow_html=True)
    st.markdown(shelf_html(sid, gifts), unsafe_allow_html=True)

    if filled >= SLOTS:
        st.success(f"🎉 축하해요! 친구들이 {esc(shelf['owner_name'])}님의 선반을 가득 채웠어요.")
        if not st.session_state.get("celebrated"):
            st.session_state["celebrated"] = True
            st.balloons()
    else:
        st.caption("＋ 칸을 눌러 식물을 선물하고, 채워진 칸을 누르면 메시지를 볼 수 있어요.")

    st.markdown("**🔗 친구들에게 이 링크를 보내주세요**")
    st.code(share_url(sid), language=None)
    if not store.persistent:
        st.caption("데모 모드의 링크는 실제 친구 공유용이 아니에요.")

    with st.expander("칸 번호로 직접 고르기"):
        choices = list(range(1, SLOTS + 1))
        pick = st.selectbox("칸 번호", choices, format_func=lambda n: f"{n}번 " + ("(채워짐)" if n in gifts else "(비어 있음)"))
        if st.button("이 칸 열기"):
            go(sid, pick)


def page_detail(shelf, gifts, slot):
    sid, gift = shelf["id"], gifts[slot]
    back_link(sid)
    header()
    uri = plant_uri(gift["container_type"], gift["container_color"], tuple(gift["flowers"]), 320)
    msg = esc(gift.get("message") or "(메시지 없이 마음만 놓고 갔어요 🌿)")
    st.markdown(
        f'<div class="ls-preview"><img src="{uri}" alt="선물"></div>'
        f'<div class="ls-card"><div class="ls-msg">{msg}</div>'
        f'<div class="ls-from">— {esc(gift["sender_name"])} · {esc(str(gift.get("created_at", ""))[:10])}</div></div>',
        unsafe_allow_html=True,
    )


def page_build(store, shelf, gifts, slot):
    sid = shelf["id"]
    back_link(sid)
    st.markdown(f"## {esc(shelf['owner_name'])}님의 선반 · {slot}번 칸")

    left, right = st.columns(2)
    with right:
        container = st.radio("용기", list(art.CONTAINERS), format_func=lambda k: art.CONTAINERS[k][0])
        color = st.radio("색상", list(art.COLORS), format_func=lambda k: art.COLORS[k][0], horizontal=True)

    _, kind, max_n = art.CONTAINERS[container]
    options = [""] + art.allowed_flowers(container)
    with right:
        picks = [
            st.selectbox(
                f"꽃·식물 {i + 1}", options, index=1 if i == 0 else 0,
                format_func=lambda k: "선택 안 함" if k == "" else art.FLOWERS[k],
                key=f"fl_{kind}_{i}",
            )
            for i in range(max_n)
        ]
        st.caption(f"{'화분은 2개' if kind == 'pot' else '꽃병은 3개'}까지 담을 수 있어요.")
    flowers = [p for p in picks if p]

    with left:
        uri = plant_uri(container, color, tuple(flowers), 300)
        st.markdown(f'<div class="ls-preview"><img src="{uri}" alt="미리보기"></div>', unsafe_allow_html=True)

    sender = st.text_input("보내는 사람 닉네임 (최대 15자)", max_chars=15, key="sender")
    message = st.text_area("메시지 (최대 100자)", max_chars=100, height=100, key="message",
                           placeholder="예: 생일 축하해! 항상 잘 자라길 ✿")
    st.caption("공개 링크를 아는 사람은 메시지를 볼 수 있어요. 전화번호·주소 같은 개인정보는 적지 말아주세요.")

    if st.button("🌱 선반에 놓기", type="primary"):
        sender_c, message_c = clean(sender, 15), clean(message, 100)
        if not sender_c:
            st.error("닉네임을 입력해 주세요.")
        elif not flowers:
            st.error("꽃이나 식물을 하나 이상 골라주세요.")
        elif not allow("add_gift", limit=20, min_gap=3):
            st.warning("너무 빠르게 요청하고 있어요. 잠시 후 다시 시도해 주세요.")
        elif slot in store.list_gifts(sid):  # 저장 직전에 한 번 더 확인
            st.warning("앗, 방금 다른 친구가 이 칸을 채웠어요. 다른 칸을 골라주세요.")
        else:
            result = store.add_gift(sid, slot, sender_c, container, color, flowers, message_c)
            if result == "ok":
                st.session_state["flash"] = f"{slot}번 칸에 식물을 놓았어요!"
                go(sid)
            else:  # DB UNIQUE 충돌: 동시에 같은 칸을 고른 경우
                st.warning("앗, 방금 다른 친구가 이 칸을 채웠어요. 다른 칸을 골라주세요.")


def not_found():
    header()
    st.warning("이 선반을 찾을 수 없어요. 링크가 맞는지 확인해 주세요.")
    st.markdown('<a class="ls-back" href="/" target="_self">← 새 선반 만들러 가기</a>', unsafe_allow_html=True)


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        store = get_store()
    except Exception:
        logging.exception("DB 연결 실패")
        st.error("데이터베이스에 연결하지 못했어요. Supabase 설정(secrets)을 확인해 주세요.")
        st.stop()

    if not store.persistent:
        st.info("🧪 **데모 모드** — 데이터가 이 서버의 메모리에만 임시로 저장돼요. 서버를 재시작하면 사라지고, "
                "실제 친구 공유·영구 저장은 Supabase를 연결해야 가능해요.")

    params = st.query_params
    sid = params.get("shelf", "")
    if not sid:
        return page_home(store)
    if not ID_RE.match(sid):
        return not_found()

    try:
        shelf = store.get_shelf(sid)
        if shelf is None:
            return not_found()
        gifts = store.list_gifts(sid)
        raw = params.get("slot", "")
        slot = int(raw) if raw.isdigit() and 1 <= int(raw) <= SLOTS else None

        if slot is None:
            page_shelf(store, shelf, gifts)
        elif slot in gifts:
            page_detail(shelf, gifts, slot)
        else:
            page_build(store, shelf, gifts, slot)
    except Exception:
        logging.exception("화면을 그리는 중 오류")
        st.error("잠시 문제가 생겼어요. 새로고침 후 다시 시도해 주세요.")


main()
