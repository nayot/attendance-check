"""Every string the UI shows must have a Thai translation."""

import ast
import re
from datetime import datetime
from pathlib import Path

from app import i18n

APP = Path(__file__).parent.parent / "app"
# Keyword arguments and calls whose string values are shown to users.
UI_KEYWORDS = {"title", "text", "error", "info"}
UI_CALLS = {"_", "gettext", "HTTPException", "CheckInResult"}


def template_strings():
    pattern = re.compile(r"""_\(\s*(["'])((?:\\.|(?!\1).)*)\1""")
    for path in (APP / "templates").rglob("*.*"):
        for m in pattern.finditer(path.read_text()):
            yield path.name, m.group(2).replace('\\"', '"').replace("\\'", "'")


def python_strings():
    for path in APP.glob("*.py"):
        if path.name == "i18n.py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            args = [*node.args] if name in UI_CALLS else []
            args += [k.value for k in node.keywords if k.arg in UI_KEYWORDS]
            for a in args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and re.search("[A-Za-z]{2}", a.value):
                    if name == "gettext" and a is node.args[0]:
                        continue  # the language argument
                    yield path.name, a.value


def test_all_ui_strings_translated():
    found = list(template_strings()) + list(python_strings()) + [("display.js", s) for s in i18n.DISPLAY_STRINGS]
    missing = sorted({f"{where}: {s}" for where, s in found if s not in i18n.TH})
    assert not missing, "Missing Thai translations:\n" + "\n".join(missing)


def test_placeholders_match():
    for en, th in i18n.TH.items():
        assert set(re.findall(r"\{(\w+)\}", en)) == set(re.findall(r"\{(\w+)\}", th)), en


def test_thai_dates_and_phase_labels():
    dt = datetime(2026, 10, 12, 9, 5)
    assert i18n.strftime(dt, "%A %d %B %Y, %H:%M", "th") == "วันจันทร์ 12 ตุลาคม 2569, 09:05"
    assert i18n.strftime(dt, "%d %b %Y", "en") == "12 Oct 2026"
    assert i18n.phase_label("Mid-class check 2", "th") == "เช็คชื่อระหว่างคาบ 2"
    assert i18n.phase_label("Check-out", "th") == "เช็คชื่อออก"
