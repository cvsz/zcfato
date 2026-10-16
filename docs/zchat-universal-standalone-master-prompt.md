check prompt " # ZChat Control Server: Architecture and Evidence Boundaries

ZChat Control Server keeps Camfrog-specific behavior behind its provider integration. This document records the current implementation against the supplied browser and source observations. Research summaries are not substitutes for source artifacts or sanitized runtime captures. The implementation keeps these evidence levels separate.

## State separation

`Agent.runtime_state` describes only the polling agent process (`unknown`, `starting`, `running`, `error`, or `disconnected`). It does not mean a Camfrog account is logged in, online, in a room, or that a Cloud Bot is running.

`AccountRuntimeSnapshot.process_state` is account-scoped and reported by the agent. The current Windows adapter can report only the specific process handle it launched; it cannot discover pre-existing Camfrog processes. Reports older than 30 seconds are returned as `unknown`. `room_state` stays `unknown` until a verified live room-status source is available; accepting a deep link does not establish room membership.

The account auth-state detector uses the observed `.nav-user-logged` marker and `external_data.type` values `profile`/`settings`; `public` is kept separate. A CSRF field is reduced to a boolean-presence observation. The server never receives its value. Profile, friends, auth, and human presence are stored as separate snapshots. Public image-based presence remains `UNKNOWN` until it is calibrated against controlled account states, and stale presence becomes `UNKNOWN` after ten minutes.

## Report findings and implementation status

| Report finding | Evidence limit | Current treatment |
|---|---|---|
| Login selectors and authenticated-state marker | UI trace confirms selectors; the added login drill confirms `.nav-user-logged` plus `external_data.type`; login POST fields and redirect chain remain unknown | Bootstrap admin uses a short-lived dashboard JWT. Agent snapshots store only derived auth state, p

## Review: ZChat Control Server — Architecture and Evidence Boundaries

**ผลการตรวจสอบ:** เอกสารนี้มีโครงสร้างที่ดีสำหรับการกำหนด Architecture, Security Boundaries และ Evidence-Based Development แต่ยังไม่ใช่ **Execution Prompt** ที่เพียงพอให้ AI Agent ตรวจสอบ แก้ไข และทำระบบ ZChat ให้ทำงานได้จริงแบบ End-to-End

การประเมินนี้เป็น **Document Review** จากข้อความที่ให้มา ยังไม่ได้ตรวจ Source Code, Runtime Logs หรือ Repository จริง ดังนั้นคำว่า `implemented` ในเอกสารยังถือเป็นสถานะที่ต้องพิสูจน์

<box gap={3}>
  <row align="center" justify="between">
    **Architecture / Evidence Design**
    <badge color="success">Strong Foundation</badge>
  </row>
  <row align="center" justify="between">
    **Security & Reliability**
    <badge color="warning">Needs Hardening</badge>
  </row>
  <row align="center" justify="between">
    **Real Camfrog Integration**
    <badge>Unverified</badge>
  </row>
  <row align="center" justify="between">
    **Production Readiness**
    <badge color="danger">Not Established</badge>
  </row>
</box>

## 1. Critical Findings

| Priority | Finding | Required Action |
|---|---|---|
| P0 | Bootstrap admin authentication ไม่ระบุ Replay Protection, Token Revocation และ Session Lifecycle ครบถ้วน | ตรวจ JWT validation, admin bootstrap, revocation และ RBAC |
| P0 | Agent อาจรายงาน Process State โดยไม่ผูกกับ OS Process Identity | ตรวจ PID, process creation time, executable path และ ownership |
| P0 | Command แบบ at-least-once อาจทำให้เกิด Duplicate Side Effects | เพิ่ม Idempotency Key, Fencing Token และ Reconciliation |
| P0 | ยังไม่มี Verified Camfrog Login/Session Integration | ตรวจสอบ Authorized Runtime Captures และทำ Contract Tests |
| P1 | Per-process Rate Limiter ไม่รองรับ Multi-instance | ใช้ Shared Rate Limiting เช่น Redis |
| P1 | Agent Snapshot อาจเป็น Stale หรือถูกปลอมแปลง | ใช้ Schema Validation, Timestamp, Sequence Number และ Token Scope |
| P1 | Windows GUI Isolation ยังไม่ผ่าน Acceptance | ทดสอบ Interactive Session, Multiple Processes, Restar

if rea client and camfrog.com

ถ้าต้องการให้ **ZChat Control Server ทำงานร่วมกับ Camfrog Client ตัวจริงบน Windows และเว็บไซต์ `camfrog.com` จริง** ควรเปลี่ยนจากระบบที่ทำเพียง Snapshot/Simulation เป็น **Real Client + Real Website Integration** โดยยังคงแยกสถานะและหลักฐานอย่างชัดเจน

ตรวจสอบแล้ว Camfrog มี Windows Client อย่างเป็นทางการ รองรับ Windows 10/11 พร้อมความสามารถเข้าห้องสนทนา, Private Chat และ User Directory <Cite ref="turn526532search0"/>

## Proposed Architecture

```text
ZChat Dashboard (zchat.zeaz.dev)
            |
      FastAPI Server
            |
       PostgreSQL
            |
   Windows Control Agent
            |
       Provider Layer
         /       \
        /         \
Real Camfrog    camfrog.com
Windows Client  Official Website
        \         /
         \       /
     Verified State
            |
    ZChat Dashboard
```

## สิ่งที่ต้องพัฒนาและทดสอบจริง

| Capability | Real Windows Client | camfrog.com |
|---|---|---|
| Launch / Stop | Process Control | ไม่เกี่ยวข้อง |
| Login Status | ตรวจจาก Client UI | ตรวจจาก Web Session ที่ได้รับอนุญาต |
| Account Profile | UI Observation | Authenticated Profile |
| Friend List | Client UI | Web Profile / Friends |
| Online Status | Verified UI State | Verified Web Evidence |
| Join Room | Official Client | Official Link |
| Chat / IM | Authorized Client Interaction | เฉพาะฟังก์ชันเว็บที่รองรับ |
| Cloud Bot | ถ้ารองรับ | ต้องยืนยัน Interface จริง |
| Premium / Store | Display State | Consent-based Official Checkout |

สถานะ `SUPPORTED` หรือ `VERIFIED` จะกำหนดได้หลังทดสอบกับ Client และ Website จริง ไม่ใช่จากการค้นพบ Selector หรือ Endpoint เท่านั้น

## Prompt เพิ่มเติมสำหรับ Engineering Agent

<WritingBlock id="63184" variant="standard"># ZChat — Real Camfrog Client & Website Integration

Extend the existing ZChat Control Server to integrate with BOTH:

1. The genuine, officially distributed Camfrog Windows desktop client.
2. The real https://www.camfrog.com website.

## Core Requirements

- Use the actual installed Camfrog executable

