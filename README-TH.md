# แอป Camfrog แยกตามฟีเจอร์

ใช้ได้เฉพาะ Windows ใช้ UI Automation Selector มาจากการวิเคราะห์ Camfrog 8.5.0.51219 แบบ static และ**ยังไม่ได้ทดสอบกับ Camfrog จริง** ต้องตั้ง selector เอง — รัน `detect` ก่อน

คู่มือผู้ใช้ฉบับเต็ม: `docs/USER-MANUAL-TH.md` (English: `docs/USER-MANUAL-EN.md`)

## แอปแยกตามฟีเจอร์

แต่ละ exe อยู่คนละโฟลเดอร์และสร้างไฟล์ตั้งค่า/ข้อมูลของตัวเอง ไม่ใช้ config, log, รายการสถานะ หรือประวัติร่วมกัน

| แอป | ขอบเขต |
|---|---|
| `room-control\room-control.exe` | ควบคุมห้องและตอบอัตโนมัติในห้อง ปิดการเปลี่ยนสถานะและการตอบ IM ส่วนตัว |
| `chat-im-private\chat-im-private.exe` | แสดงและโฟกัสหน้าต่างแชทส่วนตัวที่เปิดอยู่ใน Camfrog ไม่มีการอ่านหรือส่งข้อความ |
| `status-random\status-random.exe` | สลับสถานะแบบสุ่ม มี pool สิบช่องของตัวเองใน `random-data\` |
| `status-marquee\status-marquee.exe` | สลับสถานะแบบเลื่อน มี pool สิบช่องของตัวเอง ตัวควบคุม Loop ใน `marquee-data\` |
| `im-autoreply\im-autoreply.exe` | ตอบ IM ส่วนตัวอย่างเดียว ไม่ตอบในห้อง ไม่เปลี่ยนสถานะ |
| `music-dj\music-dj.exe` | ดีเจเพลงในห้อง: รับคำสั่ง `!request` / `!queue` / `!current` / `!skip` / `!help` จากแชท เก็บคิวลงไฟล์ และเล่นไฟล์ `.wav` บนเครื่องส่งเข้า Camfrog ได้ ปิดการเปลี่ยนสถานะและการตอบ IM ส่วนตัว |
| `web-status\web-status.exe` | รุ่นทดลองแบบ GUI + console: เปลี่ยนสถานะผ่าน profiles.camfrog.com (ค่าเริ่มต้นโหมดทดลอง รหัสผ่านถามตอนรันหรือใช้ session cookie จาก Chrome ไม่เก็บความลับ) ไม่ใส่ argument เปิด GUI ใส่ argument ใช้ CLI ปุ่ม **Start** สลับ pool หลายบรรทัดอัตโนมัติทุก N วินาที (gate เดียวกัน) |

Room Control และ IM Auto-reply ใช้ `config.json` แยกกัน ส่วน Chat IM Private ใช้ `private-chat-config.json` และ Random/Marquee ใช้ `camfrog-status-config.json` ในโฟลเดอร์ข้อมูลคนละชุด แต่ละแอปแยก pool, log, ประวัติ และ worker ปุ่ม **Start** จะบันทึกค่าและเริ่ม worker ของแอปนั้น

## สร้าง exe

ดับเบิลคลิก `build.bat` (ต้องมี Python 64-bit) ระบบเลือก Python 3.12 และสร้างหกแอปแยกโฟลเดอร์ใน `dist\` โดยเก็บ config/ข้อมูลเดิมของแต่ละแอปไว้เมื่อ build ใหม่ ไม่คัดลอก config กลาง และสร้าง zip ที่มีเฉพาะ exe กับ checksums นอกจากนี้ยังเขียน `dist\SHA256SUMS.txt`

- **ไอคอน:** เปลี่ยนไฟล์ `app.ico` (ไฟล์ `.ico` หลายขนาดจริง 16–256 px) แล้ว build ใหม่ ถ้า Explorer ยังโชว์ไอคอนเก่าคือ cache ของ Windows ให้ย้ายหรือเปลี่ยนชื่อ exe หรือรีสตาร์ท Explorer
- **Checksums และ zip:** `SHA256SUMS.txt` ระบุ path ของ exe แต่ละตัว และสร้าง zip ด้วย Python ตรวจแฮชด้วย `certutil -hashfile dist\room-control\room-control.exe SHA256`

### แก้ปัญหา build

รัน **`doctor.bat`** ก่อน จะบอกเวอร์ชัน/บิตของ Python ตรวจรุ่นที่ใช้ไม่ได้ ตรวจว่าไฟล์โปรเจกต์เป็นของเก่าไหม และลองโหลด `pywin32`

ไม่มี wheel สำหรับ Python ของคุณ (`pywin32 ... no matching distribution`): pywin32 312 มี wheel สำหรับ CPython 3.9–3.15 แบบ **64-bit (และ ARM64) เฉพาะ 3.9–3.13** ใช้ไม่ได้กับ Python 32-bit รุ่น ≤ 3.13, รุ่น free-threaded, PyPy, Python < 3.8 แก้โดยติดตั้ง Python 3.13 แบบ 64-bit ลบ `.venv` แล้วรัน `build.bat` ใหม่

ถ้า error ขึ้น `requirements.txt (line 1)` และพูดถึงแต่ pywinauto แปลว่าใช้ไฟล์เก่า ให้แตก zip ล่าสุดลงโฟลเดอร์ใหม่

## เริ่มต้นใช้งาน

1. เปิด Camfrog แล้วเข้าห้อง สำหรับ Camfrog 8.x เปิด `room-control.exe` แล้วใช้ **Setup → Auto-detect** ผลวิเคราะห์: `docs/CAMFROG-8.5-FINDINGS.md`
2. แก้ `config.json` ของแอปนั้น ตั้งนิค ตั้งกฎตอบ คง `dry_run` ไว้ขณะทดสอบ
3. ใช้ `im-autoreply.exe` สำหรับตอบ IM ส่วนตัว config และ log แยกจาก Room Control
4. ใช้ `status-random.exe` หรือ `status-marquee.exe` ตั้งข้อความในโฟลเดอร์ข้อมูลของแอปนั้น โดยค่าเริ่มต้นเป็นโหมดทดลอง ให้เปิด **Send statuses live to Camfrog** ก่อนกด **Apply Now** หรือ **Start** เพื่อส่งสถานะจริง
5. เปิดแชทส่วนตัวใน Camfrog แล้วใช้ `chat-im-private.exe` refresh และโฟกัสหน้าต่าง ปุ่ม **Discover controls** ดึงรายการ control ลง `controls.txt` เพื่อตั้ง selector เหมือนแอปอื่น

คำสั่ง `python camfrog_auto.py ...` ยังใช้เป็น CLI สำหรับพัฒนา โดยใช้ `config.json` ในเครื่องซึ่ง Git จะไม่ติดตาม สร้างได้ด้วย `python camfrog_auto.py init --config config.json` หรือคัดลอกจาก `config.example.json` ส่วน CI และ build ตรวจด้วยตัวอย่างที่ปลอดภัย CLI นี้ไม่ใช่หนึ่งในหกแอปที่ build คำสั่งใน `extras\*.bat` เป็นทางลัด ยกเว้น `extras\gui.bat` ที่เปิด `dist\room-control\room-control.exe` ที่ build แล้ว

## รันเบื้องหลัง

Room Control และ IM Auto-reply มีปุ่ม **Save & Start** กับ **Stop** ส่วนแอปสถานะมีปุ่มของตัวเองและ worker ที่มากับ exe

| คำสั่ง | คำอธิบาย |
|---|---|
| `python camfrog_auto.py start --config config.json` | CLI จาก source: รันแบบซ่อน |
| `python camfrog_auto.py state --config config.json` | CLI จาก source: ดูสถานะ |
| `python camfrog_auto.py stop --config config.json` | CLI จาก source: หยุดการทำงาน |

แต่ละแอปบันทึก log ในโฟลเดอร์ของ config ตัวเอง ส่วน source CLI ใช้ `camfrog_auto.log` ในโฟลเดอร์ repository

**ข้อควรรู้:** Windows พิมพ์ลงแอปอื่นโดยไม่โฟกัสไม่ได้ ทุกครั้งที่ส่ง โปรแกรมจะดึง Camfrog ขึ้นมาหน้าสุดชั่วครู่ กด Enter แล้วคืนโฟกัสให้หน้าต่างเดิม (`safety.restore_previous_window`) Camfrog ต้องเปิดอยู่ (ย่อไว้ได้เฉพาะเมื่อ UIA ยังเข้าถึง control — ตรวจด้วย `discover`)

## สถานะเลื่อน + สลับจากประวัติ

- **สถานะเลื่อน** (`status.marquee`): ข้อความยาวเลื่อนผ่านหน้าต่างกว้าง `width` ตัวอักษร เฟรมละ `step_seconds` วินาที (ขั้นต่ำ 0.5 วินาที) วน `cycles` รอบ (จำกัดด้วย `max_frames`) แล้วหยุดที่ข้อความเต็มจนกว่าจะสลับครั้งหน้า ค่าเริ่มต้นเลื่อน 2 กลุ่มอักษรทุก 0.5 วินาที ตัวรันจะตื่นตามกำหนดเฟรมและไม่เพิ่มเวลาหน่วงสุ่มหลังส่ง โดยยังไม่ตัดสระ/วรรณยุกต์และไม่สร้างเฟรมว่าง
- **สลับจากประวัติ** (`status.history`): ทุก status ที่ตั้งถูกเก็บลง `status_history.json` ถ้าเปิด `use_as_source` จะสลับเลือกจากประวัติให้อัตโนมัติ (`rotate` = วนรอบ, `random`, `most_used`) ข้อความใน `status.messages` ถูกใส่เข้าไปอัตโนมัติ
- **สลับไทย-อังกฤษอัตโนมัติ** (`status.language_cycle: ["th","en"]`): สลับไทย→อังกฤษ→ไทย… ทุกครั้งที่เปลี่ยน status ใช้ได้ทั้งประวัติและข้อความปกติ
- **ความปลอดภัย:** ทุกเฟรมคือการเปลี่ยน status จริง จึงจำกัดความถี่ขั้นต่ำ 0.5 วินาทีและจำนวนเฟรมต่อรอบ ควรตั้ง `interval_seconds` ให้เหมาะสม เริ่มด้วย `dry_run: true`
- **ส่งสถานะจริง:** แอปสถานะเริ่มในโหมดทดลอง ปุ่ม **Apply Now** จะแจ้งว่ายังไม่ได้ส่งจนกว่าจะเปิด **Send statuses live to Camfrog** โหมดจริงจะโฟกัส Camfrog ตอนกด Enter แล้วคืนหน้าต่างเดิม
- **เป้าหมาย Enter เบื้องหลัง (ทดลอง):** ถ้า Windows มีเสียง error ทุกครั้งที่เปลี่ยนสถานะ แอป Random และ Marquee มีปุ่ม **Try combo Enter (test)** โปรแกรมจะส่ง Enter ไปที่ ComboBox สถานะแทนช่อง Edit โดยไม่ดึงหน้าต่าง Camfrog ขึ้นมา อาจใช้ไม่ได้กับ Camfrog รุ่นของคุณ ทดสอบหนึ่งสถานะด้วย **Apply Now** แล้วตรวจว่ายังอยู่ก่อนใช้ marquee เอาออกเพื่อกลับพฤติกรรมเดิม ดู `status.background_enter_target` ใน `CONFIG-TH.md`

ดูตัวอย่างโดยไม่ต้องเปิด Camfrog:
```
python camfrog_auto.py marquee "ข้อความยาว ๆ ที่อยากให้เลื่อน" --width 20
python camfrog_auto.py history                       # ดูประวัติ
python camfrog_auto.py history-add "สวัสดีครับ"        # เพิ่ม
python camfrog_auto.py history-import old_status.txt # ไฟล์ละบรรทัด
```

## เครื่องมือเสริม

| คำสั่ง | คำอธิบาย |
|---|---|
| `python camfrog_auto.py init --config config.json` | CLI จาก source: สร้าง config เริ่มต้น |
| `python camfrog_auto.py test-rules "text" --config config.json` | CLI จาก source: ทดสอบกฎแบบออฟไลน์ |
| `python camfrog_auto.py state --config config.json` | CLI จาก source: ดูสถานะและสถิติ |

- **แก้แล้วมีผลทันที:** แก้ไฟล์ตอนรันได้ ถ้าไม่ถูกต้องจะไม่รับและ log ไว้ (การแก้ `dry_run` เป็น `false` โดยไม่มี `own_nickname` จะถูกปฏิเสธ)
- **ตัวแปร:** `{sender}` `{me}` `{time}` `{date}` ใช้ได้ทั้ง status และคำตอบ
- **ตั้งเวลา:** ข้อความ status ต่างกันตามช่วงเวลา (`status.schedules`)
- **ตอบเมื่อถูกเรียกชื่อ:** `"mention": true` ตอบเมื่อมีคนพิมพ์นิคคุณ
- **กันสแปม:** ไม่ตอบข้อความที่มีลิงก์หรือตรงรูปแบบที่กำหนด (`ignore_links` เปิดเป็นค่าเริ่มต้น และ `skip_patterns`)

## พัฒนา

ติดตั้ง `requirements-dev.txt` แล้วรัน test suite แบบออฟไลน์จาก source CI (`.github/workflows/ci.yml`) รัน test บน Ubuntu และ build แอปบน Windows หมายเหตุ audit: `AUDIT.md` คู่มือผู้ใช้ฉบับเต็ม: `docs/USER-MANUAL-TH.md`

## ภาษา

`"language": "auto"` ตามภาษาหน้าจอ Windows เปลี่ยนด้วย `--lang th` หรือ `--lang en` รายการสถานะเป็นคู่ `{th, en}` ได้ และคำตอบตามภาษาข้อความที่เข้ามา — ดู `CONFIG-TH.md`

## ตอบแชทส่วนตัว (ต้องเปิดใช้เอง)

ใช้ `im-autoreply.exe` config ของแอปนี้แยกเฉพาะ แชทในห้องไม่เคยยุ่งกับแชทส่วนตัว การตอบ IM เป็นฟีเจอร์แยก มีกฎของตัวเอง **ต้องระบุรายชื่อเพื่อน** (`only_nicknames`) มี dry-run แยก และเพดานที่เข้มกว่า (ค่าเริ่มต้น: ตอบเพื่อนคนละ 1 ครั้งต่อชั่วโมง วันละ 3 ครั้ง รวมชั่วโมงละ 10 ครั้ง) ทุกคำตอบขึ้นต้นด้วย `[auto] ` และจะไม่ตอบบรรทัดที่มีคำนำหน้านี้ หน้าต่างที่เปิดอยู่ก่อนบอทเริ่มจะไม่ถูกตอบ หน้าต่างที่เปิดใหม่ทีหลังและมีแค่ 1 บรรทัดจากเพื่อนในรายชื่อจะถูกตอบ

ตั้งค่า `autoreply.own_nickname`, `autoreply_im.only_nicknames` และ `autoreply_im.rules` ใน config ของแอปนี้ และคง `dry_run: true` จนตรวจสอบการทำงานแล้ว แล้วค่อยเปิดโหมดจริงเฉพาะแอปนี้เมื่อพร้อม

**ยังไม่ได้ทดสอบกับ Camfrog จริง** ในส่วนการส่งข้อความของหน้าต่าง IM (pane ตรงกับของห้องตามผลวิเคราะห์) ชนิดหน้าต่าง `wb-log-mtim-data` (น่าจะเป็น IM แบบแท็บ) ถูกข้ามโดยตั้งใจ คำขอเปิดแชทส่วนตัว (`private_chat_request`) ไม่ถูกรับอัตโนมัติ ดู `CONFIG-TH.md`

## ความปลอดภัย

`dry_run` เปิดเป็นค่าเริ่มต้น คำตอบถูกจำกัดความถี่ (คูลดาวน์รายคน ช่องว่างรวม เพดานรายชั่วโมง) บรรทัดที่ไม่ใช่รูป `ชื่อ: ข้อความ` ถูกข้าม คำตอบที่ขึ้นต้นด้วย `/` ถูกบล็อก ไม่มีการเตะอัตโนมัติ ตรวจเงื่อนไข Camfrog และกฎห้องก่อนเปิดระบบอัตโนมัติ
