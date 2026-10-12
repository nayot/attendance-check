"""User-interface languages.

Strings are written in English in the code and templates and looked up in a
catalog per language; a missing entry falls back to English. To add a
language, add a catalog to CATALOGS and an entry to LANGUAGES.
"""

import re
from datetime import datetime

LANGUAGES = {"en": "English", "th": "ไทย"}

TH = {
    # Layout and navigation
    "Settings": "ตั้งค่า",
    "Sign out": "ออกจากระบบ",
    "Sign in": "เข้าสู่ระบบ",
    "Home": "หน้าแรก",
    "Language": "ภาษา",
    "Help": "คู่มือ",

    # Welcome / student home
    "Teachers: sign in to start a class session and show its check-in QR code.":
        "อาจารย์: เข้าสู่ระบบเพื่อเริ่มคาบเรียนและแสดง QR code สำหรับเช็คชื่อ",
    "Students: scan the QR code on the classroom screen with your phone's camera.":
        "นักศึกษา: สแกน QR code บนจอในห้องเรียนด้วยกล้องโทรศัพท์",
    "You're signed in": "เข้าสู่ระบบแล้ว",
    "as": "ในชื่อ",
    "To check in, scan the QR code on the classroom screen with your phone's camera.":
        "สแกน QR code บนจอในห้องเรียนด้วยกล้องโทรศัพท์เพื่อเช็คชื่อ",
    "Change your name": "เปลี่ยนชื่อ",

    # Login, code, profile
    "Sign in to finish checking in. Your scan is saved for 3 minutes.":
        "เข้าสู่ระบบเพื่อเช็คชื่อให้เสร็จ ระบบจำการสแกนของคุณไว้ 3 นาที",
    "Use your institution account": "ใช้บัญชีของสถาบัน",
    "Continue with {provider}": "เข้าสู่ระบบด้วย {provider}",
    "or get a code by email": "หรือรับรหัสทางอีเมล",
    "Email": "อีเมล",
    "Email me a sign-in code": "ส่งรหัสเข้าสู่ระบบทางอีเมล",
    "No sign-in method is configured. Set OIDC_PROVIDERS or OTP_LOGIN in the environment.":
        "ยังไม่ได้ตั้งค่าวิธีเข้าสู่ระบบ กรุณากำหนด OIDC_PROVIDERS หรือ OTP_LOGIN",
    "Enter code": "กรอกรหัส",
    "Check your email": "ตรวจสอบอีเมลของคุณ",
    "We sent a 6-digit code to": "เราส่งรหัส 6 หลักไปที่",
    "Code": "รหัส",
    "Use a different email": "ใช้อีเมลอื่น",
    "Your name": "ชื่อของคุณ",
    "Shown on the attendance list next to {email}.": "แสดงในรายชื่อผู้เข้าเรียนคู่กับ {email}",
    "Full name": "ชื่อ-นามสกุล",
    "Continue": "ดำเนินการต่อ",

    # Check-in result
    "Checked in": "เช็คชื่อแล้ว",
    "Not checked in": "ยังไม่ได้เช็คชื่อ",
    "Already checked in": "เช็คชื่อไปแล้ว",
    "{phase} recorded": "บันทึก{phase}แล้ว",
    "A confirmation email is on its way.": "ระบบกำลังส่งอีเมลยืนยันให้คุณ",
    "This QR code is not valid.": "QR code นี้ใช้ไม่ได้",
    "Check-in is paused. Wait for your teacher to resume it.": "อาจารย์หยุดการเช็คชื่อชั่วคราว กรุณารอให้เปิดอีกครั้ง",
    "This check-in is closed.": "ปิดการเช็คชื่อนี้แล้ว",
    "{email} is not in an allowed email domain.": "{email} ไม่ได้อยู่ในโดเมนอีเมลที่อนุญาต",
    "You have already checked in.": "คุณเช็คชื่อไปแล้ว",
    "Checked in.": "เช็คชื่อแล้ว",

    # Phases
    "Check-in": "เช็คชื่อเข้าเรียน",
    "Mid-class check": "เช็คชื่อระหว่างคาบ",
    "Mid-class check {n}": "เช็คชื่อระหว่างคาบ {n}",
    "Check-out": "เช็คชื่อออก",
    "Class session": "คาบเรียน",

    # Dashboard
    "Dashboard": "หน้าหลัก",
    "Start a class session": "เริ่มคาบเรียน",
    "Class name": "ชื่อวิชา",
    "(optional)": "(ไม่บังคับ)",
    "e.g. Circuit Analysis, Sec 01": "เช่น วงจรไฟฟ้า กลุ่ม 01",
    "Mid-class checks": "จำนวนครั้งเช็คชื่อระหว่างคาบ",
    "Check-out at the end of class": "เช็คชื่อออกเมื่อจบคาบ",
    "Email each student a confirmation": "ส่งอีเมลยืนยันให้นักศึกษาแต่ละคน",
    "Email me the attendance list when I close the session": "ส่งรายชื่อผู้เข้าเรียนให้ฉันทางอีเมลเมื่อปิดคาบ",
    "You can add mid-class checks and a check-out while the class is running.":
        "เพิ่มการเช็คชื่อระหว่างคาบและเช็คชื่อออกได้ระหว่างที่สอน",
    "Start and show QR code": "เริ่มและแสดง QR code",
    "Your sessions": "คาบเรียนของคุณ",
    "No sessions yet.": "ยังไม่มีคาบเรียน",
    "closed": "ปิดแล้ว",
    "running": "กำลังดำเนินการ",
    "checked in": "คนเช็คชื่อ",
    "Emails to your students and your attendance reports are sent from":
        "อีเมลถึงนักศึกษาและรายงานการเข้าเรียนจะส่งจาก",
    "Disconnect Gmail": "เลิกเชื่อมต่อ Gmail",
    "Connect your Gmail": "เชื่อมต่อ Gmail ของคุณ",
    "so check-in confirmations and attendance reports are sent from your own address.":
        "เพื่อให้อีเมลยืนยันการเช็คชื่อและรายงานการเข้าเรียนส่งจากอีเมลของคุณเอง",
    "Until then, they are sent from the app's address.": "ระหว่างนี้ระบบจะส่งจากอีเมลของแอป",
    "Until then, no emails are sent.": "ระหว่างนี้จะยังไม่มีการส่งอีเมล",
    "Connect Gmail": "เชื่อมต่อ Gmail",
    "Archived sessions": "คาบเรียนที่เก็บถาวร",
    "← Your sessions": "← คาบเรียนของคุณ",
    "Archived ({n})": "เก็บถาวร ({n})",
    "No archived sessions.": "ไม่มีคาบเรียนที่เก็บถาวร",
    "More actions": "ตัวเลือกเพิ่มเติม",
    "Archive": "เก็บถาวร",
    "Unarchive": "นำกลับจากที่เก็บถาวร",
    "Delete": "ลบ",
    "Archiving closes this running session. Continue?": "การเก็บถาวรจะปิดคาบเรียนที่กำลังดำเนินการอยู่ ต้องการดำเนินการต่อหรือไม่",
    "Delete this session and all its check-ins? This cannot be undone.": "ลบคาบเรียนนี้และการเช็คชื่อทั้งหมดหรือไม่ การลบนี้ย้อนกลับไม่ได้",

    # Display
    "Scan with your phone camera to check in": "สแกนด้วยกล้องโทรศัพท์เพื่อเช็คชื่อ",
    "Pause": "หยุดชั่วคราว",
    "Resume": "เปิดต่อ",
    "+ Mid-class check": "+ เช็คชื่อระหว่างคาบ",
    "+ Check-out": "+ เช็คชื่อออก",
    "Full screen": "เต็มจอ",
    "List": "รายชื่อ",
    "Close session": "ปิดคาบเรียน",
    "Live connection": "การเชื่อมต่อสด",
    "Checks in this session": "การเช็คชื่อในคาบนี้",
    "not started": "ยังไม่เริ่ม",
    "open": "เปิดอยู่",
    "paused": "หยุดชั่วคราว",
    "Paused": "หยุดชั่วคราว",
    "No check open": "ไม่มีการเช็คชื่อที่เปิดอยู่",
    "Choose a check above to open it": "เลือกการเช็คชื่อด้านบนเพื่อเปิด",
    "Showing this check": "กำลังแสดงรายการนี้",
    "Click to open this check": "คลิกเพื่อเปิดการเช็คชื่อนี้",
    "Start \"{label}\"?": "เริ่ม \"{label}\" หรือไม่",
    "Reopen \"{label}\"?": "เปิด \"{label}\" อีกครั้งหรือไม่",
    "This closes \"{label}\".": "\"{label}\" จะถูกปิด",
    "Add a mid-class check and open it now?": "เพิ่มการเช็คชื่อระหว่างคาบและเปิดทันทีหรือไม่",
    "Add a check-out and open it now?": "เพิ่มการเช็คชื่อออกและเปิดทันทีหรือไม่",
    "Close this session? Students can no longer check in.": "ปิดคาบเรียนนี้หรือไม่ นักศึกษาจะเช็คชื่อไม่ได้อีก",

    # Report
    "Attendance": "การเข้าเรียน",
    "Back to QR display": "กลับไปหน้าแสดง QR",
    "Download CSV": "ดาวน์โหลด CSV",
    "Email me this list": "ส่งรายชื่อนี้ทางอีเมล",
    "The attendance list is on its way to {email}.": "กำลังส่งรายชื่อผู้เข้าเรียนไปที่ {email}",
    "students in total": "คนทั้งหมด",
    "Name": "ชื่อ",
    "Nobody has checked in yet.": "ยังไม่มีใครเช็คชื่อ",
    "Corrections": "แก้ไขรายชื่อ",
    "student email": "อีเมลนักศึกษา",
    "name (optional)": "ชื่อ (ไม่บังคับ)",
    "Add by hand": "เพิ่มเอง",
    "Remove a check-in": "ลบการเช็คชื่อ",
    "remove": "ลบ",
    "← All sessions": "← คาบเรียนทั้งหมด",

    # Settings
    "Settings saved.": "บันทึกการตั้งค่าแล้ว",
    "Branding": "รูปลักษณ์",
    "Institution name": "ชื่อสถาบัน",
    "e.g. Faculty of Engineering, Example University": "เช่น คณะวิศวกรรมศาสตร์ มหาวิทยาลัยตัวอย่าง",
    "App title": "ชื่อแอป",
    "Accent colour": "สีหลัก",
    "Default language": "ภาษาเริ่มต้น",
    "Used for new visitors and for emails.": "ใช้กับผู้เข้าชมใหม่และอีเมล",
    "Who can use it": "ผู้ใช้งาน",
    "Student email domains": "โดเมนอีเมลนักศึกษา",
    "Only these domains can check in. *.example.edu matches any subdomain. Leave empty to allow any verified email.":
        "เฉพาะโดเมนเหล่านี้ที่เช็คชื่อได้ *.example.edu หมายถึงทุกโดเมนย่อย เว้นว่างไว้เพื่ออนุญาตอีเมลที่ยืนยันแล้วทุกโดเมน",
    "Teacher email domains": "โดเมนอีเมลอาจารย์",
    "Everyone in these domains can create sessions.": "ทุกคนในโดเมนเหล่านี้สร้างคาบเรียนได้",
    "Individual teacher emails": "อีเมลอาจารย์รายบุคคล",
    "Administrators (from ADMIN_EMAILS):": "ผู้ดูแลระบบ (จาก ADMIN_EMAILS):",
    "They are always teachers too.": "ผู้ดูแลระบบเป็นอาจารย์ด้วยเสมอ",
    "none": "ไม่มี",
    "Time zone": "เขตเวลา",
    "QR code changes every (seconds)": "QR code เปลี่ยนทุก (วินาที)",
    "A scanned code stays valid for up to two intervals.": "โค้ดที่สแกนแล้วใช้ได้ไม่เกินสองช่วงเวลา",
    "Email students a confirmation (default for new sessions)": "ส่งอีเมลยืนยันให้นักศึกษา (ค่าเริ่มต้นของคาบใหม่)",
    "Email the teacher the list on close (default for new sessions)": "ส่งรายชื่อให้อาจารย์เมื่อปิดคาบ (ค่าเริ่มต้นของคาบใหม่)",
    "Save settings": "บันทึกการตั้งค่า",
    "Logos": "โลโก้",
    "Shown in the header, on the QR display and in emails (the first PNG/JPEG logo). Up to 4 images, 2 MB each.":
        "แสดงที่ส่วนหัว หน้าแสดง QR และในอีเมล (โลโก้ PNG/JPEG ตัวแรก) ได้สูงสุด 4 รูป รูปละไม่เกิน 2 MB",
    "No logos yet.": "ยังไม่มีโลโก้",
    "Remove": "ลบ",
    "Upload logo": "อัปโหลดโลโก้",
    "Sign-in methods": "วิธีเข้าสู่ระบบ",
    "One-time code by email": "รหัสครั้งเดียวทางอีเมล",
    "Email delivery:": "การส่งอีเมล:",
    "teachers' own Gmail": "Gmail ของอาจารย์แต่ละคน",
    "not configured (messages are only logged)": "ยังไม่ได้ตั้งค่า (บันทึกไว้ใน log เท่านั้น)",
    "These are set in the server's environment.": "ตั้งค่าเหล่านี้ใน environment ของเซิร์ฟเวอร์",

    # Errors and messages
    "Not allowed": "ไม่ได้รับอนุญาต",
    "Not found": "ไม่พบหน้าที่ต้องการ",
    "Something went wrong": "เกิดข้อผิดพลาด",
    "Error": "ข้อผิดพลาด",
    "Session not found.": "ไม่พบคาบเรียน",
    "This page is for teachers. Ask an administrator to add your account.":
        "หน้านี้สำหรับอาจารย์ กรุณาติดต่อผู้ดูแลระบบเพื่อเพิ่มบัญชีของคุณ",
    "Only administrators can change settings.": "เฉพาะผู้ดูแลระบบเท่านั้นที่เปลี่ยนการตั้งค่าได้",
    "Invalid or missing CSRF token. Reload the page and try again.": "แบบฟอร์มหมดอายุ กรุณาโหลดหน้าใหม่แล้วลองอีกครั้ง",
    "QR code expired": "QR code หมดอายุ",
    "This code has changed. Scan the code on the screen again.": "โค้ดนี้เปลี่ยนแล้ว กรุณาสแกนโค้ดบนจออีกครั้ง",
    "Please scan again": "กรุณาสแกนอีกครั้ง",
    "Signing in took too long. Scan the code on the screen again.": "เข้าสู่ระบบนานเกินไป กรุณาสแกนโค้ดบนจออีกครั้ง",
    "QR code not valid": "QR code ใช้ไม่ได้",
    "Unknown sign-in method": "ไม่รู้จักวิธีเข้าสู่ระบบนี้",
    "Sign-in failed": "เข้าสู่ระบบไม่สำเร็จ",
    "Your account did not provide a verified email address.": "บัญชีของคุณไม่มีอีเมลที่ยืนยันแล้ว",
    "Account not allowed": "บัญชีนี้ไม่ได้รับอนุญาต",
    "{email} is not in an allowed email domain. Sign in with your institution account.":
        "{email} ไม่ได้อยู่ในโดเมนอีเมลที่อนุญาต กรุณาเข้าสู่ระบบด้วยบัญชีของสถาบัน",
    "Email codes are disabled": "ปิดการเข้าสู่ระบบด้วยรหัสทางอีเมล",
    "Enter a valid email address.": "กรุณากรอกอีเมลให้ถูกต้อง",
    "Use your institution email ({domains}).": "กรุณาใช้อีเมลของสถาบัน ({domains})",
    "A code was sent a moment ago. Check your inbox.": "ส่งรหัสไปเมื่อสักครู่แล้ว กรุณาตรวจสอบกล่องจดหมาย",
    "That code has expired. Request a new one.": "รหัสหมดอายุแล้ว กรุณาขอรหัสใหม่",
    "Wrong code. Try again.": "รหัสไม่ถูกต้อง กรุณาลองอีกครั้ง",
    "Please enter your name.": "กรุณากรอกชื่อ",
    "Gmail sending is not enabled": "ยังไม่ได้เปิดการส่งอีเมลผ่าน Gmail",
    "Wrong Google account": "บัญชี Google ไม่ถูกต้อง",
    "Choose {email} when Google asks.": "กรุณาเลือก {email} เมื่อ Google ถาม",
    "Gmail not connected": "ยังไม่ได้เชื่อมต่อ Gmail",
    "Google did not grant permission to send email. Try again and tick the Gmail box.":
        "Google ไม่ได้ให้สิทธิ์ส่งอีเมล กรุณาลองใหม่และติ๊กช่อง Gmail",

    "Logo files must be 2 MB or smaller.": "ไฟล์โลโก้ต้องมีขนาดไม่เกิน 2 MB",
    "Logos must be PNG, JPEG, GIF, WebP or SVG images.": "โลโก้ต้องเป็นไฟล์ PNG, JPEG, GIF, WebP หรือ SVG",
    "At most 4 logos. Remove one first.": "มีโลโก้ได้ไม่เกิน 4 รูป กรุณาลบออกก่อน",
    "Unknown time zone.": "ไม่รู้จักเขตเวลานี้",
    "This session is closed.": "คาบเรียนนี้ปิดแล้ว",
    "Unknown phase type.": "ไม่รู้จักประเภทการเช็คชื่อนี้",
    "Unknown phase.": "ไม่พบการเช็คชื่อนี้",

    # Emails
    "{code} is your {app} sign-in code": "{code} คือรหัสเข้าสู่ระบบ {app} ของคุณ",
    "Your sign-in code is {code}": "รหัสเข้าสู่ระบบของคุณคือ {code}",
    "It expires in 10 minutes. If you did not ask for it, ignore this email.":
        "รหัสนี้หมดอายุใน 10 นาที หากคุณไม่ได้ขอรหัสนี้ โปรดเพิกเฉยต่ออีเมลนี้",
    "{phase} confirmed: {title}": "ยืนยัน{phase}: {title}",
    "Attendance report: {title} ({date})": "รายงานการเข้าเรียน: {title} ({date})",
    "Hello {name},": "เรียน {name}",
    "Hello,": "สวัสดีครับ/ค่ะ",
    "Your {phase} for {title} was recorded at {time} ({tz}).": "ระบบบันทึก{phase}วิชา {title} ของคุณแล้ว เวลา {time} ({tz})",
    "If this wasn't you, tell your teacher.": "หากไม่ใช่คุณ กรุณาแจ้งอาจารย์ผู้สอน",
    "Students in total": "จำนวนนักศึกษาทั้งหมด",
    "The full list is attached as a CSV file.": "แนบรายชื่อทั้งหมดเป็นไฟล์ CSV",
    "View it online": "ดูออนไลน์",
}