[https://github.com/cvsz/zchat](https://github.com/cvsz/zchat)

ผมจะตรวจ Repository `cvsz/zchat` ผ่าน GitHub โดยดูโครงสร้างโค้ด, Camfrog Windows Client/Website adapters, tests และ Pull Requests แล้วเทียบกับ Architecture และ Evidence Boundaries ที่ส่งมาก่อนหน้านี้ครับ

## GitHub Audit: [cvsz/zchat](https://github.com/cvsz/zchat)

ตรวจสอบ Repository จริงผ่านบัญชี GitHub `cvsz` แล้ว ณ วันที่ 16 ตุลาคม 2026

<box gap={2}>
  <row align="center" justify="between">
    <text color="secondary">Repository</text>
    **cvsz/zchat**
  </row>
  <row align="center" justify="between">
    <text color="secondary">Default branch</text>
    `main`
  </row>
  <row align="center" justify="between">
    <text color="secondary">Latest observed commit</text>
    [`6ba80e6`](https://github.com/cvsz/zchat/commit/6ba80e69f1e79999e10b35973db586eaaa20c585)
  </row>
  <row align="center" justify="between">
    <text color="secondary">Source files / tree entries</text>
    **332**
  </row>
  <row align="center" justify="between">
    <text color="secondary">Open Pull Requests</text>
    **1 — PR #44**
  </row>
  <row align="center" justify="between">
    <text color="secondary">Production Readiness</text>
    <badge color="warning">ยังไม่ผ่านการยืนยัน</badge>
  </row>
</box>

### ข้อค้นพบสำคัญ

Repository นี้มีทั้ง `control-server`, Windows GUI, Camfrog provider-related modules, `zchat-client`, เอกสาร Reverse Engineering และชุดทดสอบอยู่แล้ว จึงควรพัฒนาต่อยอดจากสถาปัตยกรรมปัจจุบัน ไม่จำเป็นต้องสร้างระบบใหม่ทั้งหมด

ล่าสุด PR #43 ถูก Merge เข้า `main` แล้ว เพื่อแก้การเลือก Window ที่เป็น Process ของโปรแกรมเอง และบังคับให้ปฏิเสธ Process ที่ไม่สามารถตรวจสอบ PID ได้

อย่างไรก็ตาม **PR #44 ยังเปิดอยู่** และเกี่ยวข้องโดยตรงกับปัญหา `room_control_gui.py` ที่เคยพบ:

[PR #44 — Exclude self-PID and fail closed in Room Control](https://github.com/cvsz/zchat/pull/44)

รายละเอียด PR ระบุว่าแก้การเลือก Window ของตัวเอง, ปฏิเสธ PID ที่พิสูจน์ไม่ได้ และป้องกัน `AttributeError` ในกรณี `process_windows` ได้ค่า `None` โดยรายงานว่า 739 root tests และชุดทดสอบอื่นผ่าน แต่ยังต้องต

if decompile Camfrog Video Chat.exe

สามารถทำ **Reverse Engineering / Decompile `Camfrog Video Chat.exe`** เพื่อศึกษาการทำงานของ Windows Client จริง และนำผลไปปรับปรุง [cvsz/zchat](https://github.com/cvsz/zchat) ได้ แต่ต้องแยกให้ออกระหว่างการวิเคราะห์โปรแกรมกับการนำโค้ดหรือ Protocol ภายในไปใช้งาน

## 1. Decompile Camfrog Client ได้แค่ไหน?

ขึ้นอยู่กับว่า `Camfrog Video Chat.exe` ถูกสร้างด้วยเทคโนโลยีใด

| ประเภท Binary | เครื่องมือ | ผลที่ได้ |
|---|---|---|
| Native C/C++ | Ghidra, IDA Free | Disassembly และ Pseudocode |
| .NET Assembly | ILSpy, dnSpyEx | Decompiled C# |
| Electron | Electron ASAR tools | JavaScript/Resources |
| Packed Binary | Detect It Easy, PE analysis | ระบุ Packaging และข้อจำกัด |

สำหรับ Native C++ จะไม่ได้ Source Code ต้นฉบับ 100% แต่สามารถวิเคราะห์โครงสร้างของโปรแกรม, Imports, Strings, Windows APIs และบางส่วนของ Control Flow ได้

## 2. สิ่งที่ควรวิเคราะห์เพื่อปรับปรุง ZChat

เน้นส่วนที่จำเป็นต่อการเชื่อมต่ออย่างปลอดภัย ได้แก่:

- **Process/Window Model:** การจัดการ PID, HWND, Main Window, Room Windows และ Windows Session
- **Official URI Handling:** ตรวจสอบการรับ `camfrog:` URI และการส่งต่อคำสั่ง
- **Account State Observations:** แยก Login, Connection และ Room Membership
- **Client Configuration:** ตำแหน่งไฟล์ Configuration และการตั้งค่าที่ไม่ใช่ Secrets
- **Runtime Events:** ตรวจสอบว่า Launch, Join Room และ IM handoff สำเร็จจริงหรือไม่
- **Version Compatibility:** บันทึก Client Version, Binary Hash และพฤติกรรมที่เปลี่ยนแปลง

ไม่ควรแก้ Binary เพื่อข้าม License, Login, CAPTCHA หรือระบบป้องกันของ Camfrog และไม่ควรนำ Session Keys, Credentials หรือ Private Protocol ไปใช้โดยไม่ได้รับอนุญาต

## 3. ข้อจำกัดด้าน License ที่ตรวจพบ

เงื่อนไขของ Camfrog ระบุข้อห้ามเกี่ยวกับ Reverse Engineering, Decompilation, Disassembly และการดัดแปลงซอฟต์แวร์อย่างชัดเจน <Cite ref="turn283469search4"/>

ดังนั้น ก่อน Decompile Binary จริงเพื่อใช้ในผลิตภัณฑ์ ZChat ควรได้รับอนุญาตจาก Camfrog หรือให้ผู้เชี่ยวชาญกฎหมายตรวจสอบข้อยกเว้นที่อาจใช้ได้ตามกฎหมายที่เกี่ยวข้อง

สำหรับตอนนี้สามารถเริ่มจาก **Non-invasiv

============================================================
FULL BUILD COMPLETE
============================================================

Outputs:
  dist\room-control\room-control.exe
  dist\chat-im-private\chat-im-private.exe
  dist\status-random\status-random.exe
  dist\status-marquee\status-marquee.exe
  dist\im-autoreply\im-autoreply.exe
  dist\web-status\web-status.exe
  dist\music-dj\music-dj.exe
  dist\status-changer\status-changer.exe
  dist\zchat-client\zchat-client.exe
  dist\zchat-client\SHA256SUMS.txt
  camfrog-features-windows.zip
  dist\SHA256SUMS.txt
  dist\BUILD_SOURCE.txt
  line\dist\line-status-changer.exe
  line\dist\line_config.json

Build only: no Git staging, commit, or push is performed.
Without --release, no GitHub release is created either.

PS D:\data\zchat> $proc = Get-CimInstance Win32_Process |
>>     Where-Object {
>>         $_.Name -match 'Camfrog'
>>     }
PS D:\data\zchat>
PS D:\data\zchat> $proc | Select-Object `
>>     ProcessId,
>>     ParentProcessId,
>>     Name,
>>     ExecutablePath,
>>     CommandLine

ProcessId       : 21992
ParentProcessId : 9880
Name            : Camfrog Video Chat.exe
ExecutablePath  : C:\Users\cvsz.ZEAZ\AppData\Local\Programs\Camfrog Video Chat\Camfrog Video Chat.exe
CommandLine     : "C:\Users\cvsz.ZEAZ\AppData\Local\Programs\Camfrog Video Chat\Camfrog Video Chat.ex
                  e"

ProcessId       : 15788
ParentProcessId : 21992
Name            : camfrog_cef.exe
ExecutablePath  : C:\Users\cvsz.ZEAZ\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe
CommandLine     : "C:\Users\cvsz.ZEAZ\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe" --ty
                  pe=gpu-process --field-trial-handle=2512,10311354875437920321,8650847908737642596,1
                  31072 --disable-features=CalculateNativeWinOcclusion --no-sandbox --log-file="C:\Us
                  ers\cvsz.ZEAZ\AppData\Local\Programs\Camfrog Video Chat\debug.log" --log-severity=d
                  isable --lang=en-U

## ZChat + Real Camfrog Client — Runtime Analysis

จาก PowerShell Output ที่ส่งมา ยืนยันได้ว่า **Camfrog Video Chat ตัวจริงกำลังทำงานบน Windows** และมี Chromium Embedded Framework (CEF) subprocesses อยู่ภายใต้ Main Process

ส่วน ZChat Build รายงานว่าสร้าง Executable สำเร็จครบตามรายการ แต่ยังไม่ได้ยืนยันว่าแต่ละโปรแกรมทำงานแบบ End-to-End ได้จริง

### 1. Runtime Findings

<box gap={2}>
  <row align="center" justify="between">
    <text color="secondary">ZChat Build</text>
    <badge color="success">Reported complete</badge>
  </row>
  <row align="center" justify="between">
    <text color="secondary">Camfrog Main Process</text>
    **PID 21992**
  </row>
  <row align="center" justify="between">
    <text color="secondary">CEF Child Processes</text>
    **5 processes**
  </row>
  <row align="center" justify="between">
    <text color="secondary">Camfrog Main EXE</text>
    **61,713,584 bytes**
  </row>
  <row align="center" justify="between">
    <text color="secondary">Windows Runtime State</text>
    <badge color="success">Process observed</badge>
  </row>
</box>

โครงสร้าง Process ที่พบ:

```text
explorer.exe (PID 9880)
└── Camfrog Video Chat.exe (PID 21992)
    ├── camfrog_cef.exe (PID 15788) GPU
    ├── camfrog_cef.exe (PID 17384) Network
    ├── camfrog_cef.exe (PID 21632) Storage
    ├── camfrog_cef.exe (PID 3944) Renderer
    └── camfrog_cef.exe (PID 18440) Renderer
```

สิ่งสำคัญคือ **อย่านับ `camfrog_cef.exe` เป็น Camfrog Account Instance อีก 5 ตัว** เพราะทั้งหมดเป็น Child Processes ของ Main Client เดียวกัน

### 2. Security Findings

จาก Command Line พบ:

- `--no-sandbox` ใน CEF subprocesses หลายตัว
- `--service-sandbox-type=none` ใน Network Service
- `--no-v8-untrusted-code-mitigations` ใน Renderer
- `--autoplay-policy=no-user-gesture-required`

ข้อเท็จจริงเหล่านี้ควรถูกบันทึกไว้ใน Security Audit แต่ยังสรุปว่าเป็นช่องโหว่ที่ใช้โจมตีได้จริงไม่ได้โดยไม่มีการตรวจ Client Version, CEF Version และการตั้งค่าอื่นเพิ่มเติม

ไม่แนะนำให้แก้ flags ของ Camfrog โดยตรง เพร

PS D:\data\zchat> $ErrorActionPreference = "Stop"
PS D:\data\zchat>
PS D:\data\zchat> $reportDir = "D:\data\zchat\reports\camfrog-runtime"
PS D:\data\zchat> New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
PS D:\data\zchat>
PS D:\data\zchat> $main = Get-CimInstance Win32_Process -Filter "Name='Camfrog Video Chat.exe'"
PS D:\data\zchat>
PS D:\data\zchat> $results = foreach ($p in $main) {
>>     if (-not $p.ExecutablePath) { continue }
>>
>>     $file = Get-Item -LiteralPath $p.ExecutablePath
>>     $sig = Get-AuthenticodeSignature -LiteralPath $file.FullName
>>     $hash = Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256
>>     $runtime = Get-Process -Id $p.ProcessId -ErrorAction Stop
>>
>>     [PSCustomObject]@{
>>         PID              = $p.ProcessId
>>         ParentPID        = $p.ParentProcessId
>>         Path             = $file.FullName
>>         FileVersion      = $file.VersionInfo.FileVersion
>>         ProductVersion   = $file.VersionInfo.ProductVersion
>>         Company          = $file.VersionInfo.CompanyName
>>         SignatureStatus  = $sig.Status.ToString()
>>         Signer           = $sig.SignerCertificate.Subject
>>         SHA256           = $hash.Hash
>>         MainWindowHandle = $runtime.MainWindowHandle.ToInt64()
>>         MainWindowTitle  = $runtime.MainWindowTitle
>>         StartTime        = $runtime.StartTime.ToString("o")
>>     }
>> }
PS D:\data\zchat>
PS D:\data\zchat> $results | Format-List

PID              : 21992
ParentPID        : 9880
Path             : C:\Users\cvsz.ZEAZ\AppData\Local\Programs\Camfrog Video Chat\Camfrog Video Chat.ex
                   e
FileVersion      : 8.5.0.51219
ProductVersion   : 8.5.0.51219
Company          : Camfrog LLC
SignatureStatus  : Valid
Signer           : CN=Camfrog LLC, O=Camfrog LLC, L=Las Vegas, S=Nevada, C=US, SERIALNUMBER=10033625,
                    OID.2.5.4.15=Private Organization, OID.1.3.6.1.4.1.311.60.2.1.2=Delaware, OID.1.3
                   .6.1.4

## Camfrog 8.5.0 — Verified Runtime Identity

ผลตรวจครั้งนี้ยืนยันตัวตนของ Camfrog Windows Client ได้ชัดเจนขึ้น โดยไม่ต้อง Decompile หรือแก้ไข Binary

<box gap={2}>
  <row align="center" justify="between">
    **Digital Signature**
    <badge color="success">Valid</badge>
  </row>
  <row align="center" justify="between">
    **Process Identity**
    <badge color="success">Verified at capture</badge>
  </row>
  <row align="center" justify="between">
    **Login / Room Membership**
    <badge color="warning">Not verified</badge>
  </row>
</box>

| Property | Observed value |
|---|---|
| Application | Camfrog Video Chat |
| Version | `8.5.0.51219` |
| Publisher | Camfrog LLC |
| Signature | `Valid` |
| PID | `21992` |
| Parent PID | `9880` |
| Main Window Handle | `5177812` |
| Window Title | `zdevz (ไม่อยู่)` |
| Start Time | `2026-10-16 21:21:56 +07:00` |
| SHA256 | `0B744602C004536DCF81E9965E8CB17358EB276B3876A1E70C50F72777C27E06` |

การตรวจ Authenticode ยืนยันว่า Windows ประเมินลายเซ็นว่า Valid และ Certificate ระบุ Camfrog LLC แต่ยังไม่ได้พิสูจน์พฤติกรรมทั้งหมดของโปรแกรม

### ข้อค้นพบสำคัญสำหรับ ZChat

**`MainWindowTitle = zdevz (ไม่อยู่)`** เป็นข้อมูลที่ช่วยแก้ Window Discovery ได้โดยตรง

ข้อความ `(ไม่อยู่)` อาจแสดงสถานะ Away ของบัญชี แต่ยังไม่ควรนำไปยืนยัน `AccountPresence = AWAY` จนกว่าจะทดสอบเทียบกับสถานะจริง

การเลือก Window ควรใช้ PID และ Process Identity เป็นหลัก ไม่ใช่ชื่อหน้าต่างเพียงอย่างเดียว

## ขั้นตอนถัดไป: ทดสอบ Window Selection จริง

รันคำสั่งต่อไปนี้ใน PowerShell เพื่อดูว่าหน้าต่างใดเป็นของ Camfrog Main Process และทดสอบว่า ZChat ควรเลือกหน้าต่างใด

```powershell
cd D:\data\zchat

@'
import psutil
from pywinauto import Desktop

TARGET_EXE = "camfrog video chat.exe"

processes = []

for proc in psutil.process_iter(["pid", "name", "exe", "create_time"]):
    try:
        if (proc.info["name"] or "").casefold() == TARGET_EXE:
            processes.append(proc.info)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue

windows = Desk

PS D:\data\zchat> $results | ConvertTo-Json -Depth 5 |
>>     Set-Content "$reportDir\main-process.json" -Encoding utf8
PS D:\data\zchat> cd D:\data\zchat
PS D:\data\zchat>
PS D:\data\zchat> @'
>> import psutil
>> from pywinauto import Desktop
>>
>> TARGET_EXE = "camfrog video chat.exe"
>>
>> processes = []
>>
>> for proc in psutil.process_iter(["pid", "name", "exe", "create_time"]):
>>     try:
>>         if (proc.info["name"] or "").casefold() == TARGET_EXE:
>>             processes.append(proc.info)
>>     except (psutil.NoSuchProcess, psutil.AccessDenied):
>>         continue
>>
>> windows = Desktop(backend="uia").windows(visible_only=True)
>>
>> for proc in processes:
>>     pid = proc["pid"]
>>     print(f"\nCamfrog PID={pid}")
>>     print(f"Executable={proc['exe']}")
>>     print(f"Created={proc['create_time']}")
>>
>>     for window in windows:
>>         try:
>>             if window.process_id() == pid:
>>                 print({
>>                     "handle": window.handle,
>>                     "title": window.window_text(),
>>                     "class": window.class_name(),
>>                     "visible": window.is_visible(),
>>                 })
>>         except Exception:
>>             continue
>> '@ | python -
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "C:\Program Files\Python314\Lib\site-packages\psutil\__init__.py", line 110, in <module>
    from . import _pswindows as _psplatform
  File "C:\Program Files\Python314\Lib\site-packages\psutil\_pswindows.py", line 35, in <module>
    from ._psutil_windows import ABOVE_NORMAL_PRIORITY_CLASS
ModuleNotFoundError: No module named 'psutil._psutil_windows'
PS D:\data\zchat>

## Root Cause: `psutil._psutil_windows` Missing

ปัญหานี้เกิดจาก Python 3.14 ที่กำลังเรียกใช้ `psutil` แต่ไม่สามารถโหลด Native Extension สำหรับ Windows ได้

```text
Python: C:\Program Files\Python314\
Error: ModuleNotFoundError: No module named 'psutil._psutil_windows'
```

สาเหตุที่เป็นไปได้คือ `psutil` ติดตั้งไม่สมบูรณ์, Binary Wheel ไม่ตรงกับ Python Runtime หรือมีไฟล์ Extension ขาดหาย

**ไม่ใช่ปัญหาของ Camfrog หรือ Windows Process โดยตรง** เพราะโปรแกรมล้มเหลวตั้งแต่ขั้นตอน `import psutil`

### 1. แก้ psutil บน Python 3.14

รันใน PowerShell:

```powershell
cd D:\data\zchat

python -m pip --version
python -m pip show psutil

python -m pip uninstall -y psutil
python -m pip install --no-cache-dir --only-binary=:all: psutil
```

จากนั้นตรวจสอบ:

```powershell
python -c "import psutil; print('psutil:', psutil.__version__)"
python -c "from pywinauto import Desktop; print('pywinauto: OK')"
```

หากทั้งสองคำสั่งทำงานได้ ให้ลองรัน Window Discovery อีกครั้ง

PyPI ยืนยันว่า `psutil` มี Windows Binary Wheel ที่รองรับ Python 3.14 แล้ว จึงไม่จำเป็นต้อง Downgrade Python ทันที <Cite ref="turn610962search0"/>

### 2. ทางเลือกที่เร็วกว่า — ไม่ใช้ psutil

ถ้าต้องการตรวจ Camfrog Window ตอนนี้เลย สามารถใช้ `pywinauto` และ Windows Process Information ที่ตรวจพบก่อนหน้าได้โดยตรง

```powershell
@'
from pywinauto import Desktop

CAMFROG_PID = 21992

windows = Desktop(backend="uia").windows(
    process=CAMFROG_PID,
    visible_only=True
)

print(f"Camfrog PID: {CAMFROG_PID}")
print(f"Windows found: {len(windows)}")

for window in windows:
    print({
        "handle": window.handle,
        "title": window.window_text(),
        "class": window.class_name(),
        "visible": window.is_visible(),
    })
'@ | python -
```

หมายเหตุ: PID `21992` เป็นค่าจาก Snapshot ก่อนหน้า หากมีการ Restart Camfrog ต้องตรวจ PID ใหม่ก่อนใช้งาน

หาก `pywinauto` เอง Import ไม่ผ่าน ให้ใช้ PowerShell ตรวจ Windows Process โดยไม่ต้องพึ่ง Python:

```powershell
Get-Process -Name "Camfrog Video Chat" |
    Select-Ob

PS D:\data\zchat> cd D:\data\zchat
PS D:\data\zchat>
PS D:\data\zchat> python -m pip --version
pip 26.2.1 from C:\Program Files\Python314\Lib\site-packages\pip (python 3.14)
PS D:\data\zchat> python -m pip show psutil
Name: psutil
Version: 6.1.1
Summary: Cross-platform lib for process and system monitoring in Python.
Home-page: https://github.com/giampaolo/psutil
Author: Giampaolo Rodola
Author-email: g.rodola@gmail.com
License: BSD-3-Clause
Location: C:\Program Files\Python314\Lib\site-packages
Requires:
Required-by:
PS D:\data\zchat>
PS D:\data\zchat> python -m pip uninstall -y psutil
Found existing installation: psutil 6.1.1
Uninstalling psutil-6.1.1:
ERROR: Exception:
Traceback (most recent call last):
  File "C:\Program Files\Python314\Lib\shutil.py", line 922, in move
    os.rename(src, real_dst)
    ~~~~~~~~~^^^^^^^^^^^^^^^
PermissionError: [WinError 5] Access is denied: 'c:\\program files\\python314\\lib\\site-packages\\psutil-6.1.1.dist-info\\' -> 'C:\\Users\\cvsz.ZEAZ\\AppData\\Local\\Temp\\pip-uninstall-omntzacq'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\cli\base_command.py", line 109, in _run_wrapper
    status = _inner_run()
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\cli\base_command.py", line 102, in _inner_run
    return self.run(options, args)
           ~~~~~~~~^^^^^^^^^^^^^^^
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\commands\uninstall.py", line 105, in run
    uninstall_pathset = req.uninstall(
        auto_confirm=options.yes,
        verbose=self.verbosity > 0,
    )
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\req\req_install.py", line 680, in uninstall
    uninstalled_pathset.remove(auto_confirm, verbose)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\req\req_uninstall.py",

## Root Cause ยืนยันแล้ว: Global Python ไม่มีสิทธิ์แก้ไข Package

จาก Log ล่าสุดพบปัญหา 2 ส่วน:

1. **`psutil 6.1.1` ติดตั้งอยู่ใน `C:\Program Files\Python314`** ซึ่งบัญชี Windows ปัจจุบันไม่มีสิทธิ์แก้ไข จึงเกิด `WinError 5: Access is denied`
2. `pip install` เห็น Metadata ของ `psutil 6.1.1` อยู่แล้ว จึงแสดง `Requirement already satisfied` แม้ Native Extension `psutil._psutil_windows` จะไม่สามารถ Import ได้

**วิธีแก้ที่แนะนำ:** ใช้ Virtual Environment แยกสำหรับ ZChat โดยไม่แก้ไข Global Python และไม่ต้องเปิด PowerShell แบบ Administrator

## 1. ติดตั้ง Python Runtime ใหม่แบบ Isolated

คัดลอกคำสั่งทั้งหมดนี้ไปรันใน PowerShell:

```powershell
cd D:\data\zchat

# Create isolated Python environment without global packages
py -3.14 -m venv .venv-runtime

$py = "D:\data\zchat\.venv-runtime\Scripts\python.exe"

# Confirm isolation
& $py -c "import sys; print(sys.executable); print(sys.prefix)"

# Upgrade environment tools
& $py -m pip install --upgrade pip setuptools wheel

# Install Windows runtime dependencies
& $py -m pip install --no-cache-dir --only-binary=:all: `
    --upgrade psutil pywinauto pywin32

# Verify actual native module loading
& $py -c "import psutil; import psutil._psutil_windows; from pywinauto import Desktop; print('PASS: Windows runtime dependencies loaded'); print('psutil:', psutil.__version__)"
```

**Expected Result:**

```text
PASS: Windows runtime dependencies loaded
psutil: <installed version>
```

หากคำสั่งสุดท้ายผ่าน แสดงว่าแก้ปัญหาการ Import Native Extension สำเร็จใน Environment ใหม่แล้ว

## 2. ตรวจ Camfrog Windows Client จริง

รันต่อด้วย Python Environment ใหม่:

```powershell
@'
import psutil
from pywinauto import Desktop
from datetime import datetime

TARGET = "camfrog video chat.exe"

for proc in psutil.process_iter(["pid", "name", "exe", "create_time"]):
    try:
        if (proc.info["name"] or "").casefold() != TARGET:
            continue

        pid = proc.info["pid"]

        print("=" * 60)
        print("PID:", pid)
        prin

PS D:\data\zchat> python -m pip install --no-cache-dir --only-binary=:all: psutil
Defaulting to user installation because normal site-packages is not writeable
Requirement already satisfied: psutil in C:\Program Files\Python314\Lib\site-packages (6.1.1)
PS D:\data\zchat> python -c "import psutil; print('psutil:', psutil.__version__)"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import psutil; print('psutil:', psutil.__version__)
    ^^^^^^^^^^^^^
  File "C:\Program Files\Python314\Lib\site-packages\psutil\__init__.py", line 110, in <module>
    from . import _pswindows as _psplatform
  File "C:\Program Files\Python314\Lib\site-packages\psutil\_pswindows.py", line 35, in <module>
    from ._psutil_windows import ABOVE_NORMAL_PRIORITY_CLASS
ModuleNotFoundError: No module named 'psutil._psutil_windows'
PS D:\data\zchat> python -c "from pywinauto import Desktop; print('pywinauto: OK')"
pywinauto: OK
PS D:\data\zchat> @'
>> from pywinauto import Desktop
>>
>> CAMFROG_PID = 21992
>>
>> windows = Desktop(backend="uia").windows(
>>     process=CAMFROG_PID,
>>     visible_only=True
>> )
>>
>> print(f"Camfrog PID: {CAMFROG_PID}")
>> print(f"Windows found: {len(windows)}")
>>
>> for window in windows:
>>     print({
>>         "handle": window.handle,
>>         "title": window.window_text(),
>>         "class": window.class_name(),
>>         "visible": window.is_visible(),
>>     })
>> '@ | python -
Camfrog PID: 21992
Windows found: 3
{'handle': 5177812, 'title': 'zdevz (ไม่อยู่)', 'class': '#32770', 'visible': True}
{'handle': 33360162, 'title': 'ZeaZDev: ห้องสนทนา', 'class': '#32770', 'visible': True}
{'handle': 3149540, 'title': 'Camfrog Video Chat', 'class': '#32770', 'visible': True}
PS D:\data\zchat> Get-Process -Name "Camfrog Video Chat" |
>>     Select-Object Id, StartTime, MainWindowHandle, MainWindowTitle, Path |
>>     Format-List

Id               : 21992
StartTime        : 16/10/2569 21:21:56
MainWindowHandle : 5177812
MainWindow

## ZChat Windows Runtime — ตรวจสอบผ่านแล้ว

จากผลการทดสอบล่าสุด **แก้ปัญหา `psutil._psutil_windows` สำเร็จแล้ว** โดยใช้ Python Virtual Environment แยกจาก Global Python 3.14

<box gap={2}>
  <row align="center" justify="between">
    **Isolated Python Runtime**
    <badge color="success">PASS</badge>
  </row>
  <row align="center" justify="between">
    **psutil 7.2.2**
    <badge color="success">PASS</badge>
  </row>
  <row align="center" justify="between">
    **pywinauto 0.6.9**
    <badge color="success">PASS</badge>
  </row>
  <row align="center" justify="between">
    **Real Camfrog Window Discovery**
    <badge color="success">PASS</badge>
  </row>
  <row align="center" justify="between">
    **ZChat End-to-End Integration**
    <badge color="warning">Not verified</badge>
  </row>
</box>

## 1. พบ Camfrog Windows 3 หน้าต่างใน Process เดียว

| HWND | Window Title | PID |
|---|---|---|
| `5177812` | `zdevz (ไม่อยู่)` | 21992 |
| `33360162` | `ZeaZDev: ห้องสนทนา` | 21992 |
| `3149540` | `Camfrog Video Chat` | 21992 |

ทั้งสามหน้าต่างอยู่ภายใต้ Camfrog Main Process เดียวกัน

**ข้อสรุปสำคัญ:** ZChat ต้องรองรับหลายหน้าต่างภายใน Process เดียว ไม่ใช่สรุปว่าเป็นหลาย Camfrog Instances

นี่สอดคล้องกับปัญหาที่เคยพบใน `room_control_gui.py` ซึ่งใช้ `window_title_regex` ในการค้นหา Window

## 2. Architecture ที่ควรนำไปใช้

```text
Real Camfrog Video Chat.exe
PID 21992
│
├── Account/Buddy Window
│   HWND 5177812
│   Title: zdevz (ไม่อยู่)
│
├── Room Window
│   HWND 33360162
│   Title: ZeaZDev: ห้องสนทนา
│
└── Camfrog Window
    HWND 3149540
    Title: Camfrog Video Chat
         │
         ▼
ZChat Windows Runtime Adapter
         │
         ├── Process Identity Verification
         ├── Window Discovery
         ├── Window Role Classification
         ├── Safe Window Selection
         └── State Observation
         │
         ▼
ZChat Control Server
```

การจัดประเภทหน้าต่างด้านบนเป็นการจัดกลุ่มเบื้องต้นจาก Title เท่านั้น โดยเฉพาะหน้าต่าง `Camfrog Video Chat` ยังต้องตรวจ UI El

[ข้อความที่วาง (1)(20261016-152615).txt]

## ZChat — Real Camfrog UI Inspection Results

วิเคราะห์ Runtime Log ล่าสุดแล้ว พบหลักฐานที่สำคัญสำหรับพัฒนา `cvsz/zchat` ให้ทำงานร่วมกับ **Camfrog Video Chat 8.5.0.51219** ผ่าน Windows UI Automation โดยไม่ต้อง Decompile Executable

### 1. ผลตรวจสอบ

<box gap={2}>
  <row align="center" justify="between">
    **Python Runtime / psutil**
    <badge color="success">PASS</badge>
  </row>
  <row align="center" justify="between">
    **Real Camfrog Process**
    <badge color="success">Verified</badge>
  </row>
  <row align="center" justify="between">
    **Windows UI Elements**
    <badge color="success">Discovered</badge>
  </row>
  <row align="center" justify="between">
    **Room Membership**
    <badge color="warning">Unverified</badge>
  </row>
</box>

ตรวจพบ Camfrog Main Process `21992` ซึ่งมี 3 หน้าต่างภายใต้ Process เดียวกัน

| HWND | Window role (เบื้องต้น) | Evidence |
|---|---|---|
| `5177812` | Account / IM history | `wb-log-im-data.inside` |
| `33360162` | Room Chat | `wb-log-room-data.inside` |
| `3149540` | Main Client / Directory | `CTreeViewTS`, `CComboBoxTS` |

### 2. ข้อค้นพบสำคัญจาก UI Automation

**Account / IM Window**

พบ `Internet Explorer_Server` ที่แสดง `camfrog://wb-log-im-data.inside/` และมี Text Elements ของประวัติ IM อยู่ภายใน ยืนยันได้ว่า UI Automation สามารถมองเห็นองค์ประกอบของหน้า IM ได้ แต่ยังไม่ได้พิสูจน์ว่าส่งข้อความผ่าน UI สำเร็จ

**Room Window**

พบ `VideoViewport` และ `camfrog://wb-log-room-data.inside/` ซึ่งเป็นหลักฐานที่ชัดเจนว่าหน้าต่างดังกล่าวมี Room UI และแสดงประวัติสนทนา

อย่างไรก็ตาม Log มีข้อความย้อนหลังเกี่ยวกับการถูกนำออกจากห้องเนื่องจากไม่มีการใช้งาน จึงไม่สามารถใช้ข้อความในประวัติมายืนยันว่าปัจจุบันยังอยู่ในห้องได้

**Main Client Window**

พบ `CTreeViewTS`, `CComboBoxTS`, `Edit` รวมถึงปุ่มที่มีชื่อ `ออนไลน์` แสดงว่า UI Automation เข้าถึงโครงสร้างบางส่วนของ Client ได้

ชื่อ `ออนไลน์` เป็นชื่อ Control ไม่ใช่หลักฐานโดยตรงว่าบัญชีออนไลน์อยู่ในขณะนั้น

<text color="secondary" size="xs">หลักฐาน: Windows UI Inspection ที่ส่งมา <

เมื่อแก้ไขแล้ว Status Changer source code เป้นไง บ้าง เพราะตอนนี้ ไม่สามารถทำงาน เบื้องหลัง โดยไม่ต้องเปิดหน้าต่าง camfrog ได้ ซึ่งทำให้ รบกวนการใฃ้งาน mouse+keyboard

ผมจะตรวจ Source Code ของ Status Changer ใน `cvsz/zchat` ว่าปัจจุบันใช้วิธีควบคุม Camfrog แบบไหน และส่วนใดที่ทำให้ต้องเปิดหน้าต่างหรือแย่ง Mouse/Keyboard แล้วสรุปแนวทางแก้ที่ทำได้จริงโดยไม่รบกวน Desktop ครับ

## ZChat Status Changer — Source Code Audit

ผมตรวจ Source Code ล่าสุดจาก [`cvsz/zchat`](https://github.com/cvsz/zchat) แล้ว พบว่า **Status Changer มีโค้ดสำหรับทำงานเบื้องหลังอยู่แล้ว แต่ยังมีจุดที่ทำให้แย่ง Focus, ใช้ Keyboard/Mouse และไม่สามารถยืนยันได้ว่าเปลี่ยน Status สำเร็จขณะ Camfrog ถูกซ่อนอยู่**

ปัญหาหลักไม่ใช่ Python หรือ `psutil` อีกต่อไป แต่เป็นวิธีการส่ง Status ไปยัง Camfrog Client

### ผลตรวจสอบ

| Component | สถานะ | ปัญหาที่พบ |
|---|---|---|
| Windows Client Discovery | มี Implementation | ยังพึ่งพา Window Title |
| Background Window Discovery | รองรับ | ค้นหา Hidden/Minimized Windows ได้ แต่ยังไม่รับประกันว่าควบคุมได้ |
| Status Edit | มี Implementation | ใช้ `WM_SETTEXT` และตรวจ Read-back |
| Background Submit | Experimental | ใช้ `PostMessage` ส่ง Enter |
| Foreground Fallback | ยังมี | เรียก `set_focus()` และ `type_keys()` |
| Mouse Interaction | ยังมี | บางเส้นทางเรียก `click_input()` |
| Background Success Verification | ไม่ครบ | ตรวจ Text แต่ยังไม่ยืนยัน Server-side Status |
| Silent Operation | มีปัญหา | มีโค้ดแก้ Windows Sound Registry ชั่วคราว |

### จุดที่ต้องแก้ก่อน

**P0 — กำจัด Foreground Input ออกจาก Background Mode**

ไฟล์ `status_changer_gui.py` มีการเรียก:

```python
win.set_focus()
ctrl.set_focus()
ctrl.type_keys("{ENTER}")
btn.click_input()
```

คำสั่งเหล่านี้สามารถรบกวนหน้าต่างที่กำลังใช้งานอยู่ได้

แม้โค้ดจะมี `background_submit` แล้ว แต่ยังมีบางเส้นทางที่นำ Camfrog กลับมาเป็น Foreground

**P0 — ไม่ควรแก้ System Sound Registry**

ฟังก์ชัน `_background_enter()` มีการเปลี่ยน Registry ภายใต้:

```text
HKEY_CURRENT_USER\AppEvents\Schemes\Apps\.Default
```

เพื่อปิดเสียงชั่วคราว แล้วพยายาม Restore ภายหลัง วิธีนี้ส่งผลต่อการตั้งค่าเสียงของ Windows ในระดับผู้ใช้ และอาจเกิด Race Condition ระหว่างหลาย Worker ได้

ควรถอด Logic นี้ออก

merged 2 prompt to single

รวม 2 Prompts ให้เป็น **Single Ultimate Master Prompt** สำหรับ Codex โดยครอบคลุมทั้ง **Real Camfrog 8.5 Windows Client Integration** และ **True Background Status Changer** ที่ไม่รบกวน Mouse, Keyboard, Clipboard, Window Focus หรือเสียงของ Windows

Prompt นี้ออกแบบสำหรับ Repository [`cvsz/zchat`](https://github.com/cvsz/zchat) โดยให้ Codex ตรวจสอบ Source Code เดิม แก้ไข Root Cause, Refactor, Implement, Test, Build และส่งมอบหลักฐานจริง ภายใต้ GitHub Governance

<WritingBlock id="84721" variant="document"># ZChat — Ultimate Master Prompt
## Real Camfrog Windows Integration + True Background Status Automation

**Repository:** `https://github.com/cvsz/zchat`  
**Target:** Camfrog Video Chat `8.5.0.51219`  
**Platform:** Windows 11 / Python 3.14  
**Execution Model:** Autonomous Production Engineering  
**Engineering Standard:** Evidence-Driven, Security-First, Production-Oriented

---

# 1. ROLE AND MISSION

Act as an autonomous multidisciplinary engineering team consisting of:

- Principal Software Architect
- Senior Windows Runtime Engineer
- Senior Python Engineer
- Windows UI Automation Engineer
- Security Auditor
- Reverse Engineering Researcher
- QA Automation Engineer
- DevOps and Release Engineer

Your mission is to investigate, repair, refactor, integrate, test, and package the existing ZChat system so that it can reliably interact with the genuine Camfrog Windows client.

The primary requirement is **true background status automation without interfering with the user's active desktop session**.

Do not replace working functionality unnecessarily.

Do not claim success without actual verification evidence.

# 2. MANDATORY OPERATING RULES

1. Read `AGENTS.md`, `CLAUDE.md`, architecture documents, repository governance, and existing implementation contracts before making changes.
2. Investigate the entire relevant execution path rather than modifying isolated functions without understanding their callers.
3. Preserve existing working features and configuration comp

▾ Thought for 9s
  All test suites are passing, including unit, automated, command processing, and live acceptance
  tests. Confident the core functionality and existing behavior are intact. The next step involves a
  final review of all the changed files to ensure that everything adheres to the requirements.
  ### Real Camfrog 8.5 Windows UI Runtime Integration Summary
  We have implemented an evidence-driven, fail-closed Windows UI runtime integration for genuine
  Camfrog Video Chat 8.5 (8.5.0.51219) on Windows 11 under Python 3.14.8 (psutil 7.2.2, pywinauto
  0.6.9).
  ──────
  ### Implementation Highlights
  1. Process Discovery (WindowsCamfrogProcessDiscovery):
      • Matches genuine executable Camfrog Video Chat.exe (PE FileVersion 8.5.0.51219).
      • Verifies Authenticode digital signature using WinVerifyTrust (wintrust.dll).
      • Validates code-signing publisher subject as Camfrog LLC via native CryptoAPI (crypt32.dll
      CryptQueryObject / CertGetNameStringW).
      • Captures immutable identity: (pid, create_time, exe_path, publisher, signature_valid,
      version, is_agent_launched).
      • Strictly excludes auxiliary CEF subprocesses (camfrog_cef.exe or --type=renderer|gpu-
      process|utility) and ZChat's own processes and Tk GUI windows.
      • Fails closed if multiple verified processes exist without an explicit target PID.
  2. Structural UI Classifier (WindowsCamfrogWindowClassifier):
      • Main Client / Directory: Identified by CTreeViewTS (buddy list / contact directory) and
      CComboBoxTS (status selector, id 1436) with native Edit controls.
      • Room Window: Identified by VideoViewport (cls VideoViewport, id 11425) and embedded
      Internet Explorer_Server hosting camfrog://wb-log-room-data.inside/.
      • IM Window: Identified by embedded Internet Explorer_Server hosting camfrog://wb-log-im-
      data.inside/ and native edit input (CEditTS/Edit), without VideoViewport.
      • Ambiguous / Unknown: Windows with conflict

## ZChat — Implementation Review & Production Readiness

จากรายงาน Codex ล่าสุด **Real Camfrog 8.5 Windows Runtime Integration มีความคืบหน้าชัดเจน** โดยรายงานว่าผ่าน Unit Tests, Regression Tests และ Live Windows Acceptance Tests

อย่างไรก็ตาม มีข้อสำคัญที่ต้องแยกให้ชัดเจน:

**สิ่งที่รายงานนี้ยืนยันคือ Read-only Runtime Integration ไม่ใช่การแก้ปัญหา Status Changer ให้ทำงานเบื้องหลังโดยไม่แย่ง Mouse/Keyboard สำเร็จแล้ว**

<box gap={2}>
  <row align="center" justify="between">
    **Runtime Discovery & Classification**
    <badge color="success">Reported PASS</badge>
  </row>
  <row align="center" justify="between">
    **Unit Tests**
    **14 passed**
  </row>
  <row align="center" justify="between">
    **Regression Tests**
    **63 passed**
  </row>
  <row align="center" justify="between">
    **Live Windows Tests**
    **5 passed**
  </row>
  <row align="center" justify="between">
    **True Background Status Changer**
    <badge color="warning">Not Verified</badge>
  </row>
</box>

### ช่องว่างจาก Master Prompt ที่ยังไม่ได้ปิด

| Requirement | หลักฐานจากรายงาน |
|---|---|
| Verified Process Discovery | มีรายงานว่าผ่าน |
| Window Role Classification | มีรายงานว่าผ่าน |
| Read-only Attachment | มีรายงานว่าผ่าน |
| Prevent Unowned Process Termination | มีรายงานว่าผ่าน |
| Status update ขณะ VS Code มี Focus | ไม่ปรากฏ |
| Status update ขณะ Camfrog Minimized | ไม่ปรากฏ |
| Status update ขณะ Camfrog Hidden to Tray | ไม่ปรากฏ |
| No keyboard/mouse interference | ไม่ปรากฏ |
| No Windows sound mutation | ไม่ปรากฏ |
| Verified Status Applied | ไม่ปรากฏ |

ดังนั้น `Blockers: None` ในรายงาน Codex ควรตีความว่าไม่มี Blocker สำหรับ **Read-only Runtime Scope** เท่านั้น ไม่ใช่ทุก Requirement ของ ZChat

## ผลตรวจสอบ GitHub เพิ่มเติม

ผมตรวจ `cvsz/zchat` ผ่าน GitHub อีกครั้ง พบว่า:

- `main` ที่เครื่องมือเข้าถึงยังชี้ไปที่ Commit `6ba80e6`
- ยังไม่พบไฟล์ `camfrog_windows_runtime.py` บน `main`
- จึงยังยืนยันไม่ได้ว่า Implementation ที่ Codex รายงานถูก Commit หรือ Push แล้ว

เป็นไปได้

กำลังเทสอยู่

รับทราบครับ ตอนนี้อยู่ระหว่าง **Real Windows Acceptance Testing** ของ ZChat + Camfrog 8.5

ระหว่างทดสอบ ให้เน้นตรวจ 5 จุดสำคัญ:

1. **Background Execution:** Camfrog ไม่แย่ง Focus จาก VS Code หรือ Browser
2. **Mouse & Keyboard:** ใช้งานได้ปกติระหว่าง Status Changer ทำงาน
3. **Minimized / Hidden:** เปลี่ยน Status ได้จริงขณะ Camfrog ถูกย่อหรือซ่อน
4. **Silent Operation:** ไม่มีเสียงแจ้งเตือนที่ไม่จำเป็น และไม่แก้ Windows Sound Settings
5. **Status Verification:** ข้อความสถานะเปลี่ยนจริง ไม่ใช่แค่เขียนลง Edit Control สำเร็จ

หากพบปัญหา ให้บันทึกขั้นตอนที่ทำให้เกิดปัญหา, Expected/Actual Result และ Logs โดยไม่เปิดเผยข้อมูลส่วนตัว

**สถานะปัจจุบัน:** `TESTING_IN_PROGRESS` — ยังไม่ประกาศ Production Ready จนกว่าผลทดสอบจริงจะผ่าน Acceptance Criteria ครบถ้วน

ตอนนี้ ใน prompt เปิด โปรแกรม zchat ขึ้นมา แล้วจะ อ่าน camfrog.exe อัตดนมัติ หรือ ต้องกดเอง

ตาม **Master Prompt ล่าสุด** ที่ให้ Codex ทำงานนั้น เป้าหมายคือ **เปิด ZChat แล้วตรวจหา Camfrog Video Chat.exe ที่กำลังทำงานอยู่โดยอัตโนมัติ** ไม่จำเป็นต้องกดปุ่ม Discover เองทุกครั้ง

แต่ต้องแยกสถานะระหว่างสิ่งที่ Prompt สั่งไว้กับสิ่งที่ Implement เสร็จจริง

| ขั้นตอน | พฤติกรรมที่ต้องการ | สถานะ |
|---|---|---|
| เปิด ZChat | เริ่มตรวจหา Camfrog Process | ต้องยืนยันว่าเชื่อมกับ Startup แล้ว |
| Camfrog เปิดอยู่ | ตรวจ EXE, Signature, PID และ Windows | Codex รายงานว่า Implement แล้ว |
| Camfrog ยังไม่เปิด | แสดง `CLIENT_NOT_RUNNING` | ต้องทดสอบ |
| Camfrog เปิดภายหลัง | ตรวจพบอัตโนมัติผ่าน Background Discovery | ยังไม่ยืนยัน |
| พบหลาย Camfrog Instances | ให้เลือก Process อย่างปลอดภัย | มีการออกแบบ Fail-Closed |
| เริ่ม Status Changer | ใช้ Client ที่ตรวจพบ | ต้องทดสอบการเชื่อมต่อ |
| Camfrog ถูก Minimize | ทำงานเบื้องหลังโดยไม่แย่ง Focus | กำลังทดสอบ |

**จุดสำคัญ:** จากรายงาน Codex ยืนยันเพียงว่ามี `WindowsCamfrogProcessDiscovery` และ `attach_to_camfrog_client()` แต่ไม่ได้ระบุชัดเจนว่า ZChat เรียกสองฟังก์ชันนี้อัตโนมัติเมื่อเปิดโปรแกรมหรือไม่

### เพิ่มคำสั่งนี้ใน Prompt ที่กำลังทำอยู่

<WritingBlock id="63518" variant="standard">Implement automatic Camfrog client discovery and read-only attachment during ZChat application startup.

Requirements:
- Automatically detect an already-running, verified Camfrog Video Chat.exe.
- Do not require manual Discover or Attach actions for a single unambiguous verified client.
- If Camfrog is not running, display CLIENT_NOT_RUNNING and continue monitoring with bounded polling.
- When Camfrog starts later, automatically discover and attach in read-only mode.
- When Camfrog exits, detach safely and refresh the UI state.
- When multiple Camfrog processes are detected, require explicit user selection.
- Persist only safe process-selection preferences, never credentials or hardcoded PIDs.
- Never launch, terminate, restore, or focus Camfrog automatically.
- Do not automatically start status-changing or messaging actions merely beca

ให้ *.exe run แบบ standalone ทั้งหมด แยก 1. feature 1.exe

## ZChat — Standalone Architecture: 1 Feature = 1 EXE

กำหนดให้ **ทุก Feature ของ `cvsz/zchat` สามารถทำงานแบบ Standalone ได้อย่างสมบูรณ์** โดยไม่ต้องเปิด `zchat-client.exe` หรือโปรแกรม ZChat อื่นเป็นตัวกลาง

แต่ละ `.exe` ต้องตรวจหา Camfrog Client อัตโนมัติ มี Configuration, Worker, Logs และ Lifecycle ของตัวเอง และไม่รบกวน Mouse/Keyboard ของผู้ใช้

### Target Executables

| Executable | Feature | Standalone |
|---|---|---|
| `room-control.exe` | ควบคุมห้องสนทนา | Required |
| `chat-im-private.exe` | Private IM | Required |
| `status-random.exe` | Random Status | Required |
| `status-marquee.exe` | Marquee Status | Required |
| `im-autoreply.exe` | IM Auto Reply | Required |
| `web-status.exe` | Website Status | Required |
| `music-dj.exe` | Music DJ | Required |
| `status-changer.exe` | Status Changer | Required |
| `zchat-client.exe` | ZChat Client | Required |
| `line-status-changer.exe` | LINE Status Changer | Required |

**Standalone** หมายถึงไม่พึ่งพา ZChat Executable ตัวอื่น แต่ Feature ที่ใช้ Camfrog ยังต้องมี Official Camfrog Client ติดตั้งและทำงานอยู่ตามข้อกำหนดของ Feature นั้น

## Master Implementation Prompt

<WritingBlock id="91742" variant="document"># ZChat — Full Standalone Windows Application Architecture

**Repository:** https://github.com/cvsz/zchat

**Primary Goal:** One Feature = One Independently Executable Application

## ROLE

Act as a Principal Windows Software Architect, Senior Python Engineer, Build & Release Engineer, Security Auditor, and QA Automation Engineer.

Refactor and validate the ZChat Windows application suite so that every feature is packaged and operates independently.

## 1. Mandatory Standalone Contract

Every feature must:

- Launch directly from its own `.exe`.
- Never require `zchat-client.exe` or another ZChat feature executable.
- Automatically discover a verified running Camfrog client when relevant.
- Continue bounded background discovery if Camfrog is not running.
- Support safe automatic read-only attachment.
- Maint

ให้ *.exe run แบบ standalone ทั้งหมด แยก 1. feature 1.exe zchat-client.exe = merge all feture to single  control panel form zchat-server

## ZChat — Final Architecture: Standalone Features + Unified Control Panel

กำหนด Architecture ใหม่สำหรับ [`cvsz/zchat`](https://github.com/cvsz/zchat) ให้รองรับการใช้งาน **2 รูปแบบพร้อมกัน** ได้แก่

1. **Standalone Applications:** แต่ละ Feature มี `.exe` ของตัวเอง สามารถเปิดและใช้งานแยกกันได้โดยไม่ต้องเปิด ZChat Control Panel
2. **Unified Control Panel:** `zchat-client.exe` รวมทุก Feature ไว้ใน Control Panel เดียว โดยเชื่อมต่อกับ `zchat-server` สำหรับจัดการ Configurations, Status, Jobs, Agents และ Logs จากส่วนกลาง

ทั้งสองรูปแบบต้องใช้ Shared Core และ Business Logic เดียวกัน ไม่ใช่พัฒนา Feature ซ้ำสองชุด

## 1. Target Architecture

<box border radius="xl" padding={3} gap={3}>
  <box background="surface-secondary" radius="lg" padding={3} align="center" gap={1}>
    **ZChat Server — Central Control Plane**
    <text color="secondary" size="xs" textAlign="center">FastAPI · PostgreSQL · Authentication · RBAC · Jobs · Config · Audit · Realtime Status</text>
  </box>
  <row justify="center" align="center">
    <icon name="arrow-up-down" color="secondary"/>
    <text size="xs" color="secondary">Authenticated HTTPS / WebSocket</text>
  </row>
  <box background="rgba(40,130,190,0.07)" radius="lg" padding={3} gap={2}>
    <row align="center" justify="center" gap={2}>
      <icon name="layout-dashboard"/>
      **zchat-client.exe**
    </row>
    <text size="sm" textAlign="center">Unified Control Panel — รวมทุก Feature</text>
    <grid columns={2} gap={2}>
      {#each ["Room Control","Private IM","Random Status","Marquee Status","IM Auto Reply","Web Status","Music DJ","Status Changer","LINE Status"] as name}
        <grid-item>
          <box background="surface" radius="md" padding={2} align="center">
            <text size="xs" weight="medium" textAlign="center">{name}</text>
          </box>
        </grid-item>
      {/each}
    </grid>
  </box>
  <row justify="center">
    <icon name="arrow-down-up" color="secondary"/>
  </row>
  <box border radius="lg" padding={3} gap=

add sync lock userid ของผู้ใช้ ได้ไหม

ได้ครับ และแนะนำให้เพิ่ม **User Identity Synchronization + Distributed Lock by User ID** เข้าไปใน ZChat Architecture เพื่อป้องกัน Standalone EXEs และ `zchat-client.exe` ทำงานซ้ำหรือแย่งกันควบคุมบัญชี Camfrog เดียวกัน

โดยใช้ **User ID เป็นตัวระบุบัญชีหลัก (Canonical Identity)** แทนการอ้างอิงเพียง Nickname, PID หรือ HWND

## 1. Proposed Architecture

```text
                  ZChat Server
               FastAPI + PostgreSQL
                        |
              User Identity Registry
                        |
             Distributed Lock Manager
                        |
         +--------------+--------------+
         |              |              |
   status-random    status-marquee   zchat-client
       .exe             .exe             .exe
         |              |              |
         +--------------+--------------+
                        |
             Canonical Camfrog User ID
                        |
               Real Camfrog Client
```

### Identity Model

ควรแยก User ID ออกเป็นสองระดับ:

- `zchat_user_id` — UUID ภายในระบบ ZChat ใช้สำหรับ Authentication, Authorization และ Ownership
- `camfrog_user_id` — ID ของบัญชี Camfrog ที่ตรวจสอบได้จากแหล่งข้อมูลที่ได้รับอนุญาต

**หาก Camfrog User ID ยังไม่มีหลักฐานยืนยัน ห้ามสร้าง ID สมมติหรือใช้ Nickname แทนแล้วถือว่า Verified**

ให้ใช้ Internal Account UUID ผูกกับ Process Identity ที่ตรวจสอบแล้ว และรายงานสถานะ `IDENTITY_UNVERIFIED` จนกว่าจะยืนยัน External Account Identity ได้

## 2. Locking Strategy

| Resource | Lock Key | Purpose |
|---|---|---|
| Camfrog Account | `camfrog:user:{id}` | Account-level coordination |
| Status Writer | `camfrog:user:{id}:status` | ป้องกัน Random/Marquee/Changer ชนกัน |
| Room Control | `camfrog:user:{id}:room:{room_id}` | ป้องกัน Room Actions ซ้ำ |
| Private IM | `camfrog:user:{id}:im:{recipient_id}` | ป้องกันการส่งข้อความซ้ำ |
| Worker Lifecycle | `zchat:worker:{instance_id}` | ป้องกัน Worker ซ้ำ |
| LINE User | `line:user:{id}:status` | แยก Lock Domain ของ LINE |

ไม่จำเป

เปิดหลาย Feature พร้อมกันได้ โดยไม่ให้ Random Status, Marquee Status และ Unified Control Panel แย่งกันแก้สถานะของบัญชีเดียวกัน และยังรองรับการขยายไปยัง Windows หลายเครื่องผ่าน `zchat-server`

ถูกต้องครับ นี่ควรเป็น **Core Architecture Requirement ของ ZChat** เพื่อให้ทุก Feature ทำงานพร้อมกันได้ โดยไม่มีการแย่งควบคุม Camfrog Account เดียวกัน และสามารถขยายไปยัง Windows หลายเครื่องผ่าน `zchat-server` ได้

## 1. Architecture: Multi-Feature, Multi-Machine, Single Writer

```text
                  ZChat Server
            FastAPI + PostgreSQL
                      |
             Identity Registry
                      |
           Distributed Lease Manager
                      |
             Command Coordinator
                      |
          +-----------+-----------+
          |                       |
     Windows PC A            Windows PC B
          |                       |
   Local Lock Manager       Local Lock Manager
          |                       |
   +------+------+          +-----+------+
   |      |      |          |            |
 Random Marquee Unified    Status       Room
 Status Status  Client     Changer     Control
   |      |      |          |            |
   +------+------+----------+------------+
                      |
          Resource-Scoped Ownership
                      |
               Camfrog Accounts
```

**หลักการ:** เปิดหลาย Feature พร้อมกันได้ แต่สำหรับบัญชีเดียวกัน ต้องมี Writer เพียงรายเดียวต่อ Resource ที่อาจขัดแย้งกัน

## 2. การทำงานที่ต้องการ

| Scenario | Expected Behavior |
|---|---|
| Random Status + Marquee Status บัญชีเดียวกัน | ตัวแรกได้ Lock อีกตัวรอ |
| Status Changer + Unified Client บัญชีเดียวกัน | ไม่สามารถเขียน Status พร้อมกัน |
| Room Control + Status Changer | ทำงานพร้อมกันได้ หากไม่แย่ง Resource |
| Random Status คนละบัญชี | ทำงานพร้อมกันได้ |
| สอง Windows ควบคุมบัญชีเดียวกัน | Server กำหนด Write Authority |
| Worker Crash | Lease หมดอายุและเข้าสู่ Reconciliation |
| Server Disconnect | หยุด Server-managed Writes |
| Client Reconnect | ตรวจ Identity/Lease ใหม่ก่อน Execute |

## 3. Implementation Contract

ควรใช้ **Account Identity + Resource Key + Lease + Fencing Generation**

```python
resource_key

what we can do all next

ผมจะจัดลำดับงานถัดไปจากสถาปัตยกรรม ZChat ที่กำหนดไว้ และตรวจสถานะ GitHub ล่าสุดก่อน เพื่อแยกงานที่ทำแล้วออกจากงานที่ยังต้องพัฒนาและทดสอบจริงครับ

# ZChat — Complete Next Roadmap

**เป้าหมาย:** ยกระดับ `cvsz/zchat` ให้เป็นระบบที่รองรับ Standalone EXEs, Unified Control Panel, Central Server, User ID Synchronization และ Multi-Machine Orchestration โดยทุก Feature ทำงานพร้อมกันได้โดยไม่แย่งกันควบคุมบัญชี Camfrog หรือรบกวน Mouse/Keyboard

จากการตรวจ GitHub ล่าสุด ยังพบว่า `main` อยู่ที่ Commit `6ba80e6`, PR #44 ยังเปิดอยู่ และยังไม่พบ `camfrog_windows_runtime.py` บน `main` ดังนั้นงานที่ Codex รายงานว่าเสร็จแล้วอาจยังอยู่ใน Local Working Tree หรือ Branch อื่น

## 1. Roadmap ทั้งระบบ

<box gap={3}>
  <row align="start" gap={3}>
    <box background="surface-secondary" radius="lg" padding={2}>
      <icon name="shield-check" size="lg"/>
    </box>
    <box flex="1" gap={1}>
      **Phase 0 — Consolidate & Audit**

      ตรวจ Local Changes, Runtime Tests, PR #44, CI, Security และย้ายงานที่ยืนยันแล้วเข้ากระบวนการ Review

      <badge color="warning">In progress / verification needed</badge>
    </box>
  </row>
  <divider color="subtle"/>
  <row align="start" gap={3}>
    <box background="surface-secondary" radius="lg" padding={2}>
      <icon name="monitor" size="lg"/>
    </box>
    <box flex="1" gap={1}>
      **Phase 1 — True Background Engine**

      ทำให้ Status Changer, Random และ Marquee เปลี่ยนสถานะได้โดยไม่แย่ง Focus, Mouse, Keyboard, Clipboard หรือแก้ Windows Sound Settings
    </box>
  </row>
  <divider color="subtle"/>
  <row align="start" gap={3}>
    <box background="surface-secondary" radius="lg" padding={2}>
      <icon name="lock-keyhole" size="lg"/>
    </box>
    <box flex="1" gap={1}>
      **Phase 2 — User Identity & Lock Manager**

      เพิ่ม Canonical Account UUID, Windows Local Lock, PostgreSQL Lease, Fencing Generation และ Reconciliation
    </box>
  </row>
  <divider color="subtle"/>
  <row align="start" gap={3}>
    <box background="surface-secondar

▾ Thought for 7s
  The code utilizes `psutil` in process discovery and identity validation. The presence of `psutil`
  needs verification within the project's dependency file to ensure proper setup. A dependency check is
  necessary as `psutil`'s absence in the dependencies would indicate a potential installation or
  fallback mechanism oversight.
  Here is the current status across active tracks and recommendations for following up:
  ──────
  ### 1. Active Pull Request #44 https://github.com/cvsz/zchat/pull/44 (fix/ui-room-control-pid-
  exclusion)
  • Status: Approved by policedbc, all 9 CI checks passing (CodeQL, Ubuntu tests, Windows build,
  Control Server, Dependency Review).
  • Scope: Exclude self-PID and fail closed in room_control_gui.py when verifying single Camfrog
  process instances.
  • Action: Ready to merge into main (e.g. gh pr merge 44 --squash --delete-branch).
  ──────
  ### 2. Working Tree & Git State

  • Rebase state: A leftover no-op interactive rebase on feat/web-status-log-marquee (PR #42,
  already merged into main) is active in .git/rebase-merge. Running git rebase --abort will clean
  this state without impacting working files.
  • Repository health: validate_repo.py passed cleanly (structure and Markdown links valid).
  ──────
  ### 3. New Runtime Integration (Uncommitted Work in Tree)

  New implementation modules and live Windows 11 evidence artifacts for Camfrog 8.5 have been
  prepared:
  • camfrog_windows_runtime.py: Authenticode verification (WinVerifyTrust, CryptQueryObject),
  structural window classification (Internet Explorer_Server, VideoViewport, CTreeViewTS,
  CComboBoxTS), client attachment, and state separation.
  • camfrog_status_engine.py: Background status execution engine eliminating desktop disruption
  (removes registry sound modification, no focus stealing).
  • test_camfrog_windows_runtime.py: Unit test suite (needs psutil added to requirements.txt or
  mocked for the headless Linux test suite).
  • main-process

## ZChat — Recommended Execution: ทำทั้ง 3 งานตามลำดับ

จากรายงานล่าสุด แนะนำให้ Codex **ดำเนินการทั้ง 3 ข้อ ไม่ต้องเลือกเพียงข้อเดียว** โดยเน้นรักษา Local Changes และไม่ทำให้ Runtime Integration ที่พัฒนาไว้สูญหาย

ลำดับที่เหมาะสม:

1. **Merge PR #44** หลังยืนยัน CI, independent review และ Branch Protection ล่าสุด
2. **Resolve Git Rebase State** โดยสำรองงานที่ยังไม่ Commit ก่อน ตรวจสอบว่า Rebase ไม่มีการเปลี่ยนแปลงสำคัญ แล้วจึง `git rebase --abort` เฉพาะเมื่อปลอดภัย
3. **Fix `psutil` Dependencies และ Linux CI** พร้อมทดสอบ `camfrog_windows_runtime.py` และ `camfrog_status_engine.py`
4. **สร้าง Feature Branch + PR** สำหรับ Real Runtime Integration และ True Background Status Changer
5. **Verify Real Camfrog Behavior** โดยเฉพาะการเปลี่ยน Status ขณะ Camfrog Minimized โดยไม่แย่ง Mouse/Keyboard

ข้อควรระวัง: แม้ `psutil` จะติดตั้งใน `.venv-runtime` แล้ว แต่ยังต้องระบุ Runtime Dependency ใน Project Metadata ที่ใช้ Build จริง และไม่ควรให้ Linux CI พยายามเรียก Windows-only APIs โดยไม่มี Platform Guard

## อัปเดตผลตรวจ GitHub จริง

ตรวจสอบ [PR #44](https://github.com/cvsz/zchat/pull/44) อีกครั้ง พบว่า:

<row align="center" gap={2}>
  <badge color="success">Merged</badge>
  <text weight="medium">PR #44 ปิดและ Merge เรียบร้อยแล้ว</text>
</row>

CI ทั้ง 9 Check Runs แสดง `completed / success` รวมถึง CodeQL, Windows Build, Dependency Review และ Tests

ดังนั้น **ไม่ต้อง Merge PR #44 ซ้ำ** และสามารถไปทำขั้นตอน Git Rebase Cleanup กับ Runtime Integration ต่อได้เลย

### Prompt สำหรับ Codex

<WritingBlock id="64127" variant="standard">Proceed autonomously with the remaining ZChat implementation work.

Repository: cvsz/zchat
Local workspace: D:\data\zchat

PR #44 is already merged. Do not attempt to merge it again.

1. Inspect and preserve all local changes, untracked files, and active rebase metadata.
2. Create a safe backup of the current working state before modifying Git history or aborting the stale rebase.
3. Resolve the obsolete PR #42 rebase state without losing current work.
4. S

rewrite full master prompt  "  "

[ข้อความที่วาง (1)(20261016-170324).txt]

# ZCHAT — ULTIMATE MASTER ENGINEERING PROMPT V4.0

**Repository:** [cvsz/zchat](https://github.com/cvsz/zchat)  
**Workspace:** `D:\data\zchat`  
**Target:** Windows 11 · Camfrog Video Chat 8.5.0.51219 · Python 3.14  
**Architecture:** Standalone EXEs + Unified Client + Central Server + Multi-Machine Coordination

ผมรวมและปรับปรุง Prompt จากเอกสารที่แนบและข้อกำหนดล่าสุดทั้งหมด ให้เป็น **Master Prompt เดียว** สำหรับ Codex, Kilo CLI หรือ Autonomous Engineering Agent โดยเน้น 5 เป้าหมายหลัก:

1. ทุก Feature ทำงาน Standalone ได้ — `1 Feature = 1 EXE`
2. `zchat-client.exe` รวมทุก Feature เป็น Unified Control Panel
3. `zchat-server` จัดการ Account, User ID, Agents และ Windows หลายเครื่อง
4. ทุก Feature ทำงานเบื้องหลังโดยไม่รบกวน Mouse, Keyboard, Focus, Clipboard หรือ Windows Sound Settings ในโหมด Strict Background
5. ป้องกันหลาย Feature แย่งควบคุมบัญชีเดียวกันด้วย Canonical Identity, Local Locks และ Distributed Leases

Prompt จะสั่งให้ Agent ตรวจงานที่ทำไปแล้วก่อน ไม่เขียนใหม่โดยไม่จำเป็น ไม่ทำลาย Local Changes และไม่ประกาศ Production Ready โดยไม่มีหลักฐานจริง

<WritingBlock id="90471" variant="document"># ZCHAT — ULTIMATE MASTER ENGINEERING & EXECUTION PROMPT V4.0

## Autonomous Full-Stack Engineering, Real Camfrog Integration, Standalone Windows Applications, Unified Control Panel, Distributed Resource Coordination & Production Readiness

**Repository:** https://github.com/cvsz/zchat  
**Local Workspace:** `D:\data\zchat`  
**Target OS:** Windows 11  
**Python:** 3.14  
**Camfrog Client:** 8.5.0.51219  
**Execution Strategy:** Investigate → Preserve → Repair → Refactor → Implement → Verify → Build → Review → Release

---

# 1. ROLE AND ENGINEERING MISSION

You are an autonomous multidisciplinary engineering agent operating as:

- Principal Software Architect
- Senior Python / Windows Engineer
- Senior Full-Stack Engineer
- Windows Runtime and UI Automation Engineer
- Distributed Systems Architect
- Security Auditor
- Database and DevOps Engineer
- QA Automation Engineer

- \# Role & Profile\
  คุณคือ \*\*Ultimate Super Ultra Intelligence Full-Stack Developer & Full-Stack Mobile Developer & Systems Architect Agent\*\* ที่มีความเชี่ยวชาญระดับสูงในการตรวจสอบ ควบคุม และพัฒนาทุกระบบ (All Systems) ทั้ง Backend, Frontend, Database, DevOps, API Integrations และ Infrastructure ทั้งหมดใน Repository นี้ \
  \
  คุณได้รับมอบหมายให้เจาะลึก วิเคราะห์ และแก้ไขปัญหาอย่างอิสระ (Independent Implementation) เพื่อยกระดับ Codebase ทุกส่วนให้พร้อมใช้งานจริงในระดับ Production (Production-Grade Ready)\
  \
  \---\
  \
  \# Core Directives & Workflow\
  \
  1\. \*\*Comprehensive Systems Investigation & Root Cause Analysis:\*\*\
  &#x20;  \- ทำการ Drill Deeper และตรวจเช็ก \*\*ทุกระบบ ทุกสถาปัตยกรรม และทุกโมดูล\*\* ภายใน Repository ทั้งหมดอย่างละเอียด\
  &#x20;  \- ค้นหาและจัดการทุก "Red Flag", Bugs, Incomplete Features, Invalid Logic, Security Vulnerabilities, Performance Bottlenecks และ Tech Debt ในทุกระบบ\
  \
  2\. \*\*Universal Fix, Upgrade, & Full Implementation:\*\*\
  &#x20;  \- แก้ไข อัปเกรด และเติมเต็มส่วนที่ขาดหายไปของทุกระบบให้สมบูรณ์ 100%\
  &#x20;  \- เขียนโค้ดตามมาตรฐาน Production-Grade (มี Robust Error Handling, Type Safety, Clean Architecture และ Scalability)\
  \
  3\. \*\*Validation & Testing:\*\*\
  &#x20;  \- ตรวจสอบความถูกต้องของทุกระบบ ทดสอบการเชื่อมต่อ (Integration Test) และรัน Build/Lint จนมั่นใจว่าไม่มี Error\
  \
  \---\
  \
  \# Operating Rules & Language Standards\
  \
  1\. \*\*Language Policy:\*\*\
  &#x20;  \- \*\*การสื่อสารทั่วไป:\*\* ใช้ \*\*ภาษาไทย\*\* \
  &#x20;  \- \*\*งานด้านเทคนิค:\*\* โค้ด, คอมเมนต์, ชื่อฟังก์ชัน, เอกสาร, Commit Messages และ PR Descriptions ต้องใช้ \*\*ภาษาอังกฤษ\*\* เท่านั้น\
  \
  2\. \*\*Final Release & Deployment Protocol (เมื่อทำทุกระบบเสร็จสิ้นสมบูรณ์):\*\*\
  &#x20;  เมื่อทุกระบบได้รับการแก้ไขและตรวจสอบเรียบร้อยแล้ว ให้ดำเนินการ GPG Commit, Push และ เนินตามลำดับคำสั่ง GitHub CLI ดังนี้:\
  \
  &#x20;  \- \*\*Step 1: Switch Account for Review & Audit\*\*\
  &#x20;    สลับไปยังบัญชีผู้ตรวจสอบด้วยคำ

## ZChat — Ultimate Autonomous Engineering & Production Release Prompt V5.0

ปรับรวม Role & Profile, Core Directives, Language Policy และ GPG/GitHub Release Protocol ล่าสุด เข้ากับ Master Prompt ของ ZChat เพื่อให้ AI Agent สามารถตรวจสอบ พัฒนา แก้ไข ทดสอบ และส่งมอบงานทั้ง Repository ได้อย่างเป็นระบบ โดยรักษาข้อกำหนด **1 Feature = 1 EXE, Unified Control Panel, True Background Execution และ Multi-Machine Synchronization**

<WritingBlock id="71842" variant="document"># ZCHAT — ULTIMATE SUPER ULTRA INTELLIGENCE ENGINEERING MASTER PROMPT V5.0

## Role & Profile

คุณคือ **Ultimate Super Ultra Intelligence Full-Stack Developer & Full-Stack Mobile Developer & Systems Architect Agent** ที่มีความเชี่ยวชาญระดับ Principal และ Senior ในด้าน:

- Full-Stack Software Engineering
- Windows Desktop Development
- Mobile Application Development
- Backend, Frontend และ Database Architecture
- API Integrations และ Distributed Systems
- Windows Runtime Integration และ UI Automation
- AI Automation และ Agent Orchestration
- DevOps, CI/CD และ Infrastructure
- Cybersecurity, Code Audit และ Supply-Chain Security
- Automated Testing, Quality Assurance และ Release Engineering
- Performance, Reliability, Scalability และ Observability

คุณได้รับมอบหมายให้ตรวจสอบ วิเคราะห์ แก้ไข อัปเกรด Refactor และเติมเต็มระบบภายใน Repository นี้อย่างอิสระ (Independent Implementation) เพื่อยกระดับ Codebase ให้พร้อมสำหรับการใช้งานจริงระดับ Production ภายใต้หลักฐานการตรวจสอบที่พิสูจน์ได้

**Repository:** https://github.com/cvsz/zchat  
**Workspace:** `D:\data\zchat`  
**Primary Platform:** Windows 11  
**Target Client:** Camfrog Video Chat 8.5.0.51219  
**Engineering Mode:** Autonomous, Evidence-Driven, Production-Oriented

---

# 1. CORE DIRECTIVES & WORKFLOW

## 1.1 Comprehensive Systems Investigation & Root Cause Analysis

ทำการ Drill Deeper, Investigate และ Audit ทุกระบบ ทุก Architecture และทุกโมดูลภายใน Repository ที่เกี่ยวข้องกับการทำงานจริง

ตรวจสอบ:

- Bugs และ Incomplete Features
- Incorrect Logic และ Edge

ขาดอะไรอีกไหม

มีครับ **Master Prompt V5.0 ครอบคลุม Architecture หลักของ ZChat ค่อนข้างครบแล้ว แต่ยังขาดข้อกำหนดสำคัญบางส่วนที่มีผลต่อ Production Readiness โดยตรง** โดยเฉพาะการยืนยัน User Identity, การควบคุมหลายเครื่อง, Desktop Agent Security, Database Migrations และการทดสอบ EXE ที่ Build แล้วจริง ๆ

ผมแนะนำให้เพิ่มอีก **15 หัวข้อ** เพื่อยกระดับเป็น V6.0 โดยไม่ต้องเขียน V5.0 ใหม่ทั้งหมด

## 1. Gap Analysis — สิ่งที่ยังขาด

| Priority | Missing Component | เหตุผล |
|---|---|---|
| P0 | **Local Execution Authority** | Windows Mutex อย่างเดียวไม่เพียงพอสำหรับควบคุม External GUI Actions |
| P0 | **Account Identity Proof** | ป้องกันการผูก Camfrog Account ผิด User ID |
| P0 | **Distributed Split-Brain Protection** | ป้องกัน Windows สองเครื่องสั่งงานบัญชีเดียวกันเมื่อเครือข่ายขาด |
| P0 | **Explicit User Consent & Command Policy** | ป้องกัน Server สั่ง External Actions โดยไม่ได้รับอนุญาต |
| P0 | **Emergency Stop / Kill Switch** | หยุด Workers และระงับ Commands ทั้งระบบอย่างปลอดภัย |
| P0 | **API Contract & Version Compatibility** | ป้องกัน Client/Server คนละเวอร์ชันทำงานผิดพลาด |
| P1 | **Database Migration & Rollback** | รองรับการเปลี่ยน Schema โดยไม่สูญเสียข้อมูล |
| P1 | **Multi-Tenant Isolation** | ป้องกัน User หรือ Tenant เข้าถึงบัญชีของผู้อื่น |
| P1 | **Real Packaged EXE Acceptance** | Source Tests ผ่านไม่ได้หมายความว่า EXE ทำงานได้ |
| P1 | **Secure Agent Enrollment** | ป้องกัน Windows Agent ปลอมเชื่อมต่อ Server |
| P1 | **Observability & Alerting** | ตรวจ Worker Crash, Deadlock, Lock Conflicts |
| P1 | **Automated Recovery & Reconciliation** | รับมือ Commands ที่ไม่ทราบผลหลัง Crash |
| P2 | **Auto-update & Rollback** | อัปเดต EXE หลายเครื่องโดยไม่ทำให้ Feature เสีย |
| P2 | **Load / Stress / Soak Testing** | ตรวจสอบ Memory Leak และ Worker Stability |
| P2 | **Feature Capability Matrix** | ระบุว่าแต่ละ Feature รองรับ Background, Offline และ Remote Control จริงหรือไม่ |

### จุดที่สำคัญที่สุด

**Distributed Lock ไม่ได้แปลว่าปลอดภัยแล้วโดยอัตโนมัติ**

สมมติเปิด `status-random.exe`

ดู cvsz/zworkforce และบอกมาว่า ขาดอะไรอีกไหม

[docs.zip]

ผมจะตรวจ `cvsz/zworkforce` และเอกสารใน `docs.zip` ที่แนบมา แล้วเทียบกับ ZChat Master Prompt V6.0 เพื่อหาว่ายังขาดส่วนใด โดยแยกข้อค้นพบจากโค้ดจริงกับข้อเสนอด้านสถาปัตยกรรมครับ

พบจุดสำคัญแล้ว: `zworkforce` มีระบบ Governance, Durable Jobs, Policy-as-Code, Approval Gates และ Observability ที่ ZChat สามารถนำแนวคิดไปใช้ได้ แต่ `apps/zchat` ใน `zworkforce` เป็น Chat UI สำหรับ AI Gateway ไม่ใช่ Camfrog ZChat ตัวเดียวกัน จึงต้องกำหนดขอบเขต Integration ให้ชัดเจน ไม่รวมสองระบบเข้าด้วยกันโดยตรงครับ

# วิเคราะห์ `cvsz/zworkforce` เทียบกับ ZChat — ยังขาดอะไรอีก?

**พบว่า ZChat Master Prompt V6.0 ยังขาด Integration Layer สำคัญสำหรับเชื่อมกับ zWorkforce** แม้ว่าจะมีข้อกำหนดเรื่อง Standalone EXEs, Unified Client, Account Locking และ Multi-Machine Control แล้วก็ตาม

ผมตรวจ Repository [`cvsz/zworkforce`](https://github.com/cvsz/zworkforce) บน GitHub รวมถึงเอกสาร 50 รายการใน `docs.zip` ที่แนบมา

จุดสำคัญคือ **zWorkforce มีความสามารถหลายอย่างที่ ZChat ควรนำมาใช้ผ่าน API/Contracts แทนการสร้างระบบ AI Orchestration และ Governance ซ้ำอีกชุด**

## 1. สิ่งที่ zWorkforce มีอยู่แล้ว

จาก README และเอกสารของบริการที่ตรวจพบ:

| Capability | zWorkforce | สิ่งที่ควรทำกับ ZChat |
|---|---|---|
| Durable Task & Workflow Engine | มี Implementation ตาม README | เชื่อม Job Execution |
| Policy-as-Code / RBAC | มี | ใช้กำกับ Remote Commands |
| Approval-Gated Execution | มี | ใช้กับ Actions ที่มีผลภายนอก |
| Audit & Correlation IDs | มี | เชื่อม Audit Events |
| Model Gateway / Routing | มี | ใช้ AI สำหรับงานที่ได้รับอนุญาต |
| MCP Integration | มี | สร้าง ZChat MCP Adapter |
| PostgreSQL Task Leasing | มี | ตรวจว่าจะ Reuse Contract ได้แค่ไหน |
| Scheduler & Durable Events | มี | เชื่อม ZChat Feature Scheduling |
| Metrics, Tracing, FinOps | มี | รวม Monitoring |
| Emergency Stop | มีใน Action Gateway ที่ตรวจ | ออกแบบ ZChat Stop Contract ให้สอดคล้อง |

**ข้อจำกัด:** ความสามารถเหล่านี้กระจายอยู่หลาย Subsystems และบางบริการยังมี Production Adapters ที่ต้องตั้งค่าเพิ่มเติม ไม่ควรถือว่าทุก Capability เปิดใช

sudo apt-get -y install Wine

สำหรับติดตั้ง **Wine บน Ubuntu 24.04 LTS** เพื่อรันโปรแกรม Windows `.exe` ให้ใช้คำสั่งนี้:

```bash
sudo dpkg --add-architecture i386
sudo apt-get update
sudo apt-get -y install wine wine64 wine32 winbind
```

ตรวจสอบการติดตั้ง:

```bash
wine --version
winecfg
```

ทดลองเปิด ZChat:

```bash
wine /path/to/zchat-client.exe
```

**ข้อควรระวังสำหรับ ZChat + Camfrog:** Wine อาจไม่รองรับ Windows UI Automation, `pywinauto`, WinVerifyTrust และ Native Controls ของ Camfrog ได้ครบถ้วน จึงไม่ควรใช้ Wine เป็นหลักฐานยืนยันว่า True Background Status Changer ทำงานได้บน Windows 11 จริง

หากใช้งานผ่าน **WSL2 Ubuntu** หรือ Ubuntu Server ที่ไม่มี Desktop GUI ต้องตรวจการรองรับ GUI ก่อนด้วย

ต้องการใช้ Wine บน **WSL2 Ubuntu 24.04** หรือ **Ubuntu VM**?

WSL2 Ubuntu 24.04

WSL2 Ubuntu 26.04

สำหรับ **WSL2 Ubuntu 26.04 LTS (Resolute)** บน Windows 11 สามารถติดตั้ง Wine เพื่อทดสอบ Windows `.exe` ได้ โดย Ubuntu 26.04 มีแพ็กเกจ Wine 10.0 ใน Official Repository แล้ว <Cite ref="turn374571search0"/>

## 1. ตรวจสอบ Ubuntu และ WSLg

รันใน WSL2 Ubuntu:

```bash
cat /etc/os-release
uname -m
echo "$DISPLAY"
echo "$WAYLAND_DISPLAY"
```

ควรพบ `VERSION_ID="26.04"` และมีค่า `DISPLAY` หรือ `WAYLAND_DISPLAY` สำหรับเปิด GUI

ใน PowerShell ของ Windows ตรวจสอบและอัปเดต WSL:

```powershell
wsl --version
wsl --update
wsl --shutdown
```

จากนั้นเปิด Ubuntu ใหม่

## 2. ติดตั้ง Wine สำหรับ Ubuntu 26.04

```bash
sudo dpkg --add-architecture i386

sudo apt-get update

sudo apt-get install -y software-properties-common

sudo add-apt-repository -y universe

sudo apt-get update

sudo apt-get install -y \
    wine \
    wine64 \
    wine32:i386 \
    winbind \
    winetricks \
    fonts-wine
```

แพ็กเกจ `wine64`, `wine32` และ `winetricks` มีอยู่ใน Ubuntu 26.04 Universe Repository <Cite ref="turn374571search0"/>

## 3. ตรวจสอบและตั้งค่า Wine

```bash
wine --version

export WINEPREFIX="$HOME/.wine-zchat"
export WINEARCH=win64

wineboot -i
winecfg
```

ตั้ง Windows Version ใน `winecfg` เป็น Windows 10 ก่อน แล้วทดสอบความเข้ากันได้ของแอปพลิเคชัน

## 4. ทดลองเปิด ZChat EXE

ถ้า Repository อยู่ที่ `D:\data\zchat` บน Windows:

```bash
cd /mnt/d/data/zchat

export WINEPREFIX="$HOME/.wine-zchat"

wine dist/status-changer/status-changer.exe
```

หรือ Unified Client:

```bash
wine dist/zchat-client/zchat-client.exe
```

สำหรับ PyInstaller `--onedir` ต้องเก็บ DLL, `_internal` และไฟล์ประกอบทั้งหมดอยู่กับ EXE ตามโครงสร้างเดิม

## 5. ข้อจำกัดสำคัญสำหรับโครงการ ZChat

| Test | WSL2 + Wine |
|---|---|
| EXE Startup | ทดสอบได้ |
| GUI Rendering | ทดสอบได้ถ้า WSLg พร้อม |
| Bundled Dependencies | ทดสอบได้บางส่วน |
| Basic Application Logic | ทดสอบได้ |
| Native WinVerifyTrust | ต้องทดสอบความเข้ากันได้ |
| pywinauto / UI Automation | ไม่เทียบเท่า Windows จริง |
| ตรวจจับ Camfrog ที่เปิดบน Windows Host |

desig gui เป็นรูป ของ แต่ละ module

[Image: แดชบอร์ด ZChat Control Suite]

สร้าง 1 module 1 รูป

[Image: แผงควบคุมห้อง ZChat ทันสมัย]

[Image: หน้าควบคุมห้องแชต ZChat สไตล์ Windows]

ผมจะแยกภาพออกเป็นรายโมดูล โดยให้แต่ละภาพเป็นหน้าต่าง Standalone EXE ของตัวเอง ไม่รวมหลายโมดูลไว้ในภาพเดียว เริ่มจากโมดูลสถานะและระบบข้อความต่อจาก Room Control ที่สร้างไว้แล้วครับ

[Image: แดชบอร์ดปรับสถานะ ZChat]

[Image: หน้าต่าง ZChat เปลี่ยนสถานะแบบนีออน]

เริ่มแยกภาพ GUI แบบ **1 Module = 1 รูป** แล้ว โดยภาพที่สร้างเป็น Concept Design สำหรับพัฒนา Windows Standalone EXEs ไม่ใช่ภาพหน้าจอจากโปรแกรมที่ทำงานจริง

ตอนนี้มีแบบของ **Room Control** และ **Status Changer** แล้ว โดยจะใช้ Dark Theme สีน้ำเงินให้เป็น Design System เดียวกันตลอด ZChat

โมดูลที่เหลือสำหรับออกแบบแยกภาพ ได้แก่ `status-random`, `status-marquee`, `chat-im-private`, `im-autoreply`, `web-status`, `music-dj`, `line-status-changer`, `zchat-client` และ `Account/Lock Management`

สร้าง release gui 1 module 1 รูป   "D:\data\zchat\dist\web-status"
"D:\data\zchat\dist\zchat-client"
"D:\data\zchat\dist\zchat-client-verified"
"D:\data\zchat\dist\chat-im-private"
"D:\data\zchat\dist\im-autoreply"
"D:\data\zchat\dist\music-dj"
"D:\data\zchat\dist\room-control"
"D:\data\zchat\dist\status-changer"
"D:\data\zchat\dist\status-marquee"
"D:\data\zchat\dist\status-random"
D:\data\zchat\line

ทำได้ครับ แต่คำขอนี้มี **11 โมดูล = 11 รูป** ซึ่งเกินลิมิตที่สร้างได้สูงสุด **10 รูปต่อครั้ง**

รายการที่คุณขอมี:
1. web-status  
2. zchat-client  
3. zchat-client-verified  
4. chat-im-private  
5. im-autoreply  
6. music-dj  
7. room-control  
8. status-changer  
9. status-marquee  
10. status-random  
11. line

เลือกได้ 2 แบบ:

**แบบ A:** ตัดออก 1 โมดูล แล้วผมสร้างให้ครบ 10 รูปทันที  
**แบบ B:** ให้ผม **รวม `zchat-client` + `zchat-client-verified` เป็นชุดเดียว** แล้วสร้างครบ 10 รูป

ถ้าต้องการ ผมแนะนำ **แบบ B** มากที่สุด เพราะจะได้เดินงานต่อทันทีครบในรอบเดียว

สร้าง release gui 1 module 1 รูป   "D:\data\zchat\dist\web-status"
"D:\data\zchat\dist\zchat-client-verified"
"D:\data\zchat\dist\chat-im-private"
"D:\data\zchat\dist\im-autoreply"
"D:\data\zchat\dist\music-dj"
"D:\data\zchat\dist\room-control"
"D:\data\zchat\dist\status-changer"
"D:\data\zchat\dist\status-marquee"
"D:\data\zchat\dist\status-random"
D:\data\zchat\line