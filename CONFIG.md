# config.json reference / คู่มือ config

Missing keys use built-in defaults. Run `camfrog-auto check` after every edit.
key ที่ไม่ใส่จะใช้ค่าเริ่มต้น รัน `camfrog-auto check` ทุกครั้งหลังแก้

| Key | Default | EN | ไทย |
|---|---|---|---|
| `language` | `auto` | UI/log language: `auto`, `th`, `en` (CLI `--lang` overrides) | ภาษาของข้อความโปรแกรม/ล็อก (`--lang` ทับค่านี้) |
| `reload_config` | `true` | Hot-reload this file when it changes (invalid edits rejected) | โหลด config ใหม่เองเมื่อไฟล์เปลี่ยน (ถ้าไม่ถูกต้องจะไม่รับ) |
| `stats.enabled/file/write_seconds` | `true` / `stats.json` / `60` | Counters shown by `state` | ตัวนับที่ `state` แสดง |
| `window_title_regex` | `.*Camfrog.*` | Regex for the Camfrog window title | regex ชื่อหน้าต่าง Camfrog |
| `dry_run` | `true` | `true` = log only, nothing sent | `true` = แค่ log ไม่ส่งจริง |
| `poll_seconds` | `1.5` | Main loop tick (0.2–60) | ความถี่ลูปหลัก (0.2–60) |
| `log.level/file/max_bytes/backups` | `INFO` / `camfrog_auto.log` | Rotating log. **Background mode needs `file`** | ล็อกหมุนไฟล์ **โหมดเบื้องหลังต้องมี `file`** |
| `log.log_message_text` | `true` | `false` hides chat/status text in logs | `false` = ไม่เก็บเนื้อข้อความใน log |
| `active_hours` | disabled | Act only between `start`–`end` (local, overnight OK). Outside: chat read but never answered | ทำงานเฉพาะช่วงเวลา (ข้ามเที่ยงคืนได้) นอกช่วงจะอ่านแต่ไม่ตอบ |
| `safety.stop_file` | `STOP` | Create this file to stop (cleared on next start) | สร้างไฟล์นี้เพื่อหยุด (ลบเองตอนเริ่มรอบใหม่) |
| `safety.pid_file` | `camfrog_auto.pid` | PID file for background mode / single instance | ไฟล์ PID สำหรับโหมดเบื้องหลัง/กันรันซ้ำ |
| `safety.require_foreground` | `true` | Refuse to press Enter unless Camfrog is foreground | ไม่กด Enter ถ้า Camfrog ไม่อยู่หน้าสุด |
| `safety.restore_previous_window` | `true` | After sending, return focus to the window you were using | ส่งเสร็จแล้วคืนโฟกัสให้หน้าต่างที่คุณใช้อยู่ |
| `safety.max_consecutive_failures` | `5` | Stop after N failed ticks in a row (backoff + re-attach) | หยุดเมื่อล้มเหลวติดกัน N ครั้ง |
| `status.enabled` | `true` | Rotate status | หมุน status |
| `status.edit` / `apply_button` | selectors / `null` | UIA selectors from `discover`; `apply_button` is invoked instead of Enter | selector จาก `discover` ถ้าใส่ `apply_button` จะกดปุ่มแทน Enter |
| `status.background_enter_target` | `edit` | Experimental `combo`: when `safety.require_foreground` is `false`, post Enter to the verified `CComboBoxTS` parent instead of its Edit child. May avoid a Windows error sound, but **not confirmed to save status**. No fallback if the parent is missing. Test with Apply Now, confirm the status in Camfrog, and set back to `edit` if it fails. No effect when an apply button is configured or foreground mode is on. | ตัวเลือกทดลอง `combo`: ส่ง Enter ไป ComboBox แทนช่อง Edit ขณะทำงานเบื้องหลัง ยังไม่ยืนยันว่าบันทึกได้ หากไม่สำเร็จให้กลับเป็น `edit` |
| `status.interval_seconds` | `600` | Minimum 30 | ขั้นต่ำ 30 |
| `status.set_on_start` | `true` | Set first status immediately | ตั้ง status แรกทันที |
| `status.random` | `false` | Random instead of sequential | สุ่มแทนเรียงลำดับ |
| `status.language_mode` | `both` | For `{th,en}` items: `th`, `en`, `both` (`TH \| EN`), `alternate` | สำหรับรายการแบบ `{th,en}`: `th`, `en`, `both` (ต่อกัน), `alternate` (สลับรอบ) |
| `status.schedules[]` | `[]` | `{start, end, messages}`: pool used during that time window (overnight OK); otherwise `status.messages` | ชุดข้อความตามช่วงเวลา (ข้ามเที่ยงคืนได้) นอกช่วงใช้ `status.messages` |
| `status.language_cycle` | `[]` | e.g. `["th","en"]`: alternate languages on every status change (messages or history) | สลับภาษาทุกครั้งที่เปลี่ยน status |
| `status.marquee.enabled` | `false` | Scroll long statuses frame by frame | เลื่อนข้อความยาวทีละเฟรม |
| `status.marquee.width` / `stride` | `28` / `2` | Window size (8–80, ≤ `max_length`) / Thai-safe clusters advanced per frame | ความกว้างหน้าต่าง / จำนวนกลุ่มอักษรที่เลื่อนต่อเฟรม |
| `status.marquee.step_seconds` | `0.5` | Seconds between frames (**min 0.5**); the runner wakes at the frame deadline to avoid extra poll delay | วินาทีต่อเฟรม (**ขั้นต่ำ 0.5**); ตัวรันจะตื่นตามกำหนดเฟรมเพื่อลดเวลารอเกิน |
| `status.marquee.cycles` / `max_frames` | `1` / `80` | Loops (1–5) and hard cap on frames per switch (5–300); then settles on the full text | จำนวนรอบ และเพดานเฟรมต่อการสลับ จากนั้นหยุดที่ข้อความเต็ม |
| `status.marquee.infinite_loop` | `false` | `true` = continuous loop (no settle), frames cycle up to `max_frames` then repeat; `cycles` ignored | `true` = เลื่อนวนลูปไม่หยุด (ไม่หยุดที่ข้อความเต็ม) เฟรมวนซ้ำถึง `max_frames` แล้วเริ่มใหม่ `cycles` จะถูกละเว้น |
| `status.marquee.separator` | `   •   ` | Gap shown between end and restart of the ticker | ช่องว่างระหว่างท้ายข้อความกับจุดเริ่มใหม่ |
| `status.history.enabled` / `file` | `true` / `status_history.json` | Save every status you set | เก็บทุก status ที่ตั้ง |
| `status.history.use_as_source` | `false` | `true` = next status is picked from history (`status.schedules` are then ignored) | `true` = เลือก status ถัดไปจากประวัติ (`schedules` จะไม่ถูกใช้) |
| `status.history.mode` | `rotate` | `rotate` (round-robin, least recently used first), `random`, `most_used` | วนรอบ / สุ่ม / ใช้บ่อยสุด |
| `status.history.seed_from_messages` | `true` | Copy `status.messages` (both languages) into history at start | คัดลอก `status.messages` เข้าประวัติตอนเริ่ม |
| `status.history.record` / `max_items` | `true` / `50` | Record what is sent / keep at most N (least used dropped first) | บันทึกที่ส่ง / เก็บสูงสุด N รายการ |
| `status.max_length` | `120` | Truncate status | ตัดความยาว status |
| `status.messages` | `[]` | Strings or `{ "th": "...", "en": "..." }` objects | ข้อความล้วน หรือ object `{th,en}` |
| `autoreply.enabled` | `true` | Auto reply | ตอบแชทอัตโนมัติ |
| `autoreply.own_nickname` | `""` | Your nick (never answered). **Required for live mode** | นิคของคุณ (ไม่ตอบตัวเอง) **จำเป็นเมื่อรันจริง** |
| `autoreply.history` / `input` | selectors | Chat history control / chat input control | control ประวัติแชท / ช่องพิมพ์ |
| `autoreply.ignore_nicknames` / `only_nicknames` | `[]` | Skip these nicks / answer only these (empty = everyone) | ข้ามนิคเหล่านี้ / ตอบเฉพาะนิคเหล่านี้ |
| `autoreply.per_sender_cooldown_seconds` | `300` | Min gap per person | ระยะห่างขั้นต่ำต่อคน |
| `autoreply.global_min_gap_seconds` | `20` | Min gap between any two replies | ระยะห่างขั้นต่ำระหว่างคำตอบ |
| `autoreply.max_per_hour` | `30` | Hard hourly cap | เพดานต่อชั่วโมง |
| `autoreply.delay_range_seconds` | `[2,5]` | Random delay before replying | หน่วงสุ่มก่อนตอบ |
| `autoreply.max_reply_length` / `max_incoming_length` | `200` / `500` | Output cap / input length for regex | จำกัดความยาวคำตอบ / ข้อความขาเข้า |
| `autoreply.skip_patterns` | `[]` | Regexes; matching messages are never answered | regex ที่ตรงแล้วจะไม่ตอบ |
| `autoreply.ignore_links` | `true` | Never answer messages containing `http://`, `https://`, `www.` | ไม่ตอบข้อความที่มีลิงก์ |
| `autoreply.rules[]` | `[]` | `pattern` (regex, case-insens.), `reply`, optional `cooldown_seconds`, `enabled`, `lang` (`th`/`en`: match only messages in that language), `mention` (`true`: only when `own_nickname` appears in the message). First matching rule wins, so put specific rules first | `pattern` (regex), `reply`, และเลือกใส่ `cooldown_seconds`, `enabled`, `lang`, `mention` (ตอบเมื่อมีนิคคุณในข้อความ) กฎแรกที่ตรงชนะ จึงควรวางกฎเฉพาะไว้ก่อน |

