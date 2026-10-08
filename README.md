# camfrog-auto — Auto status + auto reply for Camfrog / ตั้ง status + ตอบแชทอัตโนมัติ

Windows only. Uses UI Automation. Selectors are derived from static analysis of Camfrog 8.5.0.51219 and **not yet verified on a live session** — run `detect` first.
ใช้ได้เฉพาะ Windows ใช้ UI Automation **ยังไม่ได้ทดสอบกับ Camfrog จริง** ต้องตั้ง selector เอง

## GUI / หน้าจอควบคุม
Double-click `camfrog-auto-gui.exe` (or `gui.bat`), or run `python camfrog_gui.py`. Tabs: **Dashboard** (state, Save & Start, Stop, EMERGENCY STOP, live log, DRY-RUN/LIVE switch), **Setup** (window regex, nickname, selectors, *List windows*, *Discover*), **Status** (messages, marquee preview, history source), **Auto-reply** (separate Room and Private IM editors with their limits, allowlist, rules and skip patterns), **History**, **Advanced**. Text and entry fields support Ctrl+C/X/V/A and right-click clipboard menus. Valid GUI changes auto-apply after a short pause; turn off **Auto-apply** to edit several fields before saving. Invalid values never overwrite the config. If a LIVE bot is running, auto-apply pauses and **Save** asks before applying changes the bot could hot-reload. `TH / EN` switches the language. Closing the window does **not** stop the bot. The same exe accepts CLI commands (`camfrog-auto-gui.exe check`).
ดับเบิลคลิก `camfrog-auto-gui.exe` หรือ `gui.bat` แก้ค่า เริ่ม/หยุดบอท ดูล็อกสด และทดสอบกฎได้ในหน้าเดียว หน้า Auto-reply แยกตั้งค่าห้องและ IM รวมถึงเพดาน รายชื่อที่อนุญาต กฎ และรายการข้าม ช่องข้อความรองรับ Ctrl+C/X/V/A และเมนูคลิกขวา ค่าที่ถูกต้องจะบันทึกอัตโนมัติหลังหยุดแก้ชั่วครู่ ปิด Auto-apply เพื่อแก้หลายค่าก่อนบันทึก หากบอท LIVE กำลังทำงาน Auto-apply จะพักไว้ และปุ่ม Save จะถามก่อนใช้ค่าที่บอทอาจโหลดไปส่งข้อความจริง การปิดหน้าต่างไม่หยุดบอท

Double-click `zcfato.exe` for the resizable standalone status editor. Its **Random Status** and **Marquee Status** tabs each have 10 independent slots, stored in `random.db` and `marquee.db` beside its private `camfrog-status-config.json`. The first run copies `config.json` as an initial settings snapshot when available; later saves do not update or read the main app's config. The Marquee tab includes a **Loop** checkbox. The small **TH / EN** dropdown switches the interface language. **Start** saves the pools and selected mode before starting this executable's hidden worker. The worker uses the runner bundled inside the Status Changer; it does not require or start `camfrog-auto.exe` or `camfrog-auto-gui.exe`. **Stop** stops its worker. Clicking **X** or closing the window stops the worker before the Status Changer exits; it does not minimize to the tray or auto-start a worker. Marquee defaults to 2 Thai-safe clusters every 0.5 seconds, timed from completion of each UI update. / ดับเบิลคลิก `zcfato.exe` เพื่อเปิดหน้าต่างปรับขนาดได้แบบ standalone แท็บ **Random Status** และ **Marquee Status** แยกช่องข้อความแท็บละ 10 ช่อง บันทึกไว้ใน `random.db` และ `marquee.db` ข้างไฟล์ตั้งค่าส่วนตัว `camfrog-status-config.json` ครั้งแรกจะคัดลอก `config.json` เป็นค่าเริ่มต้นถ้ามี หลังจากนั้นจะไม่อ่านหรือเขียน config ของแอปหลัก ในแท็บ Marquee มีช่อง **Loop** เมนู **TH / EN** ขนาดเล็กใช้สลับภาษา ปุ่ม **Start** บันทึกรายการและโหมดที่เลือกก่อนเริ่ม worker เบื้องหลังที่มากับไฟล์ Status Changer เอง ไม่ต้องใช้หรือเปิด `camfrog-auto.exe` หรือ `camfrog-auto-gui.exe` ปุ่ม **Stop** หยุด worker ของแอปนี้ เมื่อกด **X** หรือปิดหน้าต่าง โปรแกรมจะหยุด worker ก่อนออก โดยไม่ซ่อนไว้ในถาดระบบและไม่เริ่ม worker อัตโนมัติ ค่า Marquee เริ่มต้นเลื่อน 2 กลุ่มอักษรทุก 0.5 วินาที โดยเริ่มนับจังหวะหลังส่งแต่ละเฟรมเสร็จ

