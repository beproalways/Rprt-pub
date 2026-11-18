"""
Telegram Report Plugin (Telethon userbot)

Master ID: 8679127662

Usage:
    .report <link>
        .report t.me/channelname
        .report t.me/channelname/123
        .report t.me/c/1234567890/123

Flow:
    1. Category  -> send number (1-6) or name
    2. Reason    -> send reason text
    3. Personal  -> send personal data string (name, phone, address etc.)
    4. Review    -> send "confirm" to submit or "cancel" to abort

Reports 50x per .report command from your account.
"""

import asyncio
import inspect
import re
import time

from telethon import events, functions, types
from telethon.errors import FloodWaitError, RPCError


MASTER_ID = 8679127662
SESSION_TIMEOUT = 300
REPORT_COUNT = 50
REPORT_DELAY = 0.4

_registered = False
_sessions = {}
_own = set()

try:
    _NEW_API = "option" in inspect.signature(
        functions.messages.ReportRequest.__init__
    ).parameters
except Exception:
    _NEW_API = False


CATEGORIES = [
    {
        "name": "Spam",
        "reason": types.InputReportReasonSpam,
        "keywords": ("spam",),
        "aliases": ("spam",),
    },
    {
        "name": "Violence",
        "reason": types.InputReportReasonViolence,
        "keywords": ("violence",),
        "aliases": ("violence",),
    },
    {
        "name": "Child abuse",
        "reason": types.InputReportReasonChildAbuse,
        "keywords": ("child",),
        "aliases": ("child", "child abuse", "childabuse"),
    },
    {
        "name": "Illegal drugs / goods",
        "reason": types.InputReportReasonIllegalDrugs,
        "keywords": ("drug", "illegal"),
        "aliases": ("drugs", "drug", "illegal", "illegal drugs", "illegal goods"),
    },
    {
        "name": "Pornography",
        "reason": types.InputReportReasonPornography,
        "keywords": ("porn",),
        "aliases": ("porn", "pornography"),
    },
    {
        "name": "Other",
        "reason": types.InputReportReasonOther,
        "keywords": ("other",),
        "aliases": ("other",),
    },
]


async def _say(event, text):
    sent = await event.reply(text)
    if len(_own) > 1000:
        _own.clear()
    _own.add((sent.chat_id, sent.id))
    return sent


_LINK_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/(.+)$", re.IGNORECASE
)


def _parse_link(text):
    text = text.strip()
    match = _LINK_RE.match(text)
    if match:
        path = match.group(1)
    elif text.startswith("@"):
        path = text[1:]
    else:
        return None

    path = path.split("?")[0].strip("/")
    parts = [p for p in path.split("/") if p]
    if not parts:
        return None

    if parts[0].startswith("+") or parts[0].lower() == "joinchat":
        return "invite"

    last_is_msg = len(parts) >= 2 and parts[-1].isdigit()
    msg_id = int(parts[-1]) if last_is_msg else None

    if parts[0].lower() == "c":
        if len(parts) < 2 or not parts[1].isdigit():
            return None
        return {"peer": types.PeerChannel(int(parts[1])), "msg_id": msg_id}

    return {"peer": parts[0], "msg_id": msg_id}


def _match_category(text):
    text = text.strip().lower()
    if text.isdigit():
        index = int(text) - 1
        if 0 <= index < len(CATEGORIES):
            return CATEGORIES[index]
        return None
    for cat in CATEGORIES:
        if text in cat["aliases"]:
            return cat
    return None


def _category_menu():
    lines = ["📂 Which category?", ""]
    for i, cat in enumerate(CATEGORIES, start=1):
        lines.append(f"{i}. {cat['name']}")
    lines.append("")
    lines.append('Send the number or the name. "cancel" to abort.')
    return "\n".join(lines)


def _review_card(session):
    return (
        "📋 REPORT REVIEW\n\n"
        f"🔗 Target: {session['link']}\n"
        f"📂 Category: {session['category']['name']}\n"
        f"📝 Reason: {session['reason']}\n"
        f"👤 Personal data: {session['personal_data']}\n"
        f"🔁 Count: {REPORT_COUNT} reports\n\n"
        'Reply "confirm" to submit all\n'
        'Reply "cancel" to abort'
    )


def _build_message(reason, personal_data, index):
    base = reason
    if personal_data:
        base += (
            f"\n\n--- Reported by user (personal identification) ---\n"
            f"{personal_data}\n"
            f"--- Report #{index} of {REPORT_COUNT} ---"
        )
    else:
        base += f"\n\n--- Report #{index} of {REPORT_COUNT} ---"
    return base[:512]


def _pick_option(options, category):
    for opt in options:
        text = (opt.text or "").lower()
        if any(key in text for key in category["keywords"]):
            return opt
    for opt in options:
        if "other" in (opt.text or "").lower():
            return opt
    return options[0]


async def _submit_once(client, session, index):
    peer = session["input_peer"]
    msg_id = session["msg_id"]
    category = session["category"]
    message = _build_message(session["reason"], session["personal_data"], index)

    if msg_id is None:
        await client(
            functions.account.ReportPeerRequest(
                peer=peer,
                reason=category["reason"](),
                message=message,
            )
        )
        return True

    if not _NEW_API:
        await client(
            functions.messages.ReportRequest(
                peer=peer,
                id=[msg_id],
                reason=category["reason"](),
                message=message,
            )
        )
        return True

    option = b""
    for _ in range(6):
        result = await client(
            functions.messages.ReportRequest(
                peer=peer,
                id=[msg_id],
                option=option,
                message=message,
            )
        )
        kind = type(result).__name__

        if kind == "ReportResultReported":
            return True
        if kind == "ReportResultAddComment":
            option = result.option
            continue
        if kind == "ReportResultChooseOption":
            option = _pick_option(result.options, category).option
            continue
        return False

    return False


