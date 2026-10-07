"""Standalone Camfrog Status Changer — no camfrog_auto dependency."""
import copy
import ctypes
import datetime as dt
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import time
import unicodedata
import queue
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional, Union


class SingleInstanceGuard:
    """Prevent multiple GUI instances using a Windows named mutex.

    On non-Windows platforms, always allows the instance to run.
    If another instance exists, restores it instead of showing an error.
    """

    ERROR_ALREADY_EXISTS = 183
    WM_SHOWME = 0x8000 + 42  # Custom message to restore window

    def __init__(self, name: str = "CamfrogStatusChanger"):
        self.name = name
        self.handle = None
        self.kernel32 = None
        self.user32 = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
        self.kernel32.CreateMutexW.restype = ctypes.c_void_p
        self.kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        self.kernel32.CloseHandle.restype = ctypes.c_int
        ctypes.set_last_error(0)
        mutex_name = f"Local\\{self.name}"
        self.handle = self.kernel32.CreateMutexW(None, False, mutex_name)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), f"Could not create mutex {mutex_name}")
        if ctypes.get_last_error() == self.ERROR_ALREADY_EXISTS:
            # Another instance exists - try to restore it
            self._restore_existing_instance()
            return False
        return True

    def _restore_existing_instance(self):
        """Find the existing window and send a restore message."""
        if os.name != "nt":
            return
        try:
            self.user32 = ctypes.WinDLL("user32", use_last_error=True)
            # Find window by class name (TkTopLevel) and title containing our app name
            # The first instance registers a window class we can find
            self.user32.EnumWindows.argtypes = (ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p), ctypes.c_void_p)
            self.user32.EnumWindows.restype = ctypes.c_int
            self.user32.GetWindowTextW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int)
            self.user32.GetWindowTextW.restype = ctypes.c_int
            self.user32.GetClassNameW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int)
            self.user32.GetClassNameW.restype = ctypes.c_int
            self.user32.PostMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
            self.user32.PostMessageW.restype = ctypes.c_int

            def enum_callback(hwnd, lparam):
                try:
                    length = self.user32.GetWindowTextW(hwnd, ctypes.create_unicode_buffer(256), 256)
                    if length > 0:
                        title = ctypes.create_unicode_buffer(256)
                        self.user32.GetWindowTextW(hwnd, title, 256)
                        if "Camfrog Status Changer" in title.value:
                            # Found it - send restore message
                            self.user32.PostMessageW(hwnd, self.WM_SHOWME, 0, 0)
                            return False  # Stop enumeration
                except Exception:
                    pass
                return True  # Continue enumeration

            callback = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(enum_callback)
            self.user32.EnumWindows(callback, 0)
        except Exception:
            pass  # Best effort

    def release(self):
        if self.handle and self.kernel32:
            self.kernel32.CloseHandle(self.handle)
        self.handle = None

# ---------- Inlined Constants and Functions ----------
BASE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent

NICK_RE = re.compile(r"^[\w][\w .\-]{0,31}$", re.UNICODE)

LINE_RE = re.compile(r"^(?P<nick>[^:\r\n]{1,32}):\s(?P<msg>.+)$")

CTRL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

THAI_RE = re.compile(r"[\u0e00-\u0e7f]")

log = logging.getLogger("camfrog_auto")

LOG_TEXT = True

LANG = "en"