CATALOGS = {"th": TH}

TH_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
             "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
TH_MONTHS_ABBR = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
                  "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
TH_DAYS = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"]


def normalize(lang: str | None) -> str:
    return lang if lang in LANGUAGES else "en"


def gettext(lang: str, text: str, **params) -> str:
    out = CATALOGS.get(lang, {}).get(text, text)
    return out.format(**params) if params else out


def translator(lang: str):
    return lambda text, **params: gettext(lang, text, **params)


def strftime(dt: datetime, fmt: str, lang: str) -> str:
    """strftime with Thai month and day names and Buddhist-era years for `th`."""
    if lang != "th":
        return dt.strftime(fmt)
    fmt = (fmt.replace("%A", TH_DAYS[dt.weekday()])
              .replace("%B", TH_MONTHS[dt.month - 1])
              .replace("%b", TH_MONTHS_ABBR[dt.month - 1])
              .replace("%Y", str(dt.year + 543)))
    return dt.strftime(fmt)


_MID = re.compile(r"^Mid-class check (\d+)$")


def phase_label(label: str, lang: str) -> str:
    """Phase labels are stored in English; translate them for display."""
    m = _MID.match(label)
    if m:
        return gettext(lang, "Mid-class check {n}", n=m.group(1))
    return gettext(lang, label)

# Strings used by static/display.js; the page embeds their translations.
DISPLAY_STRINGS = [
    "Pause", "Resume", "not started", "open", "paused", "closed", "Paused", "No check open",
    "Choose a check above to open it", "Showing this check", "Click to open this check",
    'Start "{label}"?', 'Reopen "{label}"?', 'This closes "{label}".', "Checked in",
    "Add a mid-class check and open it now?", "Add a check-out and open it now?",
    "Close this session? Students can no longer check in.",
]