async def _submit_all(client, event, session):
    success = 0
    flood_waits = 0
    errors = []

    progress_msg = await _say(event, f"⏳ Sending reports... 0/{REPORT_COUNT}")

    for i in range(1, REPORT_COUNT + 1):
        try:
            ok = await _submit_once(client, session, i)
            if ok:
                success += 1
        except FloodWaitError as exc:
            flood_waits += 1
            wait = min(exc.seconds, 30)
            await asyncio.sleep(wait)
            try:
                ok = await _submit_once(client, session, i)
                if ok:
                    success += 1
            except Exception as e2:
                errors.append(f"#{i}: {type(e2).__name__}")
        except RPCError as exc:
            errors.append(f"#{i}: {type(exc).__name__}")
        except Exception as exc:
            errors.append(f"#{i}: {type(exc).__name__}: {exc}")

        if i % 5 == 0 or i == REPORT_COUNT:
            try:
                await progress_msg.edit(
                    f"⏳ Sending reports... {i}/{REPORT_COUNT} (✅ {success} sent)"
                )
            except Exception:
                pass

        if i < REPORT_COUNT:
            await asyncio.sleep(REPORT_DELAY)

    summary_lines = [
        "📊 REPORT SUMMARY",
        "",
        f"✅ Sent: {success}/{REPORT_COUNT}",
        f"🌊 FloodWaits hit: {flood_waits}",
    ]
    if errors:
        summary_lines.append(f"❌ Errors: {len(errors)}")
        summary_lines.extend(errors[:10])

    try:
        await progress_msg.edit("\n".join(summary_lines))
    except Exception:
        await _say(event, "\n".join(summary_lines))


async def _start_session(client, event, arg):
    parsed = _parse_link(arg)

    if parsed == "invite":
        await _say(
            event,
            "❌ Invite links can't be reported directly. Use a public or message link.",
        )
        return

    if parsed is None:
        await _say(
            event,
            "❌ Couldn't parse that link.\n\n"
            "Examples:\n"
            ".report t.me/channelname\n"
            ".report t.me/channelname/123",
        )
        return

    try:
        input_peer = await client.get_input_entity(parsed["peer"])
        entity = await client.get_entity(input_peer)
    except Exception as exc:
        await _say(event, f"❌ Couldn't find that chat: {type(exc).__name__}")
        return

    msg_id = parsed["msg_id"]
    if msg_id is not None:
        try:
            message = await client.get_messages(input_peer, ids=msg_id)
        except Exception:
            message = None
        if not message:
            await _say(event, "❌ That message wasn't found.")
            return

    title = (
        getattr(entity, "title", None)
        or getattr(entity, "username", None)
        or getattr(entity, "first_name", None)
        or "unknown"
    )

    _sessions[event.chat_id] = {
        "step": "category",
        "link": arg.strip(),
        "input_peer": input_peer,
        "msg_id": msg_id,
        "category": None,
        "reason": None,
        "personal_data": "",
        "last": time.time(),
    }

    what = "message" if msg_id is not None else "chat"
    await _say(
        event,
        f"🎯 Target {what}: {title}\n"
        f"🔁 Will send {REPORT_COUNT} reports.\n\n"
        f"{_category_menu()}",
    )


async def _handler(event, client):
    if getattr(event, "sender_id", None) != MASTER_ID:
        return

    chat_id = event.chat_id
    if (chat_id, event.id) in _own:
        return

    text = (event.raw_text or "").strip()
    if not text:
        return

    low = text.lower()
    parts = text.split(None, 1)

    if parts[0].lower() == ".report":
        if len(parts) < 2:
            await _say(
                event,
                "Usage: .report <link>\nExample: .report t.me/channelname/123",
            )
            return
        _sessions.pop(chat_id, None)
        await _start_session(client, event, parts[1])
        return

    session = _sessions.get(chat_id)
    if not session:
        return

    if time.time() - session["last"] > SESSION_TIMEOUT:
        _sessions.pop(chat_id, None)
        await _say(event, "⌛ Session expired. Use .report <link> again.")
        return

    session["last"] = time.time()

    if low == "cancel":
        _sessions.pop(chat_id, None)
        await _say(event, "🚫 Report cancelled.")
        return

    if session["step"] == "category":
        cat = _match_category(text)
        if not cat:
            await _say(event, "❌ Invalid category.\n\n" + _category_menu())
            return
        session["category"] = cat
        session["step"] = "reason"
        await _say(event, f"✅ Category: {cat['name']}\n\n📝 Send the reason text.")
        return

    if session["step"] == "reason":
        session["reason"] = text
        session["step"] = "personal_data"
        await _say(
            event,
            "✅ Reason saved.\n\n"
            "👤 Now send personal data to embed in the report\n"
            "(name, phone, address, ID number, etc.)\n\n"
            '"skip" to leave empty.',
        )
        return

    if session["step"] == "personal_data":
        session["personal_data"] = "" if low == "skip" else text
        session["step"] = "confirm"
        await _say(event, _review_card(session))
        return

    if session["step"] == "confirm":
        if low != "confirm":
            await _say(event, 'Reply "confirm" to submit or "cancel" to abort.')
            return
        s = _sessions.pop(chat_id)
        await _submit_all(client, event, s)


def init(client):
    global _registered
    if _registered:
        return
    _registered = True

    async def handler(event):
        await _handler(event, client)

    client.add_event_handler(handler, events.NewMessage())

    print(
        "[report-plugin] Loaded | "
        f"master={MASTER_ID} | "
        f"count={REPORT_COUNT} | "
        f"api={'option-flow' if _NEW_API else 'reason-flow'}"
    )