S = {
    "cfg_ok": ("config OK", "คอนฟิกถูกต้อง"),
    "cfg_errs": ("{n} error(s)", "พบข้อผิดพลาด {n} รายการ"),
    "cfg_hint": ("config errors (run `check`):", "คอนฟิกมีข้อผิดพลาด (รัน `check`):"),
    "cannot_load": ("cannot load config: {e}  (try `init` to create one)", "อ่านคอนฟิกไม่ได้: {e}  (ลองรัน `init` เพื่อสร้างใหม่)"),
    "warn": ("WARN : {m}", "คำเตือน: {m}"),
    "err": ("ERROR: {m}", "ผิดพลาด: {m}"),
    "e_regex": ("window_title_regex invalid: {e}", "window_title_regex ไม่ถูกต้อง: {e}"),
    "e_hours": ("active_hours start/end must be HH:MM", "active_hours start/end ต้องเป็นรูปแบบ HH:MM"),
    "e_msgs": ("status.messages is empty", "status.messages ว่างเปล่า"),
    "e_interval": ("status.interval_seconds must be >= 30", "status.interval_seconds ต้องไม่น้อยกว่า 30"),
    "e_sel": ("{k} must be a selector object", "{k} ต้องเป็น object ของ selector"),
    "e_delay": ("autoreply.delay_range_seconds must be [min, max] with 0 <= min <= max",
                "autoreply.delay_range_seconds ต้องเป็น [min, max] โดย 0 <= min <= max"),
    "e_hour": ("autoreply.max_per_hour must be >= 1", "autoreply.max_per_hour ต้องไม่น้อยกว่า 1"),
    "e_cool": ("autoreply cooldowns must be >= 0", "ค่า cooldown ของ autoreply ต้องไม่ติดลบ"),
    "e_rule": ("autoreply.rules[{i}] invalid: {e}", "autoreply.rules[{i}] ไม่ถูกต้อง: {e}"),
    "e_reply": ("autoreply.rules[{i}] has no reply", "autoreply.rules[{i}] ไม่มี reply"),
    "e_struct": ("config has a wrong value type or missing section: {e}",
                 "คอนฟิกมีชนิดข้อมูลผิดหรือขาดส่วนที่จำเป็น: {e}"),
    "e_lang": ("language must be auto, th or en", "language ต้องเป็น auto, th หรือ en"),
    "e_mode": ("status.language_mode must be th, en, both or alternate",
               "status.language_mode ต้องเป็น th, en, both หรือ alternate"),
    "w_norules": ("autoreply.rules is empty (nothing will be replied)",
                  "autoreply.rules ว่างเปล่า (จะไม่มีการตอบ)"),
    "w_nick": ("autoreply.own_nickname is empty (required for live mode)",
               "autoreply.own_nickname ว่าง (จำเป็นเมื่อรันจริง)"),
    "w_live": ("dry_run is false: messages WILL be sent", "dry_run เป็น false: จะส่งข้อความจริง"),
    "dry_send": ("[dry-run] would send: {text}", "[ทดลอง] จะส่ง: {text}"),
    "mismatch": ("read-back mismatch; not sending", "ข้อความที่อ่านกลับไม่ตรง จึงไม่ส่ง"),
    "not_fg": ("Camfrog not foreground; not sending", "Camfrog ไม่ได้อยู่หน้าสุด จึงไม่ส่ง"),
    "no_window": ("Camfrog window not found (check window_title_regex)",
                  "ไม่พบหน้าต่าง Camfrog (ตรวจ window_title_regex)"),
    "no_ctrl": ("control not found: {spec} (matches={n})", "ไม่พบ control: {spec} (พบ {n} รายการ)"),
    "status_set": ("status set: {text}", "ตั้ง status แล้ว: {text}"),
    "status_fail": ("status commit failed", "ตั้ง status ไม่สำเร็จ"),
    "reply_fail": ("reply commit failed", "ส่งข้อความตอบไม่สำเร็จ"),
    "replied": ("replied to {nick}: {text}", "ตอบ {nick} แล้ว: {text}"),
    "refuse_live": ("refusing to run live: set autoreply.own_nickname first",
                    "ไม่ยอมรันจริง: ตั้ง autoreply.own_nickname ก่อน"),
    "running": ("running (dry_run={dry}). Stop: Ctrl+C or `stop` / {stop}",
                "กำลังทำงาน (dry_run={dry}) หยุดด้วย Ctrl+C หรือคำสั่ง `stop` / ไฟล์ {stop}"),
    "stopped": ("stopped", "หยุดทำงานแล้ว"),
    "interrupted": ("interrupted", "ถูกขัดจังหวะ"),
    "fatal": ("fatal error", "เกิดข้อผิดพลาดร้ายแรง"),
    "tick_failed": ("tick failed ({n}/{m})", "รอบทำงานล้มเหลว ({n}/{m})"),
    "too_many": ("too many consecutive failures; stopping", "ล้มเหลวติดต่อกันมากเกินไป จึงหยุด"),
    "re_resolve": ("re-attach failed: {e}", "จับหน้าต่างใหม่ไม่สำเร็จ: {e}"),
    "discover_done": ("wrote {p}. Copy auto_id/class_name/index into config.json selectors.",
                      "เขียนไฟล์ {p} แล้ว คัดลอก auto_id/class_name/index ไปใส่ selector ใน config.json"),
    "win_hdr": ("visible windows (title | class | PID); * = matches window_title_regex:",
                "หน้าต่างที่เห็น (ชื่อ | class | PID) เครื่องหมาย * = ตรงกับ window_title_regex:"),
    "win_none": ("no visible windows found", "ไม่พบหน้าต่างที่มองเห็น"),
    "win_hint": ("Camfrog not listed? Open it (not minimized to tray) and run as the same user / same admin level. "
                 "If its title has no 'Camfrog', set window_title_regex in config.json to part of the title above.",
                 "ไม่เห็น Camfrog? เปิดโปรแกรมให้เห็นหน้าต่าง (ไม่ซ่อนในถาดระบบ) และรันด้วยผู้ใช้/สิทธิ์ระดับเดียวกัน "
                 "ถ้าชื่อหน้าต่างไม่มีคำว่า Camfrog ให้แก้ window_title_regex ใน config.json เป็นส่วนหนึ่งของชื่อด้านบน"),
    "det_none": ("detect: found no candidate controls. Open a chat room (not tray-minimized) and retry.",
                 "detect: ไม่พบ control ที่ใช่ เปิดห้องแชทให้เห็นหน้าต่างแล้วลองใหม่"),
    "det_found": ("detect: {k} -> {sel}  [{why}]", "detect: {k} -> {sel}  [{why}]"),
    "det_miss": ("detect: {k} not found", "detect: ไม่พบ {k}"),
    "det_applied": ("detect: wrote selectors to {p}. Run `check`, then test with dry_run on.",
                    "detect: เขียน selector ลง {p} แล้ว รัน `check` แล้วทดสอบด้วย dry_run"),
    "det_report": ("detect: structure report (no chat text) -> {p}", "detect: รายงานโครงสร้าง (ไม่มีข้อความแชท) -> {p}"),
    "no_room": ("no chat-room window yet (status still works). Open a room; it is picked up automatically.",
                "ยังไม่พบหน้าต่างห้องแชท (ตั้ง status ได้ตามปกติ) เปิดห้องแชทแล้วจะจับให้เอง"),
    "room_attached": ("attached to chat room window {title}", "จับหน้าต่างห้องแชทแล้ว {title}"),
    "ok": ("ok", "สำเร็จ"),
    "failed": ("failed", "ล้มเหลว"),
    "already_running": ("already running (PID {pid})", "ทำงานอยู่แล้ว (PID {pid})"),
    "bg_started": ("started in background (PID {pid}). Log: {log}",
                   "เริ่มทำงานเบื้องหลังแล้ว (PID {pid}) ล็อก: {log}"),
    "bg_failed": ("background process exited (code {code}). See log: {log}",
                  "โปรเซสเบื้องหลังจบการทำงาน (code {code}) ดูล็อก: {log}"),
    "bg_needs_log": ("background mode needs log.file set in config",
                     "โหมดเบื้องหลังต้องตั้ง log.file ใน config"),
    "win_only": ("this command is Windows-only", "คำสั่งนี้ใช้ได้เฉพาะ Windows"),
    "not_running": ("not running", "ไม่ได้ทำงานอยู่"),
    "stopping": ("stopping PID {pid} ...", "กำลังหยุด PID {pid} ..."),
    "stopped_ok": ("stopped", "หยุดแล้ว"),
    "killed": ("did not stop in time; terminated", "หยุดไม่ทันเวลา จึงบังคับปิด"),
    "stop_failed": ("could not confirm process exit (PID {pid}); STOP and PID files were kept so you can retry",
                    "ยืนยันไม่ได้ว่าโปรเซสหยุดแล้ว (PID {pid}) จึงเก็บไฟล์ STOP/PID ไว้ให้ลองใหม่"),
    "state_running": ("RUNNING (PID {pid})", "กำลังทำงาน (PID {pid})"),
    "state_stopped": ("STOPPED", "หยุดอยู่"),
    "autostart_on": ("autostart enabled: {cmd}", "เปิดการรันอัตโนมัติแล้ว: {cmd}"),
    "autostart_off": ("autostart removed", "ยกเลิกการรันอัตโนมัติแล้ว"),
    "autostart_none": ("autostart was not set", "ไม่ได้ตั้งการรันอัตโนมัติไว้"),
    "e_sched": ("status.schedules[{i}] invalid (needs start/end HH:MM and non-empty messages)",
                "status.schedules[{i}] ไม่ถูกต้อง (ต้องมี start/end แบบ HH:MM และ messages ไม่ว่าง)"),
    "e_skip": ("autoreply.skip_patterns[{i}] invalid: {e}", "autoreply.skip_patterns[{i}] ไม่ถูกต้อง: {e}"),
    "w_mention": ("rule #{i} uses `mention` but own_nickname is empty (it will never match)",
                  "กฎ #{i} ใช้ `mention` แต่ own_nickname ว่าง (จะไม่ตรงเลย)"),
    "reloaded": ("config reloaded", "โหลดคอนฟิกใหม่แล้ว"),
    "reload_rejected": ("config reload rejected: {m}", "ไม่รับคอนฟิกที่แก้ใหม่: {m}"),
    "init_done": ("wrote {p}", "สร้างไฟล์ {p} แล้ว"),
    "init_exists": ("{p} already exists (use --force to overwrite)", "{p} มีอยู่แล้ว (ใช้ --force เพื่อเขียนทับ)"),
    "tr_lang": ("detected language: {l}", "ภาษาที่ตรวจพบ: {l}"),
    "tr_skip": ("SKIPPED ({why})", "ข้าม ({why})"),
    "tr_match": ("rule #{i} -> {reply}", "กฎ #{i} -> {reply}"),
    "tr_none": ("no rule matches", "ไม่มีกฎที่ตรง"),
    "tr_blocked": ("(blocked: empty or starts with /)", "(ถูกบล็อก: ว่างหรือขึ้นต้นด้วย /)"),
    "tr_badline": ("ignored line (not `name: message`): {line}", "ข้ามบรรทัด (ไม่ใช่รูปแบบ `ชื่อ: ข้อความ`): {line}"),
    "why_sender": ("sender filtered", "กรองผู้ส่ง"),
    "why_link": ("contains a link", "มีลิงก์"),
    "why_pattern": ("matches skip_patterns", "ตรงกับ skip_patterns"),
    "e_marquee": ("status.marquee invalid: width 8-80 (and <= status.max_length), stride 1..width, step_seconds >= 0.5, cycles 1-5, max_frames 5-300",
                  "status.marquee ไม่ถูกต้อง: width 8-80 (และไม่เกิน status.max_length), stride 1..width, step_seconds >= 0.5, cycles 1-5, max_frames 5-300"),
    "e_cycle": ("status.language_cycle items must be th or en", "status.language_cycle ต้องเป็น th หรือ en เท่านั้น"),
    "e_hmode": ("status.history.mode must be rotate, random or most_used", "status.history.mode ต้องเป็น rotate, random หรือ most_used"),
    "e_hmax": ("status.history.max_items must be 5-500 and file must be set", "status.history.max_items ต้อง 5-500 และต้องตั้ง file"),
    "w_sched_hist": ("status.schedules are ignored while status.history.use_as_source is true",
                     "status.schedules จะไม่ถูกใช้ขณะที่ status.history.use_as_source เป็น true"),
    "status_blank": ("chosen status is blank; skipped", "status ที่เลือกว่างเปล่า จึงข้าม"),
    "hist_empty": ("history is empty", "ประวัติว่างเปล่า"),
    "hist_item": ("{i:>3}. [{lang}] x{n}  {text}", "{i:>3}. [{lang}] ใช้ {n} ครั้ง  {text}"),
    "hist_added": ("added to history", "เพิ่มเข้าประวัติแล้ว"),
    "hist_exists": ("already in history (or blank)", "มีในประวัติแล้ว (หรือข้อความว่าง)"),
    "hist_imported": ("imported {n} new status(es)", "นำเข้า status ใหม่ {n} รายการ"),
    "mq_frames": ("{n} frame(s), {s}s apart -> about {t}s total", "{n} เฟรม ห่างกัน {s} วินาที -> รวมประมาณ {t} วินาที"),
    "mq_static": ("text fits in the window: no scrolling, shown as-is", "ข้อความสั้นพอดีหน้าต่าง: ไม่เลื่อน แสดงตามเดิม"),
    "e_range": ("{k} is out of range ({lo}..{hi})", "{k} อยู่นอกช่วงที่ยอมรับ ({lo}..{hi})"),
    "w_selclash": ("selectors {a} and {b} are identical: they point at the same control (run `discover`)",
                   "selector {a} กับ {b} เหมือนกัน คือ control ตัวเดียวกัน (รัน `discover`)"),
    "e_selclash": ("live mode refused: selectors {a} and {b} are identical (run `discover` and fix config.json)",
                   "ไม่ยอมรันจริง: selector {a} กับ {b} เหมือนกัน (รัน `discover` แล้วแก้ config.json)"),
    "burst_skip": ("{n} new chat lines at once (room switch / history reload?): not answered",
                   "มีข้อความใหม่ {n} บรรทัดพร้อมกัน (เปลี่ยนห้อง/โหลดประวัติ?) จึงไม่ตอบ"),
    "e_selempty": ("{k} has no criteria (set control_type, auto_id, class_name or title)",
                   "{k} ไม่มีเงื่อนไขเลย (ใส่ control_type, auto_id, class_name หรือ title)"),
    "e_im_only": ("autoreply_im.only_nicknames must list at least one friend (IM auto-reply never answers 'everyone')",
                  "autoreply_im.only_nicknames ต้องระบุเพื่อนอย่างน้อย 1 คน (ตอบ IM แบบ 'ทุกคน' ไม่ได้)"),
    "e_im_nick": ("autoreply_im needs autoreply.own_nickname (otherwise the bot would answer its own replies)",
                  "autoreply_im ต้องตั้ง autoreply.own_nickname (ไม่งั้นบอทจะตอบตัวเอง)"),
    "e_im_kind": ("autoreply.log_kind must be room while autoreply_im is enabled (room rules must never answer private chats)",
                  "autoreply.log_kind ต้องเป็น room ขณะเปิด autoreply_im (กฎห้องห้ามตอบแชทส่วนตัว)"),
    "e_im_prefix": ("autoreply_im.prefix must be text and must not start with /",
                    "autoreply_im.prefix ต้องเป็นข้อความและห้ามขึ้นต้นด้วย /"),
    "e_im_rule": ("autoreply_im.rules[{i}] invalid: {e}", "autoreply_im.rules[{i}] ไม่ถูกต้อง: {e}"),
    "e_im_skip": ("autoreply_im.skip_patterns[{i}] invalid: {e}", "autoreply_im.skip_patterns[{i}] ไม่ถูกต้อง: {e}"),
    "e_im_delay": ("autoreply_im.delay_range_seconds must be [min, max] with 0 <= min <= max",
                   "autoreply_im.delay_range_seconds ต้องเป็น [min, max] โดย 0 <= min <= max"),
    "w_im_norules": ("autoreply_im has no rules: nothing will be answered", "autoreply_im ไม่มีกฎ: จะไม่ตอบอะไรเลย"),
    "w_im_noprefix": ("autoreply_im.prefix is empty: friends cannot tell the reply is automatic",
                      "autoreply_im.prefix ว่าง: เพื่อนจะไม่รู้ว่าเป็นข้อความตอบอัตโนมัติ"),
    "im_attached": ("attached to private-chat window {title}", "จับหน้าต่างแชทส่วนตัวแล้ว {title}"),
    "im_replied": ("IM reply to {nick}: {text}", "ตอบ IM {nick} แล้ว: {text}"),
    "refuse_im": ("refusing to run: autoreply_im needs autoreply.own_nickname",
                  "ไม่ยอมรัน: autoreply_im ต้องตั้ง autoreply.own_nickname"),
    "why_bot": ("looks like an automatic reply (prefix)", "ดูเหมือนข้อความตอบอัตโนมัติ (prefix)"),
    "e_im_kinds": ("autoreply_im.log_kinds must be a non-empty list of im / mtim",
                   "autoreply_im.log_kinds ต้องเป็นรายการของ im / mtim อย่างน้อย 1 ค่า"),
    "w_im_mtim": ("autoreply_im.log_kinds includes mtim: that window kind is unverified on a live Camfrog (run `im-probe`)",
                  "autoreply_im.log_kinds มี mtim: หน้าต่างชนิดนี้ยังไม่ได้ทดสอบกับ Camfrog จริง (รัน `im-probe`)"),
    "im_on": ("IM auto-reply ON: {mode}, friends={n}, rules={r}, kinds={k}",
              "ตอบ IM อัตโนมัติ: เปิด {mode} เพื่อน={n} กฎ={r} ชนิด={k}"),
    "im_off": ("IM auto-reply is OFF (autoreply_im.enabled=false)", "ตอบ IM อัตโนมัติ: ปิดอยู่ (autoreply_im.enabled=false)"),
    "im_none": ("no private-chat window found yet. Open one, or run `im-probe` to see how Camfrog's windows are classified",
                "ยังไม่พบหน้าต่างแชทส่วนตัว เปิดหน้าต่างแชท หรือรัน `im-probe` เพื่อดูว่า Camfrog แต่ละหน้าต่างเป็นชนิดไหน"),
    "im_skip_nick": ("IM line from {nick} ignored: not in autoreply_im.only_nicknames",
                     "ข้ามข้อความ IM จาก {nick}: ไม่อยู่ใน autoreply_im.only_nicknames"),
    "stats_hdr": ("stats:", "สถิติ:"),
    "stats_line": ("  started {started} | statuses {st} | replies {rp} | failures {fl}",
                   "  เริ่ม {started} | ตั้ง status {st} | ตอบ {rp} | ล้มเหลว {fl}"),
}

def t(key: str, **kw: Any) -> str:
    en, th = S[key]
    return (th if LANG == "th" else en).format(**kw)

