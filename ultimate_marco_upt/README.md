# ⚡ MacroMaster Pro

แอพ Macro แบบ Python GUI ที่ตั้งค่าปุ่มได้ พร้อมระบบกันหน่วง (Anti-Lag)

---

## 🚀 วิธีติดตั้งและรัน

### Windows
```
pip install pynput
python macro_app.py
```
หรือดับเบิลคลิก `run_windows.bat`

### Linux / macOS
```
pip3 install pynput
python3 macro_app.py
```
หรือ `bash run_linux_mac.sh`

> **macOS**: อาจต้องให้สิทธิ์ Accessibility ใน System Preferences → Security & Privacy → Accessibility

---

## 📋 วิธีใช้งาน

### สร้าง Macro ใหม่
1. คลิก **+ Add** ในแผง Macros ด้านซ้าย
2. ตั้งชื่อ Macro ในช่อง Name
3. คลิก **🎯 Record Key** แล้วกดปุ่มที่ต้องการใช้เป็น Trigger

### เพิ่ม Actions
คลิกปุ่มเพิ่ม Action ด้านบนของรายการ:

| ปุ่ม | ทำอะไร |
|------|--------|
| **+ Key** | กดปุ่มคีย์บอร์ด เช่น `a`, `f5`, `enter`, `ctrl` |
| **+ Text** | พิมพ์ข้อความ |
| **+ Click** | คลิกเมาส์ (`left`, `right`, `middle`) |
| **+ Delay** | รอ เช่น `0.5` = ครึ่งวินาที |

### รัน Macros
กดปุ่ม **▶ START MACROS** ด้านล่าง จากนั้นกดปุ่ม Trigger ที่ตั้งไว้

---

## ⚙️ การตั้งค่า (Settings Tab)

| การตั้งค่า | คำอธิบาย |
|-----------|---------|
| **Speed Multiplier** | เพิ่มความเร็วทุก delay — 1× = ปกติ, 2× = เร็วสองเท่า |
| **Debounce Delay** | ระยะเวลาขั้นต่ำระหว่างการกระตุ้น (ป้องกันกดซ้ำเร็วเกินไป) |
| **Max Concurrent** | จำนวน Macro ที่รันพร้อมกันสูงสุด |

---

## 🛡️ ระบบกัน Anti-Lag

- แต่ละ Macro รันบน **Thread แยก** → UI ไม่ค้างเด็ดขาด
- **Debounce** — ป้องกันการ trigger ซ้ำรัวๆ ภายในเวลาสั้น
- **Max Concurrent** — จำกัดจำนวน Thread เพื่อไม่ให้ระบบล้น
- **Minimum delay 1ms** — ป้องกัน CPU busy-spin
- **Thread-safe Lock** — ป้องกัน race condition

---

## 💾 Config

การตั้งค่าทั้งหมดบันทึกอัตโนมัติใน `macros_config.json` (ไฟล์เดียวกับ `macro_app.py`)

---

## 📦 Dependencies

- Python 3.9+
- `pynput` (keyboard & mouse control)
- `tkinter` (built-in กับ Python)