## Build / สร้าง exe
Double-click `build.bat` (needs 64-bit Python in PATH). It selects Python 3.12 first for the compact standalone bundle. Output in `dist\`: `camfrog-auto.exe` (CLI), `camfrog-auto-gui.exe` (full GUI), and `zcfato.exe` (standalone resizable status GUI), plus `config.json` as the main apps' configuration and the Status Changer's first-run template, helper `.bat` files, `SHA256SUMS.txt`, and `camfrog-auto-windows.zip` next to the project. The Status Changer spec keeps its runtime automation modules and omits third-party test submodules and duplicate package source data.
ดับเบิลคลิก `build.bat` (ต้องมี Python 64-bit) ระบบเลือก Python 3.12 ก่อนเพื่อลดขนาดไฟล์ ผลลัพธ์ใน `dist\` มี CLI, GUI หลัก, `zcfato.exe` สำหรับตั้งสถานะแบบ standalone และ `config.json` สำหรับแอปหลักและเป็นต้นแบบครั้งแรกของ Status Changer

- **Icon / ไอคอน:** replace `app.ico` (a real multi-size `.ico`, ideally 16–256 px) and rebuild. If Explorer still shows the old icon it is the Windows icon cache: rename/move the exe or restart Explorer. / เปลี่ยนไฟล์ `app.ico` แล้ว build ใหม่ ถ้า Explorer ยังโชว์ไอคอนเก่าคือ cache ของ Windows ให้ย้ายหรือเปลี่ยนชื่อ exe หรือรีสตาร์ท Explorer
- **Checksums & zip:** `SHA256SUMS.txt` and the zip are made by `tools\package.py` (pure Python), so no PowerShell cmdlets such as `Get-FileHash` are needed. Verify with `certutil -hashfile camfrog-auto.exe SHA256`. / สร้างด้วย Python ล้วน ไม่ต้องพึ่ง PowerShell ตรวจค่าแฮชด้วย `certutil -hashfile camfrog-auto.exe SHA256`

### Build troubleshooting / แก้ปัญหา build
Run **`doctor.bat`** first. It prints your Python version/bit/build type, flags known-bad setups, detects an old copy of this project, and tests whether pip can fetch `pywin32`.
รัน **`doctor.bat`** ก่อน จะบอกเวอร์ชัน/บิตของ Python ตรวจรุ่นที่ใช้ไม่ได้ ตรวจว่าไฟล์โปรเจกต์เป็นของเก่าไหม และลองโหลด `pywin32`

`pywin32 ... no matching distribution` means pip has **no wheel for your Python**. pywin32 312 ships wheels for CPython 3.9–3.15, **64-bit (and ARM64) only on 3.9–3.13**. Not covered: 32-bit Python ≤ 3.13, free-threaded (`3.xt`) builds, PyPy, Python < 3.8. Fix: `winget install Python.Python.3.13` (64-bit), delete the `.venv` folder, run `build.bat` again.
ไม่มี wheel สำหรับ Python ของคุณ: ใช้ไม่ได้กับ Python 32-bit รุ่น ≤ 3.13, รุ่น free-threaded, PyPy แก้โดยติดตั้ง Python 3.13 แบบ 64-bit ลบ `.venv` แล้วรัน `build.bat` ใหม่

If the error says `requirements.txt (line 1)` and mentions only pywinauto, you are running an **older copy** of the project — extract the newest zip into a new empty folder.
ถ้า error ขึ้น `requirements.txt (line 1)` และพูดถึงแต่ pywinauto แปลว่าใช้ไฟล์เก่า ให้แตก zip ล่าสุดลงโฟลเดอร์ใหม่

## Quick start / เริ่มต้นใช้งาน
0. **Camfrog 8.x:** join a room, then run `camfrog-auto detect --apply` (or GUI → Setup → *Auto-detect*) — fills the selectors for you. Findings: `docs/CAMFROG-8.5-FINDINGS.md` / เข้าห้องแชทก่อน แล้วรัน `detect --apply` หรือกดปุ่ม Auto-detect ในหน้า Setup
1. Open Camfrog / เปิด Camfrog
2. If it says the window is not found, run `camfrog-auto windows`, find Camfrog in the list and set `window_title_regex` / ถ้าไม่พบหน้าต่าง รัน `camfrog-auto windows` แล้วตั้ง `window_title_regex`
2. `camfrog-auto discover` → open `controls.txt`, copy `auto_id` / `class_name` / `index` of the status box, chat history and chat input into `config.json` / เปิด `controls.txt` แล้วคัดลอกค่า control ใส่ `config.json`
3. Set `autoreply.own_nickname` / ใส่นิคของคุณ
4. `camfrog-auto check` (validate / ตรวจคอนฟิก)
5. `camfrog-auto status "hello"` (one-shot test / ทดสอบครั้งเดียว)
6. `camfrog-auto run` with `dry_run: true` and watch the log / รันแบบทดลองดู log
7. Set `dry_run: false` when happy / เปลี่ยนเป็น `false` เมื่อพอใจ

## Background mode / รันเบื้องหลัง
One click: GUI **Start & close window**, or double-click `run-background.bat` (stop with `stop.bat`). / คลิกเดียว: ปุ่ม **เริ่มเบื้องหลังแล้วปิดหน้าต่าง** หรือดับเบิลคลิก `run-background.bat` (หยุดด้วย `stop.bat`)

| Command | EN | ไทย |
|---|---|---|
| `camfrog-auto start` (or `start-background.bat`) | Run hidden, no window | รันแบบซ่อน ไม่มีหน้าต่าง |
| `camfrog-auto state` (`state.bat`) | Show if running | ดูว่าทำงานอยู่ไหม |
| `camfrog-auto stop` (`stop.bat`) | Graceful stop (force-kill after 20 s) | หยุดอย่างนุ่มนวล (บังคับปิดหลัง 20 วิ) |
| `camfrog-auto autostart-on` / `autostart-off` | Start in background at Windows login | เริ่มเบื้องหลังตอนเข้า Windows |

Logs go to `camfrog_auto.log` next to the exe. Only one instance can run at a time.
ล็อกอยู่ที่ `camfrog_auto.log` รันได้ทีละ instance เดียว

**Heads-up / ข้อควรรู้:** Windows has no way to type into another app without focusing it. Each send briefly brings Camfrog to the front, presses Enter, then returns focus to your previous window (`safety.restore_previous_window`). Camfrog must be open (minimized is OK only if UIA can still reach its controls — verify with `discover`). 
ทุกครั้งที่ส่ง โปรแกรมจะดึง Camfrog ขึ้นมาหน้าสุดชั่วครู่ กด Enter แล้วคืนโฟกัสให้หน้าต่างเดิม Camfrog ต้องเปิดอยู่

## Scrolling status + history switch / สถานะเลื่อน + สลับจากประวัติ TH/EN
- **Marquee / สถานะเลื่อน** (`status.marquee`): long statuses scroll across a window of `width` characters, one frame every `step_seconds` (minimum 0.5 s), for `cycles` loops (capped by `max_frames`), then settle on the full text until the next switch. The default advances 2 Thai-safe clusters every 0.5 seconds; the runner wakes at each frame deadline without an extra random delay after sending. / ข้อความยาวเลื่อนผ่านหน้าต่างกว้าง `width` ตัวอักษร เฟรมละ `step_seconds` วินาที ค่าเริ่มต้นเลื่อน 2 กลุ่มอักษรทุก 0.5 วินาที ตัวรันจะตื่นตามกำหนดเฟรมและไม่เพิ่มเวลาหน่วงสุ่มหลังส่ง โดยยังไม่ตัดสระ/วรรณยุกต์และไม่สร้างเฟรมว่าง
- **History switch / สลับจากประวัติ** (`status.history`): every status you set is saved to `status_history.json`. With `use_as_source: true` the next status is picked from that history (`rotate` = round-robin, `random`, `most_used`). Your `status.messages` are seeded into it automatically. / ทุก status ที่ตั้งถูกเก็บลงประวัติ ถ้าเปิด `use_as_source` จะสลับเลือกจากประวัติให้อัตโนมัติ
- **TH/EN auto switch / สลับไทย-อังกฤษอัตโนมัติ** (`status.language_cycle: ["th","en"]`): alternates Thai, English, Thai, English… each time the status changes. Works with history and with plain messages. / สลับไทย→อังกฤษ→ไทย… ทุกครั้งที่เปลี่ยน status
- **Safety / ความปลอดภัย:** every frame is a real status change on Camfrog, so frames are rate-limited (`step_seconds >= 0.5`) and bounded per cycle; keep `interval_seconds` generous. Start with `dry_run: true`. / ทุกเฟรมคือการเปลี่ยน status จริง จึงจำกัดความถี่ขั้นต่ำ 0.5 วินาทีและจำนวนเฟรมต่อรอบ ควรตั้ง `interval_seconds` ให้เหมาะสม
- **Experimental background Enter target:** if Windows plays an error sound on every status change, the compact Status Changer has **Try combo Enter (test)**. It posts Enter to the verified status ComboBox instead of its Edit child, without raising the Camfrog window. This might not commit the status on your Camfrog version; test one status with **Apply Now** and verify it persists before using marquee. Uncheck to restore the original behavior. See `status.background_enter_target` in `CONFIG.md`.

Preview offline / ดูตัวอย่างโดยไม่ต้องเปิด Camfrog:
```
camfrog-auto marquee "ข้อความยาว ๆ ที่อยากให้เลื่อน" --width 20
camfrog-auto history                       # list history / ดูประวัติ
camfrog-auto history-add "สวัสดีครับ"        # add / เพิ่ม
camfrog-auto history-import old_status.txt # one status per line / ไฟล์ละบรรทัด
```

## Extra tools / เครื่องมือเสริม
| Command | EN | ไทย |
|---|---|---|
| `init` | Write a starter `config.json` (`--force` to overwrite) | สร้าง `config.json` เริ่มต้น |
| `test-rules "text" [--sender N]` / `--file chat.txt` | Test which rule would answer, **offline, no Camfrog** (same filters as live) | ทดสอบว่ากฎไหนจะตอบ **ออฟไลน์ ไม่ต้องเปิด Camfrog** |
| `state` | Running state + counters (statuses, replies, failures) from `stats.json` | สถานะ + สถิติ |

- **Hot reload / แก้แล้วมีผลทันที:** edit `config.json` while running; valid changes apply within ~3 s, invalid ones are rejected and logged / แก้ไฟล์ตอนรันได้ ถ้าไม่ถูกต้องจะไม่รับและ log ไว้ (การแก้ `dry_run` เป็น `false` โดยไม่มี `own_nickname` จะถูกปฏิเสธ)
- **Variables / ตัวแปร:** `{sender}` `{me}` `{time}` `{date}` in statuses and replies / ใช้ได้ทั้ง status และคำตอบ
- **Schedules / ตั้งเวลา:** different status pools by time of day (`status.schedules`) / ข้อความ status ต่างกันตามช่วงเวลา
- **Mention rules / ตอบเมื่อถูกเรียกชื่อ:** `"mention": true` replies only when your nick appears in the message / ตอบเมื่อมีคนพิมพ์นิคคุณ
- **Spam guard / กันสแปม:** `ignore_links` (default on) and `skip_patterns` / ไม่ตอบข้อความที่มีลิงก์หรือตรงรูปแบบที่กำหนด

## Development / พัฒนา
`pip install -r requirements-dev.txt && pytest` — 105 offline tests, no Windows needed (the GUI smoke test runs only when Tk and a display exist, e.g. `xvfb-run -a pytest`). CI (`.github/workflows/ci.yml`) runs tests on Ubuntu and builds the exes on Windows. Audit notes: `AUDIT.md`.

## Language / ภาษา
`"language": "auto"` follows the Windows UI language. Override with `--lang th` or `--lang en`. Status items can be `{th, en}` pairs and replies follow the language of the incoming message — see `CONFIG.md`.

## Private-message auto-reply / ตอบแชทส่วนตัว (opt-in)
Room auto-reply never touches private chats. IM auto-reply is a separate feature (`autoreply_im` in `config.json`, off by default) with its own rules, a **mandatory friend allowlist** (`only_nicknames`), its own dry-run and stricter limits (default: one reply per friend per hour, 3 per day, 10 per hour). Every reply starts with `[auto] ` so your friend knows it is automatic, and lines carrying that prefix are never answered. Windows already open when the bot starts are never answered; a window that opens later with one line from a listed friend is.
แชทในห้องไม่เคยยุ่งกับแชทส่วนตัว การตอบ IM เป็นฟีเจอร์แยก (`autoreply_im` ปิดไว้ก่อน) มีกฎของตัวเอง **ต้องระบุรายชื่อเพื่อน** (`only_nicknames`) มี dry-run แยก และเพดานที่เข้มกว่า ทุกคำตอบขึ้นต้นด้วย `[auto] `

1. `autoreply.own_nickname` set, then fill `autoreply_im.only_nicknames` and `autoreply_im.rules` / ใส่นิคของคุณ รายชื่อเพื่อน และกฎ
2. `camfrog-auto test-rules "hello" --sender FriendNick --im` (offline / ออฟไลน์)
3. `camfrog-auto check`, then set `autoreply_im.enabled: true` (keep `dry_run: true`), run, open a private chat and watch the log for `[dry-run] would send` / ลองแบบ dry-run ก่อน
4. Set `autoreply_im.dry_run: false` and global `dry_run: false` when happy / เมื่อพอใจค่อยปิด dry-run ทั้งสองที่

**Not answering? / ไม่ตอบ?** Run `camfrog-auto im-probe` with a private chat open: it lists what is wrong in the config (not enabled, no friends, dry-run on, ...) and shows how each Camfrog window is classified (`room` / `IM` / `MTIM`). The log also prints `IM auto-reply ON ...` at start and `no private-chat window found` if none is seen. / รัน `im-probe` ตอนเปิดแชทส่วนตัวไว้ จะบอกว่าตั้งค่าอะไรผิด และแต่ละหน้าต่างถูกจัดเป็นชนิดไหน

**Not verified on a live session:** the IM window's send path (the panes match the room's, per the findings). The `wb-log-mtim-data` window kind (probably tabbed IM) is deliberately ignored. `private_chat_request` (incoming private-chat requests) is never auto-accepted. See `CONFIG.md`.
**ยังไม่ได้ทดสอบกับ Camfrog จริง** ในส่วนการส่งข้อความของหน้าต่าง IM

## Safety / ความปลอดภัย
`dry_run` is on by default; replies are rate-limited (per-sender cooldown, global gap, hourly cap); lines not in `name: message` form are ignored; replies starting with `/` are blocked; there is no auto-kick. Check Camfrog's terms and your room's rules before enabling automation.