def resolve_lang(pref: Optional[str]) -> str:
    pref = (pref or "auto").lower()
    if pref in ("th", "en"):
        return pref
    try:
        if os.name == "nt" and (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x1E:
            return "th"
    except Exception:
        pass
    env = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").lower()
    return "th" if env.startswith("th") else "en"

DEFAULTS = {
    "language": "auto",
    "reload_config": True,
    "stats": {"enabled": True, "file": "stats.json", "write_seconds": 60},
    "window_title_regex": ".*Camfrog.*",
    "dry_run": True,
    "poll_seconds": 1.5,
    "log": {"level": "INFO", "file": "camfrog_auto.log", "max_bytes": 1000000,
            "backups": 3, "log_message_text": True},
    "active_hours": {"enabled": False, "start": "09:00", "end": "23:30"},
    "safety": {"stop_file": "STOP", "pid_file": "camfrog_auto.pid",
               "require_foreground": True, "restore_previous_window": True,
               "max_consecutive_failures": 5},
    "status": {
        "enabled": True,
        "edit": {"class_name": "Edit", "auto_id": "1001", "index": 0},
        "apply_button": None,
        "interval_seconds": 600, "set_on_start": True, "random": False,
        "language_mode": "both", "retry_seconds": 30, "max_length": 120, "messages": [],
        "schedules": [],
        "language_cycle": [],
        "marquee": {"enabled": False, "width": 28, "stride": 2, "step_seconds": 0.5,
                    "separator": "   \u2022   ", "cycles": 1, "max_frames": 80, "infinite_loop": False},
        "history": {"enabled": True, "file": "status_history.json", "max_items": 50,
                    "record": True, "use_as_source": False, "seed_from_messages": True,
                    "mode": "rotate"},
    },
    "autoreply": {
        "enabled": True, "own_nickname": "", "window_title_regex": "", "log_kind": "room",
        "history_tail": 150,
        "history": {"class_name": "AtlAxWinLic140", "auto_id": "1002", "index": 0},
        "input": {"class_name": "AtlAxWinLic140", "auto_id": "1002", "index": 1},
        "ignore_nicknames": [], "only_nicknames": [],
        "per_sender_cooldown_seconds": 300, "global_min_gap_seconds": 20,
        "max_per_hour": 30, "delay_range_seconds": [2.0, 5.0],
        "max_reply_length": 200, "max_incoming_length": 500, "rules": [],
        "skip_patterns": [], "ignore_links": True,
    },
    # Private-message (IM) auto-reply: separate opt-in, own rules, own limits. Reuses the
    # autoreply.history / autoreply.input selectors (IM windows have the same two web panes).
    "autoreply_im": {
        "enabled": False, "dry_run": True, "window_title_regex": "", "max_windows": 5,
        "log_kinds": ["im"],
        "only_nicknames": [], "rules": [], "skip_patterns": [], "ignore_links": True,
        "prefix": "[auto] ", "answer_first_message": True,
        "per_sender_cooldown_seconds": 3600, "max_per_sender_per_day": 3,
        "global_min_gap_seconds": 20, "max_per_hour": 10, "delay_range_seconds": [2.0, 5.0],
        "max_reply_length": 200, "max_incoming_length": 500,
    },
}

def _im(cfg):
    return cfg.get("autoreply_im") or DEFAULTS["autoreply_im"]

def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def load_cfg(path: Union[str, Path]) -> dict:
    with Path(path).open(encoding="utf-8-sig") as f:  # Notepad may add a BOM
        return deep_merge(DEFAULTS, json.load(f))

def parse_hm(s: str) -> dt.time:
    h, m = str(s).split(":")
    return dt.time(int(h), int(m))

def validate(cfg: dict) -> tuple[list[str], list[str]]:
    """Never raises: a malformed value becomes an error message, not a traceback."""
    errs, warns = [], []
    try:
        _validate(cfg, errs, warns)
    except (TypeError, ValueError, KeyError, AttributeError) as e:
        errs.append(t("e_struct", e=f"{type(e).__name__}: {e}"))
    return errs, warns

SEL_KEYS = ("control_type", "auto_id", "class_name", "title", "title_re")

RANGES = (  # (path, lo, hi): numeric sanity so a typo cannot hammer UIA or crash the loop
    (("poll_seconds",), 0.2, 60),
    (("safety", "max_consecutive_failures"), 1, 100),
    (("status", "max_length"), 1, 500),
    (("status", "retry_seconds"), 1, 3600),
    (("autoreply", "max_reply_length"), 1, 500),
    (("autoreply", "max_incoming_length"), 1, 2000),
)

def _dig(cfg, path):
    for k in path:
        cfg = cfg[k]
    return cfg

def selector_clashes(cfg):
    """Pairs of enabled selectors that are identical (would drive one control for two jobs)."""
    sels = []
    if cfg["status"]["enabled"]:
        sels.append(("status.edit", cfg["status"]["edit"]))
    if cfg["autoreply"]["enabled"] or _im(cfg)["enabled"]:
        sels += [("autoreply.history", cfg["autoreply"]["history"]),
                 ("autoreply.input", cfg["autoreply"]["input"])]
    out = []
    for i, (na, a) in enumerate(sels):
        for nb, b in sels[i + 1:]:
            if isinstance(a, dict) and a == b:
                out.append((na, nb))
    return out

def _validate(cfg, errs, warns):
    st, ar = cfg["status"], cfg["autoreply"]
    for path, lo, hi in RANGES:
        v = _dig(cfg, path)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            errs.append(t("e_range", k=".".join(path), lo=lo, hi=hi))
    to_check = []
    if st["enabled"]:
        to_check.append(("status.edit", st["edit"]))
        if st["apply_button"]:
            to_check.append(("status.apply_button", st["apply_button"]))
    if ar["enabled"] or _im(cfg)["enabled"]:
        to_check += [("autoreply.history", ar["history"]), ("autoreply.input", ar["input"])]
    for name, sel in to_check:
        if isinstance(sel, dict) and not any(sel.get(k) not in (None, "") for k in SEL_KEYS):
            errs.append(t("e_selempty", k=name))
    for na, nb in selector_clashes(cfg):
        (errs if not cfg["dry_run"] else warns).append(
            t("e_selclash" if not cfg["dry_run"] else "w_selclash", a=na, b=nb))
    if ar.get("log_kind", "room") not in ("room", "im", "any"):
        errs.append("autoreply.log_kind must be room, im or any")
    if str(cfg["language"]).lower() not in ("auto", "th", "en"):
        errs.append(t("e_lang"))
    try:
        re.compile(cfg["window_title_regex"])
    except re.error as e:
        errs.append(t("e_regex", e=e))
    if cfg["active_hours"]["enabled"]:
        try:
            parse_hm(cfg["active_hours"]["start"]); parse_hm(cfg["active_hours"]["end"])
        except Exception:
            errs.append(t("e_hours"))
    if st["enabled"]:
        if not st["messages"]:
            errs.append(t("e_msgs"))
        if st["interval_seconds"] < 30:
            errs.append(t("e_interval"))
        if st["language_mode"] not in ("th", "en", "both", "alternate"):
            errs.append(t("e_mode"))
        if not isinstance(st["edit"], dict):
            errs.append(t("e_sel", k="status.edit"))
        mq, hs = st["marquee"], st["history"]
        try:
            inf = mq.get("infinite_loop", False)
            if mq["enabled"] and not (8 <= mq["width"] <= 80 and mq["width"] <= st["max_length"]
                                      and 1 <= mq["stride"] <= mq["width"]
                                      and mq["step_seconds"] >= 0.5
                                      and (inf or (1 <= mq["cycles"] <= 5))
                                      and 5 <= mq["max_frames"] <= 300):
                errs.append(t("e_marquee"))
        except TypeError:
            errs.append(t("e_marquee"))
        if any(x not in ("th", "en") for x in st["language_cycle"]):
            errs.append(t("e_cycle"))
        if hs["enabled"]:
            if hs["mode"] not in ("rotate", "random", "most_used"):
                errs.append(t("e_hmode"))
            if not (5 <= hs["max_items"] <= 500) or not hs["file"]:
                errs.append(t("e_hmax"))
            if hs["use_as_source"] and st["schedules"]:
                warns.append(t("w_sched_hist"))
        for i, sc in enumerate(st["schedules"]):
            try:
                parse_hm(sc["start"]); parse_hm(sc["end"])
                if not sc["messages"]:
                    raise ValueError
            except Exception:
                errs.append(t("e_sched", i=i))
    if ar["enabled"]:
        for k in ("history", "input"):
            if not isinstance(ar[k], dict):
                errs.append(t("e_sel", k=f"autoreply.{k}"))
        lo, hi = ar["delay_range_seconds"]
        if not (0 <= lo <= hi):
            errs.append(t("e_delay"))
        if ar["max_per_hour"] < 1:
            errs.append(t("e_hour"))
        if ar["per_sender_cooldown_seconds"] < 0 or ar["global_min_gap_seconds"] < 0:
            errs.append(t("e_cool"))
        if not ar["rules"]:
            warns.append(t("w_norules"))
        for i, r in enumerate(ar["rules"]):
            try:
                re.compile(r["pattern"], re.I)
            except (re.error, KeyError) as e:
                errs.append(t("e_rule", i=i, e=e))
            if not r.get("reply"):
                errs.append(t("e_reply", i=i))
            if r.get("mention") and not ar["own_nickname"].strip():
                warns.append(t("w_mention", i=i + 1))
        for i, sp in enumerate(ar["skip_patterns"]):
            try:
                re.compile(sp, re.I)
            except re.error as e:
                errs.append(t("e_skip", i=i, e=e))
        if not ar["own_nickname"].strip():
            warns.append(t("w_nick"))
    _validate_im(cfg, errs, warns)
    if not cfg["dry_run"]:
        warns.append(t("w_live"))

IM_RANGES = (  # (key, lo, hi)
    ("per_sender_cooldown_seconds", 60, 604800),
    ("max_per_sender_per_day", 1, 50),
    ("global_min_gap_seconds", 0, 3600),
    ("max_per_hour", 1, 100),
    ("max_reply_length", 1, 500),
    ("max_incoming_length", 1, 2000),
    ("max_windows", 1, 20),
)

def _validate_im(cfg, errs, warns):
    """Private-message auto-reply is stricter than room auto-reply: allowlist and own nick are
    mandatory, the prefix cannot be a command, and room rules can never reach a private chat."""
    im, ar = _im(cfg), cfg["autoreply"]
    if not im["enabled"]:
        return
    if not [n for n in im["only_nicknames"] if str(n).strip()]:
        errs.append(t("e_im_only"))
    if not ar["own_nickname"].strip():
        errs.append(t("e_im_nick"))
    if ar["enabled"] and ar.get("log_kind", "room") != "room":
        errs.append(t("e_im_kind"))
    for k in ("history", "input"):
        if not isinstance(ar[k], dict):
            errs.append(t("e_sel", k=f"autoreply.{k}"))
    for key, lo, hi in IM_RANGES:
        v = im[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            errs.append(t("e_range", k=f"autoreply_im.{key}", lo=lo, hi=hi))
    try:
        lo, hi = im["delay_range_seconds"]
        if not (0 <= lo <= hi):
            raise ValueError
    except (TypeError, ValueError):
        errs.append(t("e_im_delay"))
    try:
        re.compile(im["window_title_regex"])
    except re.error as e:
        errs.append(t("e_regex", e=e))
    ks = im["log_kinds"]
    if not isinstance(ks, list) or not ks or any(k not in ("im", "mtim") for k in ks):
        errs.append(t("e_im_kinds"))
    elif "mtim" in ks:
        warns.append(t("w_im_mtim"))
    pre = im["prefix"]
    if not isinstance(pre, str) or pre.lstrip().startswith("/"):
        errs.append(t("e_im_prefix"))
    elif not pre.strip():
        warns.append(t("w_im_noprefix"))
    for i, r in enumerate(im["rules"]):
        try:
            re.compile(r["pattern"], re.I)
        except (re.error, KeyError) as e:
            errs.append(t("e_im_rule", i=i, e=e))
        if not r.get("reply"):
            errs.append(t("e_reply", i=i))
    for i, sp in enumerate(im["skip_patterns"]):
        try:
            re.compile(sp, re.I)
        except re.error as e:
            errs.append(t("e_im_skip", i=i, e=e))
    if not im["rules"]:
        warns.append(t("w_im_norules"))

def shown(text: str) -> str:
    return repr(text) if LOG_TEXT else f"<{len(text)} chars>"

def get_window(cfg: dict):
    from pywinauto import Desktop  # lazy: `check` works without pywinauto
    wins = Desktop(backend="uia").windows(
        title_re=cfg["window_title_regex"], visible_only=True)
    if not wins:
        raise RuntimeError(t("no_window"))
    return wins[0]

def process_windows(main) -> list:
    """All visible top-level windows of the same process as `main` (Camfrog opens each chat room,
    IM and the buddy list as separate windows)."""
    from pywinauto import Desktop
    return Desktop(backend="uia").windows(process=main.process_id(), visible_only=True)

def _ctrl_attr(ctrl, attr: str) -> str:
    try:
        return getattr(ctrl.element_info, attr) or ""
    except Exception:
        return ""

def find(win, spec: dict):
    """Locate a control. Only class_name/control_type/title go to pywinauto's descendants():
    older pywinauto (0.6.x) raises TypeError on auto_id / title_re there, so those two are
    filtered here instead."""
    kw = {k: v for k, v in spec.items() if k in ("class_name", "control_type", "title")}
    items = win.descendants(**kw)
    if spec.get("auto_id") not in (None, ""):
        want = str(spec["auto_id"])
        items = [c for c in items if str(_ctrl_attr(c, "automation_id")) == want]
    if spec.get("title_re"):
        rx = re.compile(spec["title_re"])
        items = [c for c in items if rx.match(str(_ctrl_attr(c, "name")))]
    idx = spec.get("index", 0)
    if len(items) <= idx:
        raise LookupError(t("no_ctrl", spec=spec, n=len(items)))
    return items[idx]

def read_text(ctrl) -> str:
    try:
        v = ctrl.iface_value.CurrentValue
        if v:
            return v
    except Exception:
        pass
    v = ctrl.window_text()
    return v if v else "\n".join(ctrl.texts() or [])

def is_web(ctrl):
    return _ctrl_attr(ctrl, "class_name") == "AtlAxWinLic140"

def log_kind(ctrl):
    """'room' / 'im' / 'mtim' for a Camfrog web log pane (so a private-message window is never auto-answered).
    Returns None if the pane kind cannot be determined."""
    try:
        for d in ctrl.descendants(class_name="Internet Explorer_Server"):
            n = str(_ctrl_attr(d, "name"))
            if "wb-log-room-data" in n:
                return "room"
            if "wb-log-im-data" in n:
                return "im"
            if "wb-log-mtim-data" in n:
                return "mtim"
    except Exception:
        pass
    return None

def _wm_settext(ctrl, text):
    """Last resort for real HWND edit/richedit controls (Camfrog's input is RICHEDIT50W)."""
    WM_SETTEXT = 0x000C
    u = ctypes.windll.user32
    u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_wchar_p]
    u.SendMessageW(ctrl.handle, WM_SETTEXT, None, text)

def write_text(ctrl, text: str) -> bool:
    for fn in (lambda t_: ctrl.set_edit_text(t_), lambda t_: ctrl.iface_value.SetValue(t_),
               lambda t_: _wm_settext(ctrl, t_)):
        try:
            fn(text)
        except Exception:
            continue
        if read_text(ctrl).strip() == text.strip():
            return True
    return False

def foreground_ok(win, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        win.set_focus()
        if ctypes.windll.user32.GetForegroundWindow() == win.handle:
            return True
        time.sleep(0.1)
    return False

def _clip_get():
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    u.GetClipboardData.restype = ctypes.c_void_p
    k.GlobalLock.restype, k.GlobalLock.argtypes = ctypes.c_void_p, [ctypes.c_void_p]
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    if not u.OpenClipboard(None):
        return None
    try:
        h = u.GetClipboardData(13)  # CF_UNICODETEXT
        if not h:
            return ""
        p = k.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else ""
        finally:
            k.GlobalUnlock(h)
    finally:
        u.CloseClipboard()

def _clip_set(text):
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    k.GlobalAlloc.restype, k.GlobalAlloc.argtypes = ctypes.c_void_p, [ctypes.c_uint, ctypes.c_size_t]
    k.GlobalLock.restype, k.GlobalLock.argtypes = ctypes.c_void_p, [ctypes.c_void_p]
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    k.GlobalFree.argtypes = [ctypes.c_void_p]
    u.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    data = (text + "\0").encode("utf-16-le")
    if not u.OpenClipboard(None):
        return False
    try:
        u.EmptyClipboard()
        h = k.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
        if not h:
            return False
        p = k.GlobalLock(h)
        if not p:
            k.GlobalFree(h)
            return False
        ctypes.memmove(p, data, len(data))
        k.GlobalUnlock(h)
        return bool(u.SetClipboardData(13, h))
    finally:
        u.CloseClipboard()

def _escape_keys(text):
    return "".join("{%s}" % c if c in "{}()+^%~" else c for c in text)

def commit_web(win, ctrl, text: str, require_fg: bool = True, restore: bool = False) -> bool:
    """Send into Camfrog's web chat box. There is no text control to write to, so: bring the room to
    front, click the box, paste (clipboard is restored) or type, press Enter. Never types unless the
    room window is verified foreground, re-checked right before Enter."""
    from pywinauto import keyboard
    user32 = ctypes.windll.user32
    prev = user32.GetForegroundWindow() if restore else 0
    if not foreground_ok(win):
        log.error(t("not_fg"))
        return False
    ctrl.click_input()  # caret into the editable area
    time.sleep(0.15)
    if user32.GetForegroundWindow() != win.handle:
        log.error(t("not_fg"))
        return False
    old = _clip_get()
    pasted = _clip_set(text)
    try:
        keyboard.send_keys("^a", pause=0.02)
        keyboard.send_keys("^v" if pasted else _escape_keys(text), pause=0.01, with_spaces=True)
        time.sleep(0.2)
    finally:
        if pasted and old is not None:
            time.sleep(0.2)
            _clip_set(old)
    if user32.GetForegroundWindow() != win.handle:
        log.error(t("not_fg"))
        return False
    keyboard.send_keys("{ENTER}")
    if prev and prev != win.handle and user32.IsWindow(prev):
        time.sleep(0.15)
        user32.SetForegroundWindow(prev)
    return True

def press_button(btn):
    """Camfrog's CButtonTS buttons are owner-drawn and expose no UIA Invoke pattern: try Invoke,
    then background messages, then a real click."""
    try:
        btn.invoke()
        return
    except Exception:
        pass
    handle = getattr(btn, "handle", 0)
    if not handle and hasattr(btn, "element_info"):
        handle = getattr(btn.element_info, "handle", 0)
    if handle:
        import ctypes
        u = ctypes.windll.user32
        u.PostMessageW(handle, 0x0201, 1, 0)
        u.PostMessageW(handle, 0x0202, 0, 0)
        time.sleep(0.05)
        return
    btn.click_input()

def commit(win, ctrl, text: str, dry: bool, require_fg: bool = True, apply_btn=None, restore: bool = False) -> bool:
    """Write text, verify read-back, confirm Camfrog is foreground, send, restore focus."""
    if dry:
        log.info(t("dry_send", text=shown(text)))
        return True
    if is_web(ctrl):
        return commit_web(win, ctrl, text, require_fg, restore)
    if not write_text(ctrl, text):
        log.error(t("mismatch"))
        return False
    user32 = ctypes.windll.user32
    prev = user32.GetForegroundWindow() if restore else 0
    
    needs_foreground = require_fg and apply_btn is None
    if needs_foreground and not foreground_ok(win):
        log.error(t("not_fg"))
        return False

    if apply_btn is not None:
        press_button(apply_btn)
    else:
        if require_fg:
            ctrl.set_focus()
            if user32.GetForegroundWindow() != win.handle:  # focus stolen: do not type
                log.error(t("not_fg"))
                return False
            ctrl.type_keys("{ENTER}")
        else:
            handle = getattr(ctrl, "handle", 0)
            if not handle and hasattr(ctrl, "element_info"):
                handle = getattr(ctrl.element_info, "handle", 0)
            if handle:
                ctypes.windll.user32.PostMessageW(handle, 0x0100, 0x0D, 0)
                ctypes.windll.user32.PostMessageW(handle, 0x0101, 0x0D, 0)
            else:
                ctrl.send_keystrokes("{ENTER}")
    if prev and prev != win.handle and user32.IsWindow(prev):
        time.sleep(0.15)
        user32.SetForegroundWindow(prev)  # best effort: give focus back to what you were doing
    return True

def expand(text: str, nick: str = "", own: str = "") -> str:
    """Replace {sender} {me} {time} {date}. Plain replace (never str.format)."""
    now = dt.datetime.now()
    for k, v in (("{sender}", nick), ("{me}", own), ("{time}", now.strftime("%H:%M")),
                 ("{date}", now.strftime("%Y-%m-%d"))):
        text = text.replace(k, v)
    return text

def atomic_write(path: Union[str, Path], text: str) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    for i in range(5):  # AV/indexers can briefly lock the target
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.2 * (i + 1))
    os.replace(tmp, path)

LEAD_VOWELS = set("\u0e40\u0e41\u0e42\u0e43\u0e44")

def clusters(text: str) -> list[str]:
    """Split into display clusters: combining marks (Thai vowels/tone marks, emoji
    modifiers) stay with their base; Thai leading vowels stay with the next consonant."""
    out, prefix = [], ""
    for ch in text:
        if ch in LEAD_VOWELS:
            prefix += ch
            continue
        attach = (unicodedata.category(ch) in ("Mn", "Mc", "Me") or ch in "\u200d\ufe0f\ufe0e"
                  or (out and out[-1].endswith("\u200d")))
        if out and not prefix and attach:
            out[-1] += ch
        else:
            out.append(prefix + ch)
            prefix = ""
    if prefix:
        out.append(prefix)
    return out

def clip(text: str, limit: int) -> str:
    """Truncate to `limit` characters without cutting a Thai cluster (no dangling vowel/mark)."""
    if len(text) <= limit:
        return text
    out, n = [], 0
    for c in clusters(text):
        if n + len(c) > limit:
            break
        out.append(c)
        n += len(c)
    return "".join(out)

def pid_path(cfg):
    return BASE / cfg["safety"]["pid_file"]

def read_pid(cfg):
    try:
        return int(pid_path(cfg).read_text().strip())
    except Exception:
        return None

def pid_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def pid_image(pid):
    """Executable path of a process (Windows), or None when unknown."""
    try:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)
        if not h:
            return None
        buf, n = ctypes.create_unicode_buffer(1024), ctypes.c_ulong(1024)
        ok = k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
        k.CloseHandle(h)
        return buf.value if ok else None
    except Exception:
        return None