## Private-message (IM) auto-reply / ตอบแชทส่วนตัวอัตโนมัติ
Off by default and separate from room auto-reply: its own rules, allowlist and limits. It reuses `autoreply.history` / `autoreply.input` / `autoreply.own_nickname`. Only windows whose log pane is `wb-log-im-data` are touched; room windows and the unverified `wb-log-mtim-data` kind are never answered. If nothing is answered, run `camfrog-auto im-probe` (lists config problems and how each Camfrog window is classified). Test offline with `camfrog-auto test-rules "text" --sender Friend --im`.
ปิดไว้เป็นค่าเริ่มต้น แยกจากการตอบในห้อง มีกฎ รายชื่อเพื่อน และเพดานของตัวเอง ใช้ selector และ `own_nickname` ชุดเดียวกับ `autoreply` ทดสอบออฟไลน์ด้วย `test-rules ... --im`

| Key / คีย์ | Default | EN | ไทย |
|---|---|---|---|
| `autoreply_im.enabled` | `false` | Opt in to IM auto-reply | เปิดใช้การตอบแชทส่วนตัว |
| `autoreply_im.dry_run` | `true` | IM has its own dry-run. The global `dry_run: true` always wins | IM มี dry-run ของตัวเอง ถ้า `dry_run` หลักเป็น `true` จะชนะเสมอ |
| `autoreply_im.only_nicknames` | `[]` | **Required, non-empty.** Only these friends are ever answered (case-insensitive) | **ต้องมีอย่างน้อย 1 คน** ตอบเฉพาะเพื่อนในรายการนี้ |
| `autoreply_im.rules[]` | `[]` | Same format as `autoreply.rules`, but IM-only: room rules never answer a private chat | รูปแบบเดียวกับ `autoreply.rules` แต่ใช้เฉพาะ IM กฎของห้องไม่ตอบแชทส่วนตัว |
| `autoreply_im.skip_patterns` / `ignore_links` | `[]` / `true` | Never answer matching messages / messages with links | ไม่ตอบข้อความที่ตรง / มีลิงก์ |
| `autoreply_im.prefix` | `"[auto] "` | Put in front of every reply so friends know it is automatic. Incoming lines that start with it are never answered (no bot-to-bot ping-pong). Must not start with `/` | ใส่หน้าทุกคำตอบให้เพื่อนรู้ว่าเป็นอัตโนมัติ ข้อความที่ขึ้นต้นด้วยค่านี้จะไม่ถูกตอบ ห้ามขึ้นต้นด้วย `/` |
| `autoreply_im.answer_first_message` | `true` | A window that opens while the bot runs with exactly one line, from a listed friend, is answered. Windows already open at start, and windows with several lines (reloaded history), are baselined silently | หน้าต่างที่เปิดใหม่ขณะบอทรันและมีแค่ 1 บรรทัดจากเพื่อนในรายการจะถูกตอบ หน้าต่างที่เปิดอยู่แล้วหรือมีหลายบรรทัดจะไม่ถูกตอบ |
| `autoreply_im.per_sender_cooldown_seconds` | `3600` | Min gap per friend (min 60) | ระยะห่างขั้นต่ำต่อเพื่อน (ขั้นต่ำ 60) |
| `autoreply_im.max_per_sender_per_day` | `3` | Rolling 24 h cap per friend (1–50) | เพดานต่อเพื่อนใน 24 ชม. (1–50) |
| `autoreply_im.max_per_hour` / `global_min_gap_seconds` | `10` / `20` | Hourly cap (1–100) and min gap between any two IM replies, across all windows | เพดานต่อชั่วโมง และระยะห่างระหว่างคำตอบ IM ทุกหน้าต่าง |
| `autoreply_im.delay_range_seconds` | `[2,5]` | Random delay before replying | หน่วงสุ่มก่อนตอบ |
| `autoreply_im.max_reply_length` / `max_incoming_length` | `200` / `500` | Reply cap (the prefix counts and is never cut) / input length for regex | จำกัดความยาวคำตอบ (รวม prefix) / ข้อความขาเข้า |
| `autoreply_im.log_kinds` | `["im"]` | Window kinds treated as private chat. `im` is the verified one; add `mtim` only if `im-probe` shows your private chats are `MTIM` windows (unverified) | ชนิดหน้าต่างที่ถือว่าเป็นแชทส่วนตัว เพิ่ม `mtim` เฉพาะเมื่อ `im-probe` แสดงว่าแชทส่วนตัวของคุณเป็น `MTIM` |
| `autoreply_im.max_windows` | `5` | Most private-chat windows tracked at once (1–20) | จำนวนหน้าต่างแชทส่วนตัวสูงสุดที่ติดตาม |
| `autoreply_im.window_title_regex` | `""` | Optional filter on the IM window title | กรองตามชื่อหน้าต่าง IM (ไม่บังคับ) |

