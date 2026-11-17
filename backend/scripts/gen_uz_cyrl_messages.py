"""frontend/messages/uz.json → uz-Cyrl.json (o'zbek kirill UI) — latin.jaybi.uz dvigateli bilan.

ICU tuzilmasi saqlanadi: `{arg}`, `{n, number}` tegilmaydi; `{n, plural|select|selectordinal, key {…}}` ichidagi
matnlar o'giriladi, kalitlar (one, other, =0 …) qoladi; `<tag>` va `<code>…</code>`, URL, qisqartmalar lotinda
(`app.services.i18n.text.uz_to_cyrillic` qoidalari). Til nomlari (`locale.*`) o'z yozuvida qoladi.

    python3 backend/scripts/gen_uz_cyrl_messages.py           # faylni yozadi
    python3 backend/scripts/gen_uz_cyrl_messages.py --check   # eskirgan bo'lsa exit 1 (uz.json o'zgargandan keyin)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.i18n.text import uz_to_cyrillic  # noqa: E402

SRC = ROOT / "frontend" / "messages" / "uz.json"
DST = ROOT / "frontend" / "messages" / "uz-Cyrl.json"
PRESERVE = {"locale.uz", "locale.ru", "locale.en", "locale.uz-Cyrl"}  # til nomlari — o'z yozuvida
BRANCHING = {"plural", "select", "selectordinal"}


def _match(s: str, i: int) -> int:
    """s[i] == '{' → mos '}' indeksi."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError(f"yopilmagan qavs: {s!r}")


def convert_message(s: str) -> str:
    out: list[str] = []
    buf = ""
    i = 0
    while i < len(s):
        if s[i] == "{":
            out.append(uz_to_cyrillic(buf))
            buf = ""
            j = _match(s, i)
            out.append(_convert_argument(s[i + 1:j]))
            i = j + 1
        else:
            buf += s[i]
            i += 1
    out.append(uz_to_cyrillic(buf))
    return "".join(out)


def _convert_argument(inner: str) -> str:
    parts = inner.split(",", 2)
    if len(parts) < 3 or parts[1].strip() not in BRANCHING:
        return "{" + inner + "}"  # {name}, {n, number}, {d, date, short}
    name, kind, rest = parts
    out: list[str] = []
    i = 0
    while i < len(rest):  # "one {…} other {…}" — kalitlar va bo'shliqlar o'zgarmaydi
        if rest[i] == "{":
            j = _match(rest, i)
            out.append("{" + convert_message(rest[i + 1:j]) + "}")
            i = j + 1
        else:
            out.append(rest[i])
            i += 1
    return "{" + name + "," + kind + "," + "".join(out) + "}"


def convert_tree(node, path: str = ""):
    if isinstance(node, dict):
        return {k: convert_tree(v, f"{path}.{k}" if path else k) for k, v in node.items()}
    if isinstance(node, str):
        return node if path in PRESERVE else convert_message(node)
    return node


def render() -> str:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    return json.dumps(convert_tree(data), ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if not DST.exists() or DST.read_text(encoding="utf-8") != text:
            print(f"{DST.relative_to(ROOT)} eskirgan — qayta yarating: python3 backend/scripts/gen_uz_cyrl_messages.py")
            return 1
        print(f"{DST.relative_to(ROOT)} dolzarb")
        return 0
    DST.write_text(text, encoding="utf-8")
    print(f"yozildi: {DST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