def pid_is_ours(pid, image=None):
    """Guard against PID reuse: a stale pid file must never make `stop` kill a stranger."""
    if os.name != "nt":
        return True
    image = image if image is not None else pid_image(pid)
    if not image:
        return True  # cannot tell: keep the old behaviour
    name = Path(image).name.lower()
    return "camfrog" in name or name.startswith("python") or name == Path(sys.executable).name.lower()

def running_pid(cfg):
    pid = read_pid(cfg)
    return pid if pid_alive(pid) and pid_is_ours(pid) else None

def child_cmd(args):
    if getattr(sys, "frozen", False):
        cmd = [sys.executable]
    else:
        py = Path(sys.executable)
        pyw = py.with_name("pythonw.exe")
        cmd = [str(pyw if pyw.exists() else py), str(Path(__file__).resolve())]
    if getattr(args, "config", None):
        cmd += ["--config", str(Path(args.config).resolve())]
    if getattr(args, "lang", None):
        cmd += ["--lang", args.lang]
    return cmd

def child_env():
    """A frozen onefile exe that re-launches itself must NOT reuse the parent's unpack
    dir (it is deleted when the parent exits -> the hidden child would crash)."""
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"  # PyInstaller >= 6.9
        env.pop("_MEIPASS2", None)                  # older PyInstaller
    return env

