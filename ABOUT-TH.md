# เกี่ยวกับ cvsz

English version: `ABOUT-EN.md`.

`cvsz` เป็น builder ที่เน้นซอฟต์แวร์แบบ AI-first, developer platforms, automation, infrastructure และระบบที่มุ่งสู่ production

## ด้านที่มุ่งเน้น

- เครื่องมือ AI coding และระบบ autonomous/agentic
- แพลตฟอร์มแอป AI และการเชื่อม model/API
- developer platforms, API, SDK และ internal tooling
- platform engineering, infrastructure automation, CI/CD และ DevOps
- สถาปัตยกรรมที่คำนึงถึง security และการ hardening repository
- workflow automation, bot, social และ commerce integrations
- สถาปัตยกรรม payment, wallet, ledger และระบบการเงิน
- ระบบ media, streaming, multimodal, speech, image, OCR และ search
- โครงสร้างพื้นฐานเกมและแอป interactive
- เครื่องมือ OpenAPI และการเชื่อม service

## ปรัชญาวิศวกรรม

โปรเจกต์ควรมุ่งสู่:

- ปลอดภัยเป็นค่าเริ่มต้น
- automation-first
- แยกส่วนและใช้ซ้ำได้
- ดูแลง่าย
- สังเกตได้
- ทดสอบได้
- มีเอกสาร
- ขับเคลื่อนด้วยหลักฐาน
- เป็นมิตรกับการปรับปรุงทีละน้อย

ความล้มเหลวด้าน security/quality ควรแก้ ไม่ใช่เลี่ยง CI, infrastructure, เอกสาร, recovery, repository controls และ operational readiness ถือเป็นส่วนหนึ่งของ product engineering

## ทิศทาง ztemplate

Template นี้ตั้งใจให้ repository ใหม่มีรากฐานที่เป็นระเบียบตั้งแต่ commit แรก:

- governance และ ownership
- security policy
- ขั้นตอนเปลี่ยนที่ป้องกัน
- CI/security automation
- ดูแล dependency
- แนวทาง release/recovery
- เอกสารสถาปัตยกรรม
- สัญญาการทำงานของ AI agent
- ความหมายของ evidence-state
- การยืนยัน repository administration
- แนวทาง rollout อย่างปลอดภัยสำหรับ repository เดิม

ตัว template ไม่ได้อ้างว่าแอปที่สร้างพร้อม production ความพร้อมของแอปยังต้องพิสูจน์ด้วยหลักฐานตาม stack/สภาพแวดล้อม

## GitHub

- Handle: `cvsz`
- Repository namespace: `github.com/cvsz`

---

โปรไฟล์นี้ตั้งใจมีเฉพาะข้อมูลทางเทคนิค/โปรเจกต์ที่ปลอดภัยต่อสาธารณะ ห้ามเพิ่ม credentials, ข้อมูลบัญชีส่วนตัว, ความลับส่วนบุคคล และข้อมูลระบุตัวตนที่อ่อนไหวลงใน template repository สาธารณะ