Validation (errors, not warnings, when `enabled`): empty `only_nicknames`; empty `autoreply.own_nickname` (the bot would answer itself; also refused in dry-run); `autoreply.log_kind` other than `room` while room auto-reply is on; bad regexes; out-of-range limits. Incoming message text is never written to the log; only the friend's nick and your own canned reply are.

## `reply` formats / รูปแบบ `reply`
- `"text"` — one reply / คำตอบเดียว
- `["a","b"]` — random pick / สุ่มเลือก
- `{ "th": [...], "en": [...] }` — language follows the incoming message (any Thai character = `th`, else `en`); falls back to the other language if one is missing / ภาษาตามข้อความที่เข้ามา (มีตัวอักษรไทย = `th`) ถ้าขาดภาษาใดจะใช้อีกภาษาแทน

Variables in statuses and replies: `{sender}` (replies only), `{me}` (your nick), `{time}` (HH:MM), `{date}` (YYYY-MM-DD). Replies starting with `/` are always blocked, so rules can never emit room commands.
ตัวแปรใน status และคำตอบ: `{sender}` นิคผู้ส่ง (เฉพาะคำตอบ), `{me}` นิคคุณ, `{time}` เวลา, `{date}` วันที่ คำตอบที่ขึ้นต้นด้วย `/` ถูกบล็อกเสมอ จึงไม่มีทางส่งคำสั่งห้อง

## Validation notes / หมายเหตุการตรวจ
- Selectors with no criteria (none of `control_type`, `auto_id`, `class_name`, `title`, `title_re`) are errors. Identical selectors for `status.edit`, `autoreply.history`, `autoreply.input` are a warning in dry-run and an **error when `dry_run` is false** (one control would be driven for two jobs). / selector ที่ไม่มีเงื่อนไข = error, selector ซ้ำกัน = คำเตือนตอนทดลอง และ **error ตอนรันจริง**
- Ranges: `poll_seconds` 0.2–60, `safety.max_consecutive_failures` 1–100, `status.max_length` 1–500, `status.retry_seconds` 1–3600, `autoreply.max_reply_length` 1–500, `autoreply.max_incoming_length` 1–2000.
- More than 25 new chat lines in one poll (room switch / history reload) are treated as a reset and never answered. / ข้อความใหม่เกิน 25 บรรทัดต่อรอบ ถือเป็นการรีเซ็ต ไม่ตอบ
- In regexes do not wrap Thai words in `\b` (Thai has no word boundaries): use `เว็บพนัน`, not `\bเว็บพนัน\b`. / อย่าครอบคำไทยด้วย `\b`