def cmd_start(cfg, args):
    pid = running_pid(cfg)
    if pid:
        print(t("already_running", pid=pid))
        return 1
    if os.name != "nt":
        print(t("win_only"))
        return 2
    if not cfg["log"]["file"]:
        print(t("bg_needs_log"))
        return 2
    logf = BASE / cfg["log"]["file"]
    flags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    p = subprocess.Popen(child_cmd(args) + ["run"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags, close_fds=True, cwd=str(BASE),
                         env=child_env())
    time.sleep(2.5)
    if p.poll() is not None:
        print(t("bg_failed", code=p.returncode, log=logf))
        return 1
    print(t("bg_started", pid=p.pid, log=logf))
    return 0

def worker_cmd(args):
    """Command that runs the status-only background worker.

    The worker is camfrog-auto's run loop (Runner), not this GUI: this
    module has no run loop, so relaunching itself would just open another
    window (or exit on the single-instance mutex).
    Frozen : dist/camfrog-auto.exe next to this exe.
    Source : python camfrog_auto.py next to this file.
    """
    cfg_arg = []
    if getattr(args, "config", None):
        cfg_arg += ["--config", str(Path(args.config).resolve())]
    if getattr(args, "lang", None):
        cfg_arg += ["--lang", args.lang]
    if getattr(sys, "frozen", False):
        exe = BASE / "camfrog-auto.exe"
        if not exe.is_file():
            raise FileNotFoundError(
                f"Worker executable not found: {exe} (re-run build.bat)")
        return [str(exe)] + cfg_arg
    script = BASE / "camfrog_auto.py"
    if not script.is_file():
        raise FileNotFoundError(f"Worker script not found: {script}")
    return [str(Path(sys.executable)), str(script)] + cfg_arg

def cmd_start_worker(cfg, args):
    """Start the status-only worker (camfrog-auto run loop) in background."""
    pid = running_pid(cfg)
    if pid:
        print(t("already_running", pid=pid))
        return 1
    if os.name != "nt":
        print(t("win_only"))
        return 2
    if not cfg["log"]["file"]:
        print(t("bg_needs_log"))
        return 2
    logf = BASE / cfg["log"]["file"]
    flags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    p = subprocess.Popen(worker_cmd(args) + ["run"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags, close_fds=True, cwd=str(BASE),
                         env=child_env())
    time.sleep(2.5)
    if p.poll() is not None:
        print(t("bg_failed", code=p.returncode, log=logf))
        return 1
    print(t("bg_started", pid=p.pid, log=logf))
    return 0

def cmd_stop(cfg):
    pid = running_pid(cfg)
    stop_file = BASE / cfg["safety"]["stop_file"]
    if not pid:
        print(t("not_running"))
        pid_path(cfg).unlink(missing_ok=True)
        return 0
    print(t("stopping", pid=pid))
    stop_file.write_text("stop")
    for _ in range(200):  # up to 20 s (a reply delay may be in progress)
        if not pid_alive(pid):
            break
        time.sleep(0.1)
    forced = False
    if pid_alive(pid):
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, check=False, timeout=10)
            forced = True
        except (OSError, subprocess.TimeoutExpired):
            log.exception("taskkill failed for PID %s", pid)
        for _ in range(30):  # confirm exit after force termination
            if not pid_alive(pid) or not pid_is_ours(pid):
                break
            time.sleep(0.1)
    if pid_alive(pid) and pid_is_ours(pid):
        print(t("stop_failed", pid=pid))
        return 1  # retain STOP/PID files so another stop attempt can finish cleanup
    print(t("killed") if forced else t("stopped_ok"))
    stop_file.unlink(missing_ok=True)
    pid_path(cfg).unlink(missing_ok=True)
    return 0

STRUCT_SKIP = {"Text", "Hyperlink", "Image", "ListItem", "DataItem", "TreeItem"}

def describe_controls(win):
    """Live UIA tree -> plain dicts (no chat text: Text-like rows keep no name)."""
    rows = []
    for c in win.descendants():
        try:
            r = c.rectangle()
            rows.append({
                "class_name": _ctrl_attr(c, "class_name"), "control_type": _ctrl_attr(c, "control_type"),
                "name": str(_ctrl_attr(c, "name"))[:40], "auto_id": str(_ctrl_attr(c, "automation_id")),
                "visible": bool(c.is_visible()), "enabled": bool(c.is_enabled()),
                "left": r.left, "top": r.top, "w": r.width(), "h": r.height(),
                "parent_class": str(getattr(getattr(c.element_info, "parent", None), "class_name", "") or ""),
            })
        except Exception:
            continue
    return rows

def _nth(rows, row, field):
    """Index of `row` among rows sharing its `field` value(s), in traversal order - the same order
    find() uses (descendants(class_name=...) / (control_type=...), then auto_id)."""
    fields = (field,) if isinstance(field, str) else field
    same = [r for r in rows if all(r.get(f) == row.get(f) for f in fields)]
    return next(i for i, r in enumerate(same) if r is row)

def _sel(rows, row, key="class_name"):
    """Selector for `row`: class (or type) plus its automation id when it has one."""
    sel = {key: row[key]}
    fields = (key,)
    if row.get("auto_id") and key == "class_name":
        sel["auto_id"], fields = row["auto_id"], (key, "auto_id")
    sel["index"] = _nth(rows, row, fields)
    return sel

def detect_camfrog(rows):
    """rows (describe_controls) -> {key: (selector, why)}. Pure function, unit-tested offline."""
    live = [r for r in rows if r.get("visible") and r.get("enabled") and r["w"] > 0 and r["h"] > 0]
    out = {}
    hosts = [r for r in live if r["class_name"] == "AtlAxWinLic140"]

    def kind(h):  # the IE pane sharing the host's rectangle names the page: wb-log-room-data / wb-edit-data
        for r in rows:
            if (r["class_name"] == "Internet Explorer_Server"
                    and (r["left"], r["top"], r["w"], r["h"]) == (h["left"], h["top"], h["w"], h["h"])):
                return r["name"]
        return ""
    logs = [h for h in hosts if "wb-log-room-data" in kind(h)]
    edits_ = [h for h in hosts if "wb-edit-data" in kind(h)]
    if logs and edits_:
        out["autoreply.history"] = (_sel(rows, max(logs, key=lambda r: r["w"] * r["h"])),
                                    "room chat log (web pane wb-log-room-data)")
        out["autoreply.input"] = (_sel(rows, max(edits_, key=lambda r: r["top"])),
                                  "room chat input (web pane wb-edit-data)")
        rich = []
    else:
        rich = [r for r in live if r["class_name"].upper().startswith("RICHEDIT")]
    inp = max(rich, key=lambda r: (r["top"], r["w"]), default=None) if rich else None
    if inp:
        out["autoreply.input"] = (_sel(rows, inp),
                                  "bottom-most RichEdit = chat input")
    docs = [r for r in live if r["control_type"] == "Document"] if not out.get("autoreply.history") else []
    if out.get("autoreply.history"):
        pass
    elif docs:
        d = max(docs, key=lambda r: r["w"] * r["h"])
        out["autoreply.history"] = ({"control_type": "Document", "index": _nth(rows, d, "control_type")},
                                    "largest Chromium Document = room log")
    else:
        rest = [r for r in rich if r is not inp]
        if rest:
            h = max(rest, key=lambda r: r["w"] * r["h"])
            out["autoreply.history"] = (_sel(rows, h),
                                        "largest other RichEdit (no Document found)")
    edits = [r for r in live if r["class_name"].lower() == "edit" and "combo" in r["parent_class"].lower()]
    if edits:
        e = min(edits, key=lambda r: (r["top"], r["left"]))
        out["status.edit"] = (_sel(rows, e),
                              "top-most combo-box Edit = custom status")
    else:
        combos = [r for r in live if "combobox" in r["class_name"].lower()]
        if combos:
            c = min(combos, key=lambda r: (r["top"], r["left"]))
            out["status.edit"] = (_sel(rows, c),
                                  "top-most ComboBox (no inner Edit exposed)")
    return out

def write_detect_report(rows, path):
    with Path(path).open("w", encoding="utf-8") as f:
        f.write("class_name | control_type | name(<=40) | auto_id | visible | left,top,w,h | parent_class\n")
        for r in rows:
            if r["control_type"] in STRUCT_SKIP:
                continue
            f.write(f"{r['class_name']} | {r['control_type']} | {r['name']} | {r['auto_id']} | "
                    f"{int(r['visible'])} | {r['left']},{r['top']},{r['w']},{r['h']} | {r['parent_class']}\n")

def cmd_detect(cfg, cfg_path=None, apply=False, as_json=False):
    win = get_window(cfg)
    per_window = [describe_controls(win)] + [describe_controls(w) for w in process_windows(win)
                                             if w.handle != win.handle]
    rows = [r for rs in per_window for r in rs]
    found = {}
    for rs in per_window:  # selectors are per window (find() indexes inside one window)
        for k, v in detect_camfrog(rs).items():
            found.setdefault(k, v)
    rep = BASE / "detect_report.txt"
    write_detect_report(rows, rep)
    if as_json:
        print("PROPOSAL " + json.dumps({k: v[0] for k, v in found.items()}))
    for key in ("status.edit", "autoreply.history", "autoreply.input"):
        if key in found:
            print(t("det_found", k=key, sel=json.dumps(found[key][0]), why=found[key][1]))
        else:
            print(t("det_miss", k=key))
    print(t("det_report", p=rep))
    if not found:
        print(t("det_none"))
        return 1
    if apply:
        new = copy.deepcopy(cfg)
        for key, (sel, _why) in found.items():
            _dig(new, key.split(".")[:-1])[key.split(".")[-1]] = sel
        errs, _ = validate(new)
        if errs:
            print(*errs, sep="\n  ")
            return 2
        path = Path(cfg_path) if cfg_path else BASE / "config.json"
        atomic_write(path, json.dumps(new, ensure_ascii=False, indent=2) + "\n")
        print(t("det_applied", p=path))
    return 0

def cmd_status(cfg, text):
    win = get_window(cfg)
    st, sf = cfg["status"], cfg["safety"]
    ctrl = find(win, st["edit"])
    btn = find(win, st["apply_button"]) if st["apply_button"] else None
    text = clip(expand(text, own=cfg["autoreply"]["own_nickname"]), st["max_length"])
    ok = commit(win, ctrl, text, cfg["dry_run"], sf["require_foreground"], btn,
                sf["restore_previous_window"])
    print(t("ok") if ok else t("failed"))
    return 0 if ok else 1

CLI_COMMANDS = {
    "check", "discover", "windows", "run", "start", "stop", "state",
    "autostart-on", "autostart-off", "chat-probe", "im-probe", "detect",
    "status", "init", "marquee", "history", "history-add", "history-import",
    "test-rules",
}

# ---------- Inlined TrayIcon ----------


class TrayIcon:
    """A native Windows tray icon with Show and Exit menu items.

    On non-Windows platforms (or when pywin32 cannot initialize), ``active`` is
    false and callers can fall back to normal window behavior.
    """

    WM_TRAY = 0x8000 + 41
    ID_SHOW = 1001
    ID_EXIT = 1002

    def __init__(self, root, title, on_show, on_exit, icon_path=None):
        self.root = root
        self.on_show = on_show
        self.on_exit = on_exit
        self.title = str(title)[:127]
        self.active = False
        self._class_atom = None
        self.hwnd = None
        self.icon = None
        if os.name != "nt":
            return
        try:
            import win32con
            import win32gui

            self.win32con = win32con
            self.win32gui = win32gui
            self.hinstance = win32gui.GetModuleHandle(None)
            self.class_name = f"CamfrogTrayWindow_{os.getpid()}_{id(self):x}"
            wc = win32gui.WNDCLASS()
            wc.hInstance = self.hinstance
            wc.lpszClassName = self.class_name
            wc.lpfnWndProc = self._window_proc
            self._class_atom = win32gui.RegisterClass(wc)
            self.hwnd = win32gui.CreateWindowEx(
                0, self.class_name, self.title, 0,
                0, 0, 0, 0, 0, 0, self.hinstance, None,
            )
            self.icon = self._load_icon(icon_path)
            flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
            data = (self.hwnd, 1, flags, self.WM_TRAY, self.icon, self.title)
            if not win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, data):
                raise RuntimeError("Shell_NotifyIcon rejected NIM_ADD")
            self.active = True
            self.root.after(100, self._pump)
        except Exception:
            self.shutdown()

    def _load_icon(self, icon_path):
        gui, con = self.win32gui, self.win32con
        paths = []
        if icon_path:
            paths.append(Path(icon_path))
        frozen_dir = getattr(__import__("sys"), "_MEIPASS", None)
        if frozen_dir:
            paths.append(Path(frozen_dir) / "app.ico")
        paths.append(Path(__import__("sys").executable).resolve().parent / "app.ico")
        paths.append(Path(__file__).resolve().with_name("app.ico"))
        for path in paths:
            try:
                if path.is_file():
                    icon = gui.LoadImage(
                        0, str(path), con.IMAGE_ICON, 0, 0,
                        con.LR_LOADFROMFILE | con.LR_DEFAULTSIZE,
                    )
                    if icon:
                        return icon
            except Exception:
                continue
        return gui.LoadIcon(0, con.IDI_APPLICATION)

    def _window_proc(self, hwnd, message, wparam, lparam):
        gui, con = self.win32gui, self.win32con
        if message == self.WM_TRAY:
            if lparam in (con.WM_LBUTTONUP, con.WM_LBUTTONDBLCLK):
                self.on_show()
            elif lparam == con.WM_RBUTTONUP:
                self._show_menu()
            return 0
        if message == con.WM_COMMAND:
            command = wparam & 0xFFFF
            if command == self.ID_SHOW:
                self.on_show()
            elif command == self.ID_EXIT:
                self.on_exit()
            return 0
        return gui.DefWindowProc(hwnd, message, wparam, lparam)

    def _show_menu(self):
        gui, con = self.win32gui, self.win32con
        menu = gui.CreatePopupMenu()
        gui.AppendMenu(menu, con.MF_STRING, self.ID_SHOW, "Open window")
        gui.AppendMenu(menu, con.MF_SEPARATOR, 0, None)
        gui.AppendMenu(menu, con.MF_STRING, self.ID_EXIT, "Exit GUI")
        x, y = gui.GetCursorPos()
        gui.SetForegroundWindow(self.hwnd)
        gui.TrackPopupMenu(menu, con.TPM_RIGHTBUTTON, x, y, 0, self.hwnd, None)
        gui.PostMessage(self.hwnd, con.WM_NULL, 0, 0)
        gui.DestroyMenu(menu)

    def _pump(self):
        if not self.active:
            return
        try:
            self.win32gui.PumpWaitingMessages()
        except Exception:
            self.shutdown()
            return
        if self.active:
            try:
                self.root.after(100, self._pump)
            except Exception:
                self.shutdown()

    def shutdown(self):
        if not self.active and not self.hwnd:
            return
        gui = getattr(self, "win32gui", None)
        if gui:
            try:
                if self.hwnd:
                    gui.Shell_NotifyIcon(gui.NIM_DELETE, (self.hwnd, 1))
            except Exception:
                pass
            try:
                if self.hwnd:
                    gui.DestroyWindow(self.hwnd)
            except Exception:
                pass
            try:
                if self._class_atom:
                    gui.UnregisterClass(self.class_name, self.hinstance)
            except Exception:
                pass
        self.active = False
        self.hwnd = None
        self._class_atom = None
