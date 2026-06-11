#!/usr/bin/env python3
"""템플릿 5-1~5-4 (0차+수정집행) 시트의 본표 아래 레거시 블록 제거.

레거시 블록: 재료비 양식 잔재 (#REF! 수식, 단말재/케이블 등 SUMIF 표).
푸터 행('GS네오텍' 포함 행) 이후의 모든 셀 내용을 비운다 (스타일/행 구조 유지).
ZIP/XML 패치 — openpyxl 저장 금지 규칙 준수.
"""
from __future__ import annotations

import io
import unicodedata
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "템플릿.xlsx"

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
M = f"{{{NS_MAIN}}}"
R = f"{{{NS_REL}}}"
P = f"{{{NS_PKG}}}"

TARGET_SHEETS = [
    "5-1. 재료비산출내역", "5-2. 회선비산출내역", "5-3. 소모품비산출내역", "5-4. 수수료산출내역",
    "5-1. 재료비산출내역 (수정집행)", "5-2. 회선비산출내역 (수정집행)",
    "5-3. 소모품비산출내역 (수정집행)", "5-4. 수수료산출내역 (수정집행)",
]

nfc = lambda s: unicodedata.normalize("NFC", s) if s else s


def main():
    z = zipfile.ZipFile(TEMPLATE)
    names = set(z.namelist())

    # sharedStrings (푸터 행 탐지용)
    sst = etree.fromstring(z.read("xl/sharedStrings.xml"))
    strings = []
    for si in sst.findall(f"{M}si"):
        strings.append(nfc("".join(t.text or "" for t in si.iter(f"{M}t"))))

    wb = etree.fromstring(z.read("xl/workbook.xml"))
    rels = etree.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid2t = {r_.get("Id"): r_.get("Target") for r_ in rels.findall(f"{P}Relationship")}
    sheet_files = {}
    for s in wb.find(f"{M}sheets").findall(f"{M}sheet"):
        t = rid2t[s.get(f"{R}id")].lstrip("/")
        sheet_files[nfc(s.get("name"))] = t if t.startswith("xl/") else "xl/" + t

    replaced: dict[str, bytes] = {}
    for sheet_name in TARGET_SHEETS:
        path = sheet_files[sheet_name]
        tree = etree.fromstring(z.read(path))
        sheet_data = tree.find(f"{M}sheetData")

        # 푸터 행 탐지: 'GS네오텍' 문자열을 가진 행 (없으면 스킵)
        footer_row = None
        for row in sheet_data.findall(f"{M}row"):
            for c in row.findall(f"{M}c"):
                if c.get("t") == "s":
                    v = c.find(f"{M}v")
                    if v is not None and v.text and "GS네오텍" in strings[int(v.text)]:
                        footer_row = int(row.get("r"))
                        break
            if footer_row:
                break
        if footer_row is None:
            print(f"  ! {sheet_name}: 푸터 행 미발견 — 스킵")
            continue

        cleared = 0
        for row in sheet_data.findall(f"{M}row"):
            if int(row.get("r")) <= footer_row:
                continue
            for c in row.findall(f"{M}c"):
                had = False
                for tag in ("f", "v", "is"):
                    for el in c.findall(f"{M}{tag}"):
                        c.remove(el)
                        had = True
                if c.get("t"):
                    del c.attrib["t"]
                if had:
                    cleared += 1
        replaced[path] = etree.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=True)
        print(f"  {sheet_name}: 푸터 행 {footer_row}, 이후 {cleared}개 셀 비움")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in z.infolist():
            data = replaced.get(item.filename) or z.read(item.filename)
            zout.writestr(item, data)
    z.close()
    TEMPLATE.write_bytes(buf.getvalue())
    print(f"완료: {TEMPLATE} ({TEMPLATE.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