# ---------- Inlined ClipboardController ----------


_WIDGET_CLASSES = {
    "Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox", "Text", "Listbox",
}
_EDITABLE_CLASSES = {"Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox", "Text"}


def _windows_open_clipboard(clipboard, attempts=20, interval=0.025):
    """Windows clipboard is often briefly busy; retry opening it for 0.5 seconds."""
    last_error = None
    for attempt in range(attempts):
        try:
            clipboard.OpenClipboard(None)
            return
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(interval)
    raise OSError(f"Could not open the Windows clipboard: {last_error}") from last_error


def set_clipboard_text(root, text):
    text = str(text)
    if os.name == "nt":
        import win32clipboard
        import win32con

        _windows_open_clipboard(win32clipboard)
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        return
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()


def get_clipboard_text(root):
    if os.name == "nt":
        import win32clipboard
        import win32con

        _windows_open_clipboard(win32clipboard)
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                value = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                value = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                if isinstance(value, bytes):
                    value = value.decode("mbcs", errors="replace")
            else:
                return ""
            return value if isinstance(value, str) else str(value)
        finally:
            win32clipboard.CloseClipboard()
    try:
        return root.clipboard_get()
    except Exception:
        return ""


def _widget_class(widget):
    try:
        return widget.winfo_class()
    except Exception:
        return ""


def _has_selection(widget, widget_class):
    try:
        if widget_class == "Text":
            return bool(widget.tag_ranges("sel"))
        if widget_class == "Listbox":
            return bool(widget.curselection())
        return bool(widget.selection_present())
    except Exception:
        return False


def _selected_text(widget, widget_class):
    if widget_class == "Text":
        return widget.get("sel.first", "sel.last")
    if widget_class == "Listbox":
        selected = widget.curselection()
        return "\n".join(widget.get(index) for index in selected)
    value = widget.get()
    start, end = int(widget.index("sel.first")), int(widget.index("sel.last"))
    return value[start:end]


def _editable(widget, widget_class):
    if widget_class not in _EDITABLE_CLASSES:
        return False
    try:
        return str(widget.cget("state")) not in {"disabled", "readonly"}
    except Exception:
        return True


def _delete_selection(widget, widget_class):
    if widget_class == "Text":
        widget.delete("sel.first", "sel.last")
    else:
        widget.delete("sel.first", "sel.last")


def _operate(root, widget, action):
    widget_class = _widget_class(widget)
    if widget_class not in _WIDGET_CLASSES:
        return False

    if action in {"copy", "cut"}:
        if not _has_selection(widget, widget_class):
            return False
        if action == "cut" and not _editable(widget, widget_class):
            return False
        selected = _selected_text(widget, widget_class)
        set_clipboard_text(root, selected)
        if action == "cut":
            _delete_selection(widget, widget_class)
        return True

    if action == "paste":
        if not _editable(widget, widget_class):
            return False
        value = get_clipboard_text(root)
        if not value:
            return False
        if widget_class == "Text":
            if _has_selection(widget, widget_class):
                widget.delete("sel.first", "sel.last")
            widget.insert("insert", value)
        else:
            if _has_selection(widget, widget_class):
                _delete_selection(widget, widget_class)
            widget.insert("insert", value)
        return True
    return False


class ClipboardController:
    """Attach reliable Ctrl+C/X/V/A, Insert shortcuts, and a right-click menu."""

    def __init__(self, root, translate=None, on_error=None):
        import tkinter as tk

        self.root = root
        self.translate = translate or (lambda text: text)
        self.on_error = on_error
        self.target = None
        self.widgets = []
        self.menu = tk.Menu(root, tearoff=False)
        for label, action in (("Cut|ตัด", "cut"), ("Copy|คัดลอก", "copy"),
                              ("Paste|วาง", "paste")):
            self.menu.add_command(label=self.translate(label),
                                  command=lambda op=action: self.perform(self.target, op))
        self.menu.add_separator()
        self.menu.add_command(label=self.translate("Select all|เลือกทั้งหมด"),
                              command=lambda: self.select_all(self.target))

    def install(self, parent):
        for widget in parent.winfo_children():
            widget_class = _widget_class(widget)
            if widget_class in _WIDGET_CLASSES:
                self.widgets.append(widget)
                for sequence, action in (
                    ("<Control-c>", "copy"), ("<Control-x>", "cut"),
                    ("<Control-v>", "paste"), ("<Control-Insert>", "copy"),
                    ("<Shift-Delete>", "cut"), ("<Shift-Insert>", "paste"),
                ):
                    widget.bind(sequence, lambda event, op=action: self.handle(event, op), add="+")
                widget.bind("<Control-a>", self._select_all_event, add="+")
                widget.bind("<Button-3>", self.show_menu, add="+")
                widget.bind("<Shift-F10>", self.show_menu, add="+")
            self.install(widget)

    def perform(self, widget, action):
        if widget is None:
            return False
        try:
            return _operate(self.root, widget, action)
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            return False

    def handle(self, event, action):
        self.target = event.widget
        self.perform(self.target, action)
        return "break"

    def select_all(self, widget):
        if widget is None:
            return "break"
        widget_class = _widget_class(widget)
        try:
            if widget_class == "Text":
                widget.tag_add("sel", "1.0", "end-1c")
                widget.mark_set("insert", "end-1c")
            elif widget_class == "Listbox":
                widget.selection_set(0, "end")
            else:
                widget.selection_range(0, "end")
                widget.icursor("end")
            widget.focus_set()
        except Exception:
            pass
        return "break"

    def _select_all_event(self, event):
        self.target = event.widget
        return self.select_all(event.widget)

    def show_menu(self, event):
        self.target = event.widget
        try:
            event.widget.focus_set()
            self.menu.tk_popup(event.x_root, event.y_root)
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
        finally:
            try:
                self.menu.grab_release()
            except Exception:
                pass
        return "break"
# ---------- Original Status GUI ----------


RUNTIME_CONFIG = BASE / "camfrog-status-runtime.json"
WORKER_MARKER = BASE / "camfrog-status-changer-worker.pid"
MARQUEE_STEP_MIN = 0.5
MARQUEE_STRIDE_DEFAULT = 2
STATUS_SLOTS = 10


def text_to_message(value):
    value = value.strip()
    if not value:
        return None
    if "||" in value:
        th, en = (part.strip() for part in value.split("||", 1))
        if th and en:
            return {"th": th, "en": en}
        return th or en or None
    return value


def message_to_text(value):
    if isinstance(value, dict):
        return f"{value.get('th', '')} || {value.get('en', '')}"
    return str(value or "")


def messages_from_slots(values):
    """Return the configured, non-empty messages represented by the ten GUI slots."""
    result = []
    for value in values:
        message = text_to_message(value)
        if message is not None:
            result.append(message)
    return result


def runtime_config(config):
    """Clone shared settings for a status-only worker; keep the shared PID lock."""
    runtime = copy.deepcopy(config)
    runtime["autoreply"]["enabled"] = False
    runtime.setdefault("autoreply_im", {})["enabled"] = False
    runtime["stats"]["file"] = "camfrog_status_changer_stats.json"
    runtime["log"]["file"] = "camfrog_status_changer.log"
    runtime.setdefault("safety", {})["require_foreground"] = False
    return runtime


def write_config(path, config):
    atomic_write(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")


def build_app():
    import tkinter as tk
    from tkinter import messagebox, ttk

    class StatusChanger:
        def __init__(self, config_path):
            self.config_path = Path(config_path).resolve()
            self.runtime_config_path = self.config_path.with_name(RUNTIME_CONFIG.name)
            self.worker_marker_path = self.config_path.with_name(WORKER_MARKER.name)
            self.root = tk.Tk()
            self.root.title("Camfrog Status Changer")
            self.root.geometry("220x505")
            self.root.resizable(False, False)
            self.root.minsize(220, 505)
            self.root.maxsize(220, 505)
            try:
                self.root.iconbitmap(str(BASE / "app.ico"))
            except (tk.TclError, OSError):
                pass
            self.busy = False
            self.close_requested = False
            self.task_results = queue.Queue()
            self.task_poll_job = None
            self.state_job = None
            self.save_job = None
            self.mode = "random"
            self.entry_widgets = []
            try:
                self.config = load_cfg(self.config_path)
            except Exception as exc:
                messagebox.showerror("Camfrog Status Changer", str(exc), parent=self.root)
                self.root.destroy()
                raise SystemExit(2)
            global LANG
            LANG = resolve_lang(self.config.get("language", "auto"))
            self.fields = [tk.StringVar(value="") for _ in range(STATUS_SLOTS)]
            self.step = tk.StringVar(value=str(max(
                MARQUEE_STEP_MIN, self.config["status"]["marquee"]["step_seconds"])))
            self.stride = tk.StringVar(value=str(self.config["status"]["marquee"].get(
                "stride", MARQUEE_STRIDE_DEFAULT)))
            self.infinite_loop = tk.BooleanVar(value=bool(
                self.config["status"]["marquee"].get("infinite_loop", False)))
            self._load_fields()
            for variable in self.fields:
                variable.trace_add("write", self.schedule_save)
            self._build()
            self.clipboard_controller = ClipboardController(
                self.root, translate=self._translate_clipboard, on_error=self._clipboard_error)
            self.clipboard_controller.install(self.root)
            self.tray = TrayIcon(
                self.root,
                "Camfrog Status Changer",
                on_show=self.show_from_tray,
                on_exit=self.exit_app,
                icon_path=str(BASE / "app.ico"),
            )
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
            self.task_poll_job = self.root.after(100, self.poll_task_results)
            self.state_job = self.root.after(500, self.refresh_state)
            if self.config.get("status", {}).get("enabled", True):
                self.root.after(400, self._auto_start_if_idle)

            # Register single-instance restore message handler
            if os.name == "nt":
                self._register_single_instance_handler()

        def _load_fields(self):
            for var, message in zip(self.fields, self.config["status"]["messages"][:STATUS_SLOTS]):
                var.set(message_to_text(message))
            st = self.config["status"]
            if st["marquee"]["enabled"]:
                self.mode = "marquee"
            elif st["random"]:
                self.mode = "random"

        def _tr(self, en, th):
            return th if LANG == "th" else en

        def _translate_clipboard(self, text):
            en, _, th = text.partition("||")
            th, en = th.strip(), en.strip()
            return th if LANG == "th" and th else en

        def _clipboard_error(self, exc):
            try:
                self.note.configure(text=self._tr(f"Clipboard error: {exc}",
                                                   f"คลิปบอร์ดผิดพลาด: {exc}"))
            except tk.TclError:
                pass

        def _build(self):
            root = self.root
            style = ttk.Style(root)
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
            style.configure("Brand.TLabel", font=("Segoe UI", 9, "bold"), foreground="#126c68")
            style.configure("State.TLabel", font=("Segoe UI", 8, "bold"))
            outer = ttk.Frame(root, padding=(7, 6, 7, 4))
            outer.pack(fill="both", expand=True)

            header = ttk.Frame(outer)
            header.pack(fill="x", pady=(0, 5))
            ttk.Label(header, text="STATUS", style="Brand.TLabel").pack(side="left")
            self.state_label = ttk.Label(header, text="", style="State.TLabel")
            self.state_label.pack(side="right")

            self.tabs = ttk.Notebook(outer)
            self.tabs.pack(fill="both", expand=True)
            self.pages = {}
            for name, mode in (("Random", "random"), ("Marquee", "marquee")):
                page = ttk.Frame(self.tabs, padding=6)
                self.tabs.add(page, text=name)
                self.pages[mode] = page
                self._build_page(page, mode)
            self.tabs.bind("<<NotebookTabChanged>>", self._tab_changed)

            self.note = ttk.Label(outer, text="", font=("Segoe UI", 7), anchor="center",
                                  foreground="#53636d", wraplength=190)
            self.note.pack(fill="x", pady=(4, 2))
            ttk.Label(outer, text="CAMFROG AUTO", style="Brand.TLabel",
                      anchor="center").pack(fill="x")
            selected = 1 if self.mode == "marquee" else 0
            self.tabs.select(selected)

        def _build_page(self, page, mode):
            if mode == "random":
                ttk.Label(page, text=self._tr("Random status pool", "ชุดสถานะสุ่ม"),
                          font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
            else:
                ttk.Label(page, text=self._tr("Marquee status pool", "ชุดสถานะเลื่อน"),
                          font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
                speed = ttk.Frame(page)
                speed.pack(fill="x", pady=(0, 3))
                ttk.Label(speed, text=self._tr("Step", "จังหวะ")).pack(side="left")
                ttk.Spinbox(speed, textvariable=self.step, from_=MARQUEE_STEP_MIN,
                            to=10, increment=0.1, width=4).pack(side="left", padx=(3, 5))
                ttk.Label(speed, text="s").pack(side="left")
                ttk.Label(speed, text=self._tr("Stride", "ก้าว")).pack(side="left", padx=(5, 2))
                ttk.Spinbox(speed, textvariable=self.stride, from_=1, to=10,
                            increment=1, width=2).pack(side="left")
                ttk.Checkbutton(speed, text=self._tr("Loop", "วนลูป"),
                                variable=self.infinite_loop).pack(side="left", padx=(5, 0))

            entries = ttk.Frame(page)
            entries.pack(fill="both", expand=True)
            for index, var in enumerate(self.fields):
                ttk.Label(entries, text=str(index + 1), width=2).grid(
                    row=index, column=0, sticky="w", pady=3)
                entry = ttk.Entry(entries, textvariable=var, width=13)
                entry.grid(row=index, column=1, sticky="ew", pady=3)
                self.entry_widgets.append((entry, var))
            entries.columnconfigure(1, weight=1)

            buttons = ttk.Frame(page)
            buttons.pack(fill="x", pady=(4, 0))
            ttk.Button(buttons, text=self._tr("Apply Now", "ใช้ทันที"),
                       command=self.apply_now).pack(
                           fill="x", pady=(0, 3))
            row2 = ttk.Frame(buttons)
            row2.pack(fill="x")
            ttk.Button(row2, text=self._tr("Enable", "เปิด"),
                       command=lambda m=mode: self.set_enabled(m, True)).pack(
                           side="left", fill="x", expand=True, padx=(0, 2))
            ttk.Button(row2, text=self._tr("Disable", "ปิด"),
                       command=lambda: self.set_enabled(mode, False)).pack(
                           side="left", fill="x", expand=True, padx=(2, 0))

        def _tab_changed(self, _event=None):
            try:
                page_index = self.tabs.index(self.tabs.select())
                self.mode = "marquee" if page_index == 1 else "random"
            except Exception:
                pass

        def schedule_save(self, *_args):
            if self.save_job is not None:
                try:
                    self.root.after_cancel(self.save_job)
                except tk.TclError:
                    pass
            self.save_job = self.root.after(450, self.save_settings)

        def collect_config(self, enabled=None, mode=None):
            config = load_cfg(self.config_path)
            st = config["status"]
            st["messages"] = messages_from_slots(var.get() for var in self.fields)
            mq = st["marquee"]
            try:
                mq["step_seconds"] = max(MARQUEE_STEP_MIN, float(self.step.get()))
                mq["stride"] = max(1, int(float(self.stride.get())))
                mq["infinite_loop"] = bool(self.infinite_loop.get())
            except ValueError as exc:
                raise ValueError(self._tr("Enter valid marquee speed values.",
                                          "กรอกค่าความเร็วข้อความเลื่อนให้ถูกต้อง")) from exc
            if mode is not None:
                st["random"] = mode == "random"
                mq["enabled"] = mode == "marquee"
            if enabled is not None:
                st["enabled"] = enabled
            if st["enabled"] and not st["messages"]:
                raise ValueError(self._tr("Enter at least one status.", "กรอกสถานะอย่างน้อยหนึ่งข้อความ"))
            errors, _warnings = validate(config)
            if errors:
                raise ValueError("\n".join(errors))
            return config

        def save_settings(self, enabled=None, mode=None, notify=False):
            self.save_job = None
            try:
                config = self.collect_config(enabled=enabled, mode=mode)
                write_config(self.config_path, config)
                runtime = runtime_config(config)
                write_config(self.runtime_config_path, runtime)
                self.config = config
                if notify:
                    self.note.configure(text=self._tr("Saved to shared config.json",
                                                      "บันทึกใน config.json แล้ว"))
                return config
            except (OSError, ValueError, KeyError) as exc:
                self.note.configure(text=str(exc), foreground="#a52834")
                return None

        def apply_now(self):
            """Immediately apply the selected or first configured status to Camfrog."""
            config = self.save_settings()
            if config is None:
                return

            chosen = None
            try:
                focused = self.root.focus_get()
                for entry, var in self.entry_widgets:
                    if entry == focused:
                        val = var.get().strip()
                        if val:
                            chosen = val
                            break
            except Exception:
                pass

            if not chosen:
                msgs = messages_from_slots(var.get() for var in self.fields)
                if msgs:
                    chosen = msgs[0]

            if not chosen:
                self.note.configure(text=self._tr("Enter a status text to apply.",
                                                  "กรอกข้อความสถานะที่จะใช้"),
                                    foreground="#a52834")
                return

            if isinstance(chosen, dict):
                status_str = chosen.get(LANG, "") or chosen.get("th") or chosen.get("en") or ""
            else:
                status_str = str(chosen)

            def do_apply():
                cfg = load_cfg(self.config_path)
                cfg_copy = copy.deepcopy(cfg)
                cfg_copy.setdefault("safety", {})["require_foreground"] = False
                try:
                    return cmd_status(cfg_copy, status_str)
                except LookupError:
                    if cmd_detect(cfg, self.config_path, apply=True) == 0:
                        cfg = load_cfg(self.config_path)
                        cfg_copy = copy.deepcopy(cfg)
                        cfg_copy.setdefault("safety", {})["require_foreground"] = False
                        return cmd_status(cfg_copy, status_str)
                    raise

            display_preview = status_str[:22] + "…" if len(status_str) > 22 else status_str
            self.run_task(do_apply, self._tr(f"Applied: {display_preview}",
                                             f"เปลี่ยนสถานะแล้ว: {display_preview}"))

        def _auto_start_if_idle(self):
            try:
                config = load_cfg(self.config_path)
                if not config.get("status", {}).get("enabled", False):
                    return
                main_pid = running_pid(config)
                if not main_pid:
                    self._start_worker(config)
            except Exception as exc:
                logging.debug("Auto-start check failed: %s", exc)

        def set_enabled(self, mode, enabled):
            config = self.save_settings(enabled=enabled, mode=mode)
            if config is None:
                return
            self.mode = mode
            if enabled:
                main_pid = running_pid(config)
                worker_pid = self._worker_pid()
                if main_pid:
                    if worker_pid == main_pid:
                        self.note.configure(text=self._tr("Status worker is already running.",
                                                          "ตัวเปลี่ยนสถานะกำลังทำงานอยู่"),
                                             foreground="#138a55")
                    else:
                        self.note.configure(text=self._tr("Settings saved for the running bot.",
                                                          "บันทึกค่าให้บอทที่กำลังทำงานแล้ว"),
                                             foreground="#138a55")
                    return
                self._start_worker(config)
            else:
                main_pid = running_pid(config)
                worker_pid = self._worker_pid()
                if main_pid and worker_pid == main_pid:
                    runtime = runtime_config(config)
                    self.run_task(lambda: self._stop_worker(runtime),
                                  self._tr("Status worker stopped.", "หยุดตัวเปลี่ยนสถานะแล้ว"))
                else:
                    self.note.configure(text=self._tr("Status rotation disabled.",
                                                      "ปิดการเปลี่ยนสถานะแล้ว"), foreground="#53636d")

        def _start_worker(self, config):
            runtime = runtime_config(config)
            args = SimpleNamespace(config=str(self.runtime_config_path), lang=None)

            def start():
                rc = cmd_start_worker(runtime, args)
                if rc == 0:
                    pid = running_pid(runtime)
                    if not pid:
                        raise RuntimeError(self._tr(
                            "Worker started but its process could not be verified.",
                            "เริ่ม worker แล้วแต่ตรวจสอบโปรเซสไม่ได้"))
                    try:
                        self.worker_marker_path.write_text(str(pid), encoding="ascii")
                    except OSError:
                        # Do not leave an untracked worker if its ownership marker
                        # cannot be written; roll it back before reporting failure.
                        cmd_stop(runtime)
                        raise
                return rc

            self.run_task(start, self._tr("Status worker started.", "เริ่มตัวเปลี่ยนสถานะแล้ว"))

        def _stop_worker(self, runtime):
            result = cmd_stop(runtime)
            if result in (None, 0):
                self.worker_marker_path.unlink(missing_ok=True)
            return result

        def _worker_pid(self):
            try:
                pid = int(self.worker_marker_path.read_text(encoding="ascii").strip())
                return pid if pid_alive(pid) else None
            except (OSError, ValueError):
                return None

        def run_task(self, function, done_text, on_done=None):
            if self.busy:
                return False
            self.busy = True
            self.note.configure(text=self._tr("Working…", "กำลังทำงาน…"), foreground="#53636d")

            def worker():
                try:
                    result = function()
                    text = done_text if result in (None, 0) else self._tr("Command failed.", "คำสั่งไม่สำเร็จ")
                    ok = result in (None, 0)
                except Exception as exc:
                    text, ok = str(exc), False
                self.task_results.put((text, ok, on_done))

            try:
                threading.Thread(target=worker, daemon=True, name="camfrog-status-task").start()
                return True
            except RuntimeError as exc:
                self.busy = False
                self.note.configure(text=str(exc), foreground="#a52834")
                return False

        def poll_task_results(self):
            try:
                while True:
                    text, ok, on_done = self.task_results.get_nowait()
                    self.finish_task(text, ok, on_done)
            except queue.Empty:
                pass
            except Exception as exc:
                logging.exception("Could not process Status Changer task result")
                if self.root.winfo_exists():
                    self.note.configure(text=str(exc), foreground="#a52834")
            try:
                self.task_poll_job = self.root.after(100, self.poll_task_results)
            except tk.TclError:
                self.task_poll_job = None

        def finish_task(self, text, ok, on_done=None):
            self.busy = False
            self.note.configure(text=text, foreground="#138a55" if ok else "#a52834")
            self.refresh_state()
            close_after_task = self.close_requested
            self.close_requested = False
            if on_done:
                on_done(ok)
            if close_after_task:
                try:
                    if self.root.winfo_exists():
                        self.close_app()
                except tk.TclError:
                    pass

        def on_close(self):
            if getattr(self, "tray", None) and self.tray.active:
                self.hide_to_tray()
            else:
                self.exit_app()

        def hide_to_tray(self):
            try:
                self.root.withdraw()
                self.note.configure(
                    text=self._tr("Hidden in system tray. Click icon to restore.",
                                  "ซ่อนใน system tray แล้ว คลิกไอคอนเพื่อเปิด"),
                    foreground="#53636d",
                )
            except tk.TclError:
                pass

        def show_from_tray(self):
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except tk.TclError:
                pass

        def exit_app(self):
            if getattr(self, "tray", None):
                self.tray.shutdown()
            self.close_app()

        def close_app(self):
            """Exit fully, stopping only the status-only worker this window owns."""
            if self.busy:
                self.close_requested = True
                self.note.configure(text=self._tr(
                    "Finishing the current task before exit…",
                    "รอให้งานปัจจุบันเสร็จแล้วปิดโปรแกรม…"), foreground="#53636d")
                return
            try:
                config = load_cfg(self.config_path)
                worker_pid = self._worker_pid()
                main_pid_val = running_pid(config)
                if worker_pid and worker_pid == main_pid_val:
                    runtime = runtime_config(config)
                    self.note.configure(text=self._tr(
                        "Stopping the status worker before exit…",
                        "กำลังหยุดตัวเปลี่ยนสถานะก่อนออก…"), foreground="#53636d")
                    started = self.run_task(
                        lambda: self._stop_worker(runtime),
                        self._tr("Status worker stopped.", "หยุดตัวเปลี่ยนสถานะแล้ว"),
                        on_done=self._close_after_worker_stop,
                    )
                    if started:
                        return
                if self.worker_marker_path.exists() and not worker_pid:
                    self.worker_marker_path.unlink(missing_ok=True)
            except Exception as exc:
                logging.exception("Could not prepare a clean Status Changer exit")
                messagebox.showerror(
                    "Camfrog Status Changer",
                    self._tr(
                        f"Could not verify worker shutdown: {exc}",
                        f"ตรวจสอบการหยุด worker ไม่สำเร็จ: {exc}"),
                    parent=self.root,
                )
                return
            self._finalize_close()

        def _close_after_worker_stop(self, ok):
            if ok:
                self._finalize_close()
            else:
                self.note.configure(text=self._tr(
                    "Worker did not confirm shutdown. The window stays open so you can retry.",
                    "worker ยังไม่ยืนยันว่าหยุดแล้ว หน้าต่างยังเปิดไว้ให้ลองใหม่"),
                    foreground="#a52834")

        def _finalize_close(self):
            if getattr(self, "tray", None):
                self.tray.shutdown()
            if self.save_job is not None:
                try:
                    self.root.after_cancel(self.save_job)
                except tk.TclError:
                    pass
                self.save_job = None
                self.save_settings()
            for job in (self.state_job, self.task_poll_job):
                if job is not None:
                    try:
                        self.root.after_cancel(job)
                    except tk.TclError:
                        pass
            try:
                self.root.quit()
            except tk.TclError:
                pass
            try:
                self.root.destroy()
            except tk.TclError:
                pass

        def _register_single_instance_handler(self):
            """Subclass the Tk root window proc to handle WM_SHOWME from second instance."""
            if os.name != "nt":
                return
            try:
                import ctypes
                self.user32 = ctypes.WinDLL("user32", use_last_error=True)
                self.user32.SetWindowLongPtrW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
                self.user32.SetWindowLongPtrW.restype = ctypes.c_void_p
                self.user32.CallWindowProcW.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
                self.user32.CallWindowProcW.restype = ctypes.c_void_p

                self.root.update_idletasks()
                hwnd = self.root.winfo_id()

                def new_wndproc(hwnd, msg, wparam, lparam):
                    if msg == SingleInstanceGuard.WM_SHOWME:
                        self.root.after(0, self.show_from_tray)
                        return 0
                    return self.user32.CallWindowProcW(self.old_wndproc, hwnd, msg, wparam, lparam)

                self.new_wndproc = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)(new_wndproc)

                GWLP_WNDPROC = -4
                self.old_wndproc = self.user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, self.new_wndproc)
            except Exception:
                pass

        def refresh_state(self):
            if not self.root.winfo_exists():
                return
            try:
                config = load_cfg(self.config_path)
                pid = running_pid(config)
                worker = self._worker_pid()
                running = bool(pid)
                self.state_label.configure(
                    text=(self._tr("WORKER", "ตัวเปลี่ยน") if running and pid == worker else
                          self._tr("RUNNING", "ทำงาน") if running else
                          self._tr("STOPPED", "หยุด")),
                    foreground="#138a55" if running else "#697780",
                )
            except Exception:
                pass
            self.state_job = self.root.after(1200, self.refresh_state)

        def mainloop(self):
            self.root.mainloop()

    return StatusChanger


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)

    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    # Single-instance guard: a second launch restores the existing window
    # (posted as WM_SHOWME in acquire()) and exits silently.
    instance = SingleInstanceGuard()
    if not instance.acquire():
        return 0

    try:
        config_path = BASE / "config.json"
        if "--config" in argv:
            index = argv.index("--config")
            if index + 1 < len(argv):
                config_path = Path(argv[index + 1])
        try:
            app = build_app()(config_path)
        except SystemExit as exc:
            return exc.code
        except Exception as exc:
            print(f"Status Changer failed: {exc}")
            return 1
        app.mainloop()
        return 0
    finally:
        instance.release()


if __name__ == "__main__":
    sys.exit(main())
