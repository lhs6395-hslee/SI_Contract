#!/usr/bin/env python3
"""템플릿.xlsx에 수정집행(차수) 지원을 통합하는 ZIP/XML 패치 스크립트.

수행 내용:
[A] 0차 시트 보정
  - 공통: E127~P127(기간 텍스트), E128~P128(DATEDIF) 수식 복원
  - 5.집행예산산출내역서: F52/G52/I52(수수료 소계), F53/G53/I53(용역수수료 SUMIF) 복원
  - 5-4. 수수료산출내역: QZ 잔재값(Q8/R8/AJ8) 제거, 행8 수식(J8/M8/AL8) 복원
  - 0. 집행계획(갑지): D30 잔재 제거, F18/F20(견적품의 경비/영업이익) 수식,
    G14(매출비율 100%) 수식화, X15~X20 IFERROR
  - 원가투입 기성청구: B6 잔재값 제거, 나누기 셀 IFERROR
[B] (수정집행) 7개 시트 이식 (소스: 퀘이사존 result v0.3)
  - 시트 XML + drawings/vml/comments/printerSettings 복사 (번호 재배정)
  - 수식 캐시(v) 제거, HLOOKUP 범위 공통!$E$8:$P$149 통일 (E5-1=0 → 0차 열 조회 가능)
  - 5-4(수정집행): 데이터행 9~31 수식 세트 복원, 소계행 18/26 재구성,
    D32 라벨 정리, AS32 잔재 제거, G21(갑지) IFERROR
[C] calcChain 제거 + fullCalcOnLoad

규칙: openpyxl 저장 금지(DrawingML 손실), sharedStrings 끝에만 추가, t 속성 유지.
출력: .pipeline/템플릿_patched.xlsx
"""
from __future__ import annotations

import hashlib
import io
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "템플릿.xlsx"
QZ_RESULT = ROOT / "senario" / "퀘이사존" / "result" / "1. (최초) 집행계획서_퀘이사존 운영_v0.3.xlsx"
OUTPUT = ROOT / ".pipeline" / "템플릿_patched.xlsx"

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
M = f"{{{NS_MAIN}}}"
R = f"{{{NS_REL}}}"
P = f"{{{NS_PKG}}}"
CT = f"{{{NS_CT}}}"

SHEET_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
COMMENTS_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml"
DRAWING_CT = "application/vnd.openxmlformats-officedocument.drawing+xml"

REV_SHEETS = [
    "0. 집행계획(갑지) (수정집행)",
    "4. 집행예산집계표 (수정집행)",
    "5.집행예산산출내역서 (수정집행)",
    "5-1. 재료비산출내역 (수정집행)",
    "5-2. 회선비산출내역 (수정집행)",
    "5-3. 소모품비산출내역 (수정집행)",
    "5-4. 수수료산출내역 (수정집행)",
]
# (수정집행) 시트를 끼워 넣을 위치: 대응되는 0차 시트 바로 뒤
COUNTERPART = {n: n.replace(" (수정집행)", "") for n in REV_SHEETS}

nfc = lambda s: unicodedata.normalize("NFC", s) if s else s


def col_to_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def split_ref(ref: str) -> tuple[str, int]:
    m = re.match(r"([A-Z]+)(\d+)", ref)
    return m.group(1), int(m.group(2))


class SheetEditor:
    """워크시트 XML의 셀 단위 편집 (행/셀 순서 유지)."""

    def __init__(self, xml: bytes):
        self.tree = etree.fromstring(xml)
        self.sheet_data = self.tree.find(f"{M}sheetData")
        self.rows = {int(r.get("r")): r for r in self.sheet_data.findall(f"{M}row")}

    def _get_row(self, num: int):
        if num in self.rows:
            return self.rows[num]
        row = etree.Element(f"{M}row")
        row.set("r", str(num))
        following = sorted(k for k in self.rows if k > num)
        if following:
            self.rows[following[0]].addprevious(row)
        else:
            self.sheet_data.append(row)
        self.rows[num] = row
        return row

    def _get_cell(self, ref: str):
        col, rownum = split_ref(ref)
        row = self._get_row(rownum)
        target = col_to_num(col)
        for c in row.findall(f"{M}c"):
            ccol, _ = split_ref(c.get("r"))
            if ccol == col:
                return c
            if col_to_num(ccol) > target:
                cell = etree.Element(f"{M}c")
                cell.set("r", ref)
                c.addprevious(cell)
                return cell
        cell = etree.SubElement(row, f"{M}c")
        cell.set("r", ref)
        return cell

    def set_formula(self, ref: str, formula: str):
        """수식 설정. 기존 캐시(v)/값 제거, t 속성은 수식 결과형에 맞게 제거."""
        cell = self._get_cell(ref)
        for tag in ("f", "v", "is"):
            for el in cell.findall(f"{M}{tag}"):
                cell.remove(el)
        if cell.get("t"):  # 값 셀이었다면 타입 제거 (수식 셀로 전환)
            del cell.attrib["t"]
        f = etree.SubElement(cell, f"{M}f")
        f.text = formula

    def clear_value(self, ref: str):
        """값 셀 비우기 (스타일 유지)."""
        col, rownum = split_ref(ref)
        if rownum not in self.rows:
            return
        for c in self.rows[rownum].findall(f"{M}c"):
            if c.get("r") == ref:
                for tag in ("f", "v", "is"):
                    for el in c.findall(f"{M}{tag}"):
                        c.remove(el)
                if c.get("t"):
                    del c.attrib["t"]
                return

    def get_formula(self, ref: str) -> str | None:
        col, rownum = split_ref(ref)
        if rownum not in self.rows:
            return None
        for c in self.rows[rownum].findall(f"{M}c"):
            if c.get("r") == ref:
                f = c.find(f"{M}f")
                return f.text if f is not None else None
        return None

    def set_shared_string(self, ref: str, sst_index: int):
        cell = self._get_cell(ref)
        for tag in ("f", "v", "is"):
            for el in cell.findall(f"{M}{tag}"):
                cell.remove(el)
        cell.set("t", "s")
        v = etree.SubElement(cell, f"{M}v")
        v.text = str(sst_index)

    def strip_formula_caches(self):
        """f가 있는 셀의 v(캐시)만 제거. 값 셀의 v는 보존."""
        n = 0
        for c in self.sheet_data.iter(f"{M}c"):
            f = c.find(f"{M}f")
            if f is None:
                continue
            for v in c.findall(f"{M}v"):
                c.remove(v)
                n += 1
        return n

    def replace_in_formulas(self, patterns: list[tuple[str, str]]):
        n = 0
        for f in self.sheet_data.iter(f"{M}f"):
            if not f.text:
                continue
            new = f.text
            for pat, repl in patterns:
                new = re.sub(pat, repl, new)
            if new != f.text:
                f.text = new
                n += 1
        return n

    def drop_page_setup_rid(self):
        """printerSettings 미복사 시 pageSetup r:id 제거용 (현재 미사용)."""
        for ps in self.tree.iter(f"{M}pageSetup"):
            if ps.get(f"{R}id"):
                del ps.attrib[f"{R}id"]

    def tobytes(self) -> bytes:
        return etree.tostring(
            self.tree, xml_declaration=True, encoding="UTF-8", standalone=True
        )


def _canon(el) -> bytes:
    """속성 정렬 기반 정규화 직렬화 (스타일 요소 동등성 비교용)."""
    e = etree.Element(el.tag)
    for k in sorted(el.keys()):
        e.set(k, el.get(k))
    for child in el:
        e.append(etree.fromstring(_canon(child)))
    return etree.tostring(e)


class StyleMerger:
    """QZ 워크북의 셀 스타일을 템플릿 styles.xml로 병합하고 s 인덱스를 재매핑.

    cellXfs → (numFmt/font/fill/border/cellStyleXfs) 재귀 find-or-append.
    """

    def __init__(self, tmpl_xml: bytes, src_xml: bytes):
        self.t = etree.fromstring(tmpl_xml)
        self.s = etree.fromstring(src_xml)
        self.modified = False
        self._xf_map: dict[int, int] = {}
        self._part_maps: dict[str, dict[int, int]] = {}
        self._t_index: dict[str, dict[bytes, int]] = {}
        # 템플릿 numFmt: formatCode → id
        self._t_numfmt: dict[str, int] = {}
        nf = self.t.find(f"{M}numFmts")
        if nf is not None:
            for el in nf:
                self._t_numfmt[el.get("formatCode")] = int(el.get("numFmtId"))
        self._s_numfmt: dict[int, str] = {}
        nf = self.s.find(f"{M}numFmts")
        if nf is not None:
            for el in nf:
                self._s_numfmt[int(el.get("numFmtId"))] = el.get("formatCode")

    def _table(self, root, part):
        el = root.find(f"{M}{part}")
        if el is None:
            raise KeyError(part)
        return el

    def _map_numfmt(self, fmt_id: int) -> int:
        if fmt_id < 164 or fmt_id not in self._s_numfmt:
            return fmt_id  # 빌트인
        code = self._s_numfmt[fmt_id]
        if code in self._t_numfmt:
            return self._t_numfmt[code]
        nf = self._table(self.t, "numFmts")
        new_id = max(164, max(self._t_numfmt.values(), default=163)) + 1
        el = etree.SubElement(nf, f"{M}numFmt")
        el.set("numFmtId", str(new_id))
        el.set("formatCode", code)
        nf.set("count", str(len(nf)))
        self._t_numfmt[code] = new_id
        self.modified = True
        return new_id

    def _map_part(self, part: str, idx: int) -> int:
        cache = self._part_maps.setdefault(part, {})
        if idx in cache:
            return cache[idx]
        t_tab = self._table(self.t, part)
        s_tab = self._table(self.s, part)
        if part not in self._t_index:
            self._t_index[part] = {_canon(el): i for i, el in enumerate(t_tab)}
        src_el = s_tab[idx]
        key = _canon(src_el)
        if key in self._t_index[part]:
            cache[idx] = self._t_index[part][key]
            return cache[idx]
        import copy as _copy
        new_el = _copy.deepcopy(src_el)
        t_tab.append(new_el)
        t_tab.set("count", str(len(t_tab)))
        new_idx = len(t_tab) - 1
        self._t_index[part][key] = new_idx
        cache[idx] = new_idx
        self.modified = True
        return new_idx

    def _remap_xf(self, xf_el, is_style_xf: bool):
        """xf 요소의 참조 id들을 템플릿 기준으로 재작성한 사본 반환."""
        import copy as _copy
        el = _copy.deepcopy(xf_el)
        if el.get("numFmtId"):
            el.set("numFmtId", str(self._map_numfmt(int(el.get("numFmtId")))))
        if el.get("fontId"):
            el.set("fontId", str(self._map_part("fonts", int(el.get("fontId")))))
        if el.get("fillId"):
            el.set("fillId", str(self._map_part("fills", int(el.get("fillId")))))
        if el.get("borderId"):
            el.set("borderId", str(self._map_part("borders", int(el.get("borderId")))))
        if not is_style_xf and el.get("xfId"):
            el.set("xfId", str(self._map_style_xf(int(el.get("xfId")))))
        return el

    _style_xf_cache: dict[int, int]

    def _map_style_xf(self, idx: int) -> int:
        cache = self._part_maps.setdefault("_styleXf", {})
        if idx in cache:
            return cache[idx]
        t_tab = self._table(self.t, "cellStyleXfs")
        s_tab = self._table(self.s, "cellStyleXfs")
        remapped = self._remap_xf(s_tab[idx], is_style_xf=True)
        key = _canon(remapped)
        if "_styleXfIdx" not in self._t_index:
            self._t_index["_styleXfIdx"] = {_canon(el): i for i, el in enumerate(t_tab)}
        if key in self._t_index["_styleXfIdx"]:
            cache[idx] = self._t_index["_styleXfIdx"][key]
            return cache[idx]
        t_tab.append(remapped)
        t_tab.set("count", str(len(t_tab)))
        new_idx = len(t_tab) - 1
        # cellStyles 항목도 추가 (orphan cellStyleXf 방지)
        cs = self.t.find(f"{M}cellStyles")
        if cs is not None:
            cse = etree.SubElement(cs, f"{M}cellStyle")
            cse.set("name", f"이식스타일 {new_idx}")
            cse.set("xfId", str(new_idx))
            cs.set("count", str(len(cs)))
        self._t_index["_styleXfIdx"][key] = new_idx
        cache[idx] = new_idx
        self.modified = True
        return new_idx

    def map_cell_xf(self, idx: int) -> int:
        if idx in self._xf_map:
            return self._xf_map[idx]
        t_tab = self._table(self.t, "cellXfs")
        s_tab = self._table(self.s, "cellXfs")
        remapped = self._remap_xf(s_tab[idx], is_style_xf=False)
        key = _canon(remapped)
        if "_cellXfIdx" not in self._t_index:
            self._t_index["_cellXfIdx"] = {_canon(el): i for i, el in enumerate(t_tab)}
        if key in self._t_index["_cellXfIdx"]:
            self._xf_map[idx] = self._t_index["_cellXfIdx"][key]
            return self._xf_map[idx]
        t_tab.append(remapped)
        t_tab.set("count", str(len(t_tab)))
        new_idx = len(t_tab) - 1
        self._t_index["_cellXfIdx"][key] = new_idx
        self._xf_map[idx] = new_idx
        self.modified = True
        return new_idx

    def remap_sheet(self, ed: "SheetEditor") -> int:
        """시트 내 모든 스타일 참조(c/@s, row/@s, col/@style) 재매핑."""
        n = 0
        for c in ed.tree.iter(f"{M}c"):
            if c.get("s"):
                c.set("s", str(self.map_cell_xf(int(c.get("s")))))
                n += 1
        for row in ed.tree.iter(f"{M}row"):
            if row.get("s"):
                row.set("s", str(self.map_cell_xf(int(row.get("s")))))
                n += 1
        for col in ed.tree.iter(f"{M}col"):
            if col.get("style"):
                col.set("style", str(self.map_cell_xf(int(col.get("style")))))
                n += 1
        return n

    def tobytes(self) -> bytes:
        return etree.tostring(self.t, xml_declaration=True, encoding="UTF-8", standalone=True)


def fee_row_formulas(r: int) -> dict[str, str]:
    """5-4(수정집행) 데이터 행 표준 수식 세트 (행 33~47 패턴)."""
    return {
        f"J{r}": f"H{r}*I{r}", f"M{r}": f"K{r}*L{r}", f"P{r}": f"N{r}*O{r}",
        f"S{r}": f"Q{r}*R{r}", f"T{r}": f"S{r}-P{r}", f"W{r}": f"U{r}*V{r}",
        f"Z{r}": f"X{r}*Y{r}", f"AC{r}": f"AA{r}*AB{r}", f"AF{r}": f"AD{r}*AE{r}",
        f"AI{r}": f"AG{r}*AH{r}", f"AL{r}": f"AJ{r}*AK{r}",
        f"AM{r}": f"AA{r}+AD{r}+AG{r}+AJ{r}", f"AN{r}": f"AC{r}+AF{r}+AI{r}+AL{r}",
        f"AO{r}": f"AM{r}+X{r}+U{r}", f"AP{r}": f"AN{r}+Z{r}+W{r}",
        f"AS{r}": f"AP{r}-S{r}",
    }


def fee_subtotal_formulas(r: int, lo: int, hi: int) -> dict[str, str]:
    """5-4(수정집행) 소계 행 수식 (행 32 패턴 + 당초/집행 당초 보강)."""
    cols = ["J", "M", "P", "S", "T", "W", "Z", "AC", "AF", "AI", "AL"]
    out = {f"{c}{r}": f"SUM({c}{lo}:{c}{hi})" for c in cols}
    out[f"AN{r}"] = f"AC{r}+AF{r}+AI{r}+AL{r}"
    out[f"AP{r}"] = f"AN{r}+Z{r}+W{r}"
    out[f"AS{r}"] = f"AP{r}-S{r}"
    return out


def main():
    src_t = zipfile.ZipFile(TEMPLATE)
    src_q = zipfile.ZipFile(QZ_RESULT)

    # ── 시트명 → 파일 매핑 (양쪽) ─────────────────────────────
    def sheet_files(z: zipfile.ZipFile) -> dict[str, str]:
        wb = etree.fromstring(z.read("xl/workbook.xml"))
        rels = etree.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid2t = {r_.get("Id"): r_.get("Target") for r_ in rels.findall(f"{P}Relationship")}
        out = {}
        for s in wb.find(f"{M}sheets").findall(f"{M}sheet"):
            t = rid2t[s.get(f"{R}id")].lstrip("/")
            out[nfc(s.get("name"))] = t if t.startswith("xl/") else "xl/" + t
        return out

    t_sheets = sheet_files(src_t)
    q_sheets = sheet_files(src_q)

    # ── sharedStrings 병합기 ──
    # 복사한 시트의 t="s" 셀은 QZ sst 인덱스를 가리키므로 템플릿 sst 기준으로 재매핑 필수.
    # 규칙: 원본 sst 유지, 새 항목은 끝에만 추가.
    sst = etree.fromstring(src_t.read("xl/sharedStrings.xml"))
    sst_q = etree.fromstring(src_q.read("xl/sharedStrings.xml"))

    def _si_key(si) -> bytes:
        return etree.tostring(si)  # 서식 run 포함 동등성

    t_sst_index: dict[bytes, int] = {_si_key(si): i for i, si in enumerate(sst.findall(f"{M}si"))}
    q_sst_items = sst_q.findall(f"{M}si")
    # 주의: 템플릿 sst에 중복 항목이 있으면 dict 크기 < 실제 si 수 — 위치 카운터를 따로 유지
    sst_state = {"modified": False, "count": len(sst.findall(f"{M}si"))}

    def merge_sst(q_idx: int) -> int:
        key = _si_key(q_sst_items[q_idx])
        if key in t_sst_index:
            return t_sst_index[key]
        import copy as _copy
        sst.append(_copy.deepcopy(q_sst_items[q_idx]))
        new_idx = sst_state["count"]  # 실제 si 위치
        sst_state["count"] += 1
        t_sst_index[key] = new_idx
        sst_state["modified"] = True
        return new_idx

    def remap_shared_strings(ed: "SheetEditor") -> int:
        n = 0
        for c in ed.sheet_data.iter(f"{M}c"):
            if c.get("t") != "s":
                continue
            v = c.find(f"{M}v")
            if v is None or not v.text:
                continue
            v.text = str(merge_sst(int(v.text)))
            n += 1
        return n

    def _ensure_template_string(text: str) -> int:
        for i, si in enumerate(sst.findall(f"{M}si")):
            ts = si.findall(f"{M}t")
            if len(ts) == 1 and nfc(ts[0].text or "") == text:
                return i
        si = etree.SubElement(sst, f"{M}si")
        t = etree.SubElement(si, f"{M}t")
        t.text = text
        sst_state["modified"] = True
        new_idx = sst_state["count"]
        sst_state["count"] += 1
        t_sst_index[_si_key(si)] = new_idx
        return new_idx

    subtotal_idx = _ensure_template_string("소계")

    # ════════════════════════════════════════════════════════
    # [A] 0차 시트 보정
    # ════════════════════════════════════════════════════════
    patched: dict[str, bytes] = {}

    # A-1. 공통: E~P 127/128
    ed = SheetEditor(src_t.read(t_sheets["공통"]))
    for col in "EFGHIJKLMNOP":
        ed.set_formula(f"{col}127", f'TEXT({col}125,"yyyy-mm-dd")& " ~ "& TEXT({col}126,"yyyy-mm-dd")')
        ed.set_formula(f"{col}128", f'DATEDIF({col}125,{col}126,"d")')
    patched[t_sheets["공통"]] = ed.tobytes()
    print("[A-1] 공통: E~P127/128 수식 24개 복원")

    # A-2. 산출내역서: F/G/I 52,53
    ed = SheetEditor(src_t.read(t_sheets["5.집행예산산출내역서"]))
    q54 = "'5-4. 수수료산출내역'"
    for col in "FGI":
        ed.set_formula(f"{col}52", f"SUM({col}53:{col}54)")
    ed.set_formula("F53", f"SUMIF({q54}!$D:$D,1,{q54}!$J:$J)")
    ed.set_formula("G53", f"SUMIF({q54}!$D:$D,1,{q54}!$M:$M)")
    ed.set_formula("I53", f"SUMIF({q54}!$D:$D,1,{q54}!$S:$S)")
    patched[t_sheets["5.집행예산산출내역서"]] = ed.tobytes()
    print("[A-2] 산출내역서: F/G/I 52~53 수수료 수식 6개 복원")

    # A-3. 5-4: 잔재 제거 + 행8 수식 보강
    ed = SheetEditor(src_t.read(t_sheets["5-4. 수수료산출내역"]))
    for ref in ("Q8", "R8", "AJ8"):
        ed.clear_value(ref)
    ed.set_formula("J8", "H8*I8")
    ed.set_formula("M8", "K8*L8")
    ed.set_formula("AL8", "AI8-M8")
    patched[t_sheets["5-4. 수수료산출내역"]] = ed.tobytes()
    print("[A-3] 5-4: Q8/R8/AJ8 잔재 제거, J8/M8/AL8 수식 복원")

    # A-4. 갑지: 잔재 제거 + 수식 보강
    ed = SheetEditor(src_t.read(t_sheets["0. 집행계획(갑지)"]))
    ed.clear_value("D30")  # QZ 특기사항 잔재
    ed.set_formula("F18", "공통!N4")
    ed.set_formula("F20", "공통!P4")
    ed.set_formula("G14", "IFERROR((F14/F14*100),0)")
    for row in range(15, 21):
        cur = ed.get_formula(f"X{row}")
        if cur and "IFERROR" not in cur:
            ed.set_formula(f"X{row}", f"IFERROR({cur},0)")
    patched[t_sheets["0. 집행계획(갑지)"]] = ed.tobytes()
    print("[A-4] 갑지: D30 잔재 제거, F18/F20/G14 수식, X15~X20 IFERROR")

    # A-5. 원가투입: B6 잔재 + IFERROR
    ed = SheetEditor(src_t.read(t_sheets["원가투입 기성청구"]))
    ed.clear_value("B6")
    for ref in ("C21", "D21", "E21", "C22", "D22", "E22",
                "C27", "D27", "E27", "C31", "D31", "E31"):
        cur = ed.get_formula(ref)
        if cur and "IFERROR" not in cur:
            ed.set_formula(ref, f"IFERROR({cur},0)")
    patched[t_sheets["원가투입 기성청구"]] = ed.tobytes()
    print("[A-5] 원가투입: B6 잔재 제거, 투입/청구/수금율 IFERROR")

    # ════════════════════════════════════════════════════════
    # [B] (수정집행) 시트 7개 이식
    # ════════════════════════════════════════════════════════
    t_names = set(src_t.namelist())
    merger = StyleMerger(src_t.read("xl/styles.xml"), src_q.read("xl/styles.xml"))

    def next_num(pattern: str) -> int:
        mx = 0
        for n in t_names:
            mm = re.match(pattern, n)
            if mm:
                mx = max(mx, int(mm.group(1)))
        return mx + 1

    next_sheet = next_num(r"xl/worksheets/sheet(\d+)\.xml")
    next_drawing = next_num(r"xl/drawings/drawing(\d+)\.xml")
    next_vml = next_num(r"xl/drawings/vmlDrawing(\d+)\.vml")
    next_comments = next_num(r"xl/comments(\d+)\.xml")
    next_printer = next_num(r"xl/printerSettings/printerSettings(\d+)\.bin")
    next_media = next_num(r"xl/media/image(\d+)\.\w+")

    # 템플릿 media 해시 (중복 이미지 재사용)
    media_hash: dict[str, str] = {}
    for n in t_names:
        if n.startswith("xl/media/"):
            media_hash[hashlib.sha256(src_t.read(n)).hexdigest()] = n

    new_files: dict[str, bytes] = {}   # 새로 추가할 파일들
    new_sheet_entries = []             # (name, file, hidden)

    hlookup_patterns = [
        (r"공통!\$?F\$?8:\$?P\$?1(28|34|49)", "공통!$E$8:$P$149"),
    ]

    def copy_media_for_drawing(drawing_rels_xml: bytes) -> bytes:
        """드로잉 rels의 media 참조를 템플릿 기준으로 재배정."""
        nonlocal next_media
        tree = etree.fromstring(drawing_rels_xml)
        for rel in tree.findall(f"{P}Relationship"):
            tgt = rel.get("Target")  # ../media/imageN.png
            if "media/" not in tgt:
                continue
            src_path = "xl/media/" + tgt.split("media/")[-1]
            data = src_q.read(src_path)
            h = hashlib.sha256(data).hexdigest()
            if h in media_hash:
                new_path = media_hash[h]
            else:
                ext = src_path.rsplit(".", 1)[-1]
                new_path = f"xl/media/image{next_media}.{ext}"
                next_media += 1
                new_files[new_path] = data
                media_hash[h] = new_path
            rel.set("Target", "../media/" + new_path.split("/")[-1])
        return etree.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=True)

    for sheet_name in REV_SHEETS:
        q_file = q_sheets[sheet_name]
        ed = SheetEditor(src_q.read(q_file))
        n_cache = ed.strip_formula_caches()
        n_hl = ed.replace_in_formulas(hlookup_patterns)
        n_styles = merger.remap_sheet(ed)
        n_strings = remap_shared_strings(ed)

        if sheet_name == "5-4. 수수료산출내역 (수정집행)":
            # 데이터 행 수식 세트 복원 (소계행 18/26 제외)
            for r_ in list(range(9, 18)) + list(range(19, 26)) + list(range(27, 32)):
                for ref, f_ in fee_row_formulas(r_).items():
                    ed.set_formula(ref, f_)
            # 소계행 18/26 재구성, 32 보강
            for ref, f_ in fee_subtotal_formulas(18, 9, 17).items():
                ed.set_formula(ref, f_)
            for ref, f_ in fee_subtotal_formulas(26, 19, 25).items():
                ed.set_formula(ref, f_)
            for c in ("J", "P", "W"):  # 행32 누락분 보강
                ed.set_formula(f"{c}32", f"SUM({c}27:{c}31)")
            ed.set_shared_string("D18", subtotal_idx)
            ed.set_shared_string("D26", subtotal_idx)
            ed.set_shared_string("D32", subtotal_idx)  # "소계 (수정 2차)" → "소계"
            ed.clear_value("AS32")  # 올리브트리 메모 잔재
            print(f"[B] {sheet_name}: 데이터행 21개 수식 복원 + 소계행 18/26/32 정비")
        if sheet_name == "0. 집행계획(갑지) (수정집행)":
            ed.set_formula("G21", "IFERROR((F21/F21*100),0)")

        # 시트 종속 리소스 복사
        q_rels_path = q_file.replace("worksheets/", "worksheets/_rels/") + ".rels"
        rels_out = None
        if q_rels_path in src_q.namelist():
            rels_tree = etree.fromstring(src_q.read(q_rels_path))
            for rel in rels_tree.findall(f"{P}Relationship"):
                typ = rel.get("Type").rsplit("/", 1)[-1]
                tgt = rel.get("Target")
                src_path = "xl/" + tgt.replace("../", "")
                if typ == "drawing":
                    new_path = f"xl/drawings/drawing{next_drawing}.xml"
                    next_drawing += 1
                    new_files[new_path] = src_q.read(src_path)
                    # 드로잉 자체 rels (media)
                    dr = src_path.replace("drawings/", "drawings/_rels/") + ".rels"
                    if dr in src_q.namelist():
                        new_files[new_path.replace("drawings/", "drawings/_rels/") + ".rels"] = \
                            copy_media_for_drawing(src_q.read(dr))
                elif typ == "vmlDrawing":
                    new_path = f"xl/drawings/vmlDrawing{next_vml}.vml"
                    next_vml += 1
                    new_files[new_path] = src_q.read(src_path)
                elif typ == "comments":
                    new_path = f"xl/comments{next_comments}.xml"
                    next_comments += 1
                    new_files[new_path] = src_q.read(src_path)
                elif typ == "printerSettings":
                    new_path = f"xl/printerSettings/printerSettings{next_printer}.bin"
                    next_printer += 1
                    new_files[new_path] = src_q.read(src_path)
                else:
                    continue
                rel.set("Target", "../" + new_path[3:] if not new_path.startswith("xl/worksheets") else new_path)
                # worksheets 기준 상대경로
                rel.set("Target", {
                    "drawing": f"../drawings/{new_path.split('/')[-1]}",
                    "vmlDrawing": f"../drawings/{new_path.split('/')[-1]}",
                    "comments": f"../{new_path.split('/')[-1]}",
                    "printerSettings": f"../printerSettings/{new_path.split('/')[-1]}",
                }[typ])
            rels_out = etree.tostring(rels_tree, xml_declaration=True, encoding="UTF-8", standalone=True)

        sheet_path = f"xl/worksheets/sheet{next_sheet}.xml"
        next_sheet += 1
        new_files[sheet_path] = ed.tobytes()
        if rels_out is not None:
            new_files[sheet_path.replace("worksheets/", "worksheets/_rels/") + ".rels"] = rels_out
        new_sheet_entries.append((sheet_name, sheet_path))
        print(f"[B] {sheet_name}: 캐시 {n_cache}, HLOOKUP {n_hl}, 스타일 {n_styles}, 문자열 {n_strings} → {sheet_path}")

    # ════════════════════════════════════════════════════════
    # [C] workbook.xml / rels / Content_Types / calcChain
    # ════════════════════════════════════════════════════════
    wb_tree = etree.fromstring(src_t.read("xl/workbook.xml"))
    sheets_el = wb_tree.find(f"{M}sheets")
    rels_tree = etree.fromstring(src_t.read("xl/_rels/workbook.xml.rels"))
    ct_tree = etree.fromstring(src_t.read("[Content_Types].xml"))

    max_sid = max(int(s.get("sheetId")) for s in sheets_el.findall(f"{M}sheet"))
    max_rid = max(
        int(m_.group(1))
        for r_ in rels_tree.findall(f"{P}Relationship")
        if (m_ := re.match(r"rId(\d+)", r_.get("Id")))
    )

    # 주의: definedNames의 localSheetId가 시트 '순서 인덱스' 기반이므로
    # 기존 순서를 깨지 않도록 반드시 끝에 추가한다 (중간 삽입 금지).
    for sheet_name, sheet_path in new_sheet_entries:
        max_sid += 1
        max_rid += 1
        el = etree.SubElement(sheets_el, f"{M}sheet")
        el.set("name", sheet_name)
        el.set("sheetId", str(max_sid))
        el.set("state", "hidden")
        el.set(f"{R}id", f"rId{max_rid}")
        rel = etree.SubElement(rels_tree, f"{P}Relationship")
        rel.set("Id", f"rId{max_rid}")
        rel.set("Type", f"{NS_REL}/worksheet")
        rel.set("Target", sheet_path[3:])  # 'worksheets/sheetN.xml'

    # Content_Types: 새 시트/코멘트/드로잉 Override (bin/vml/png은 Default 커버)
    for path in list(new_files) + []:
        if path.endswith(".rels") or path.endswith(".bin") or path.endswith(".vml"):
            continue
        if "/media/" in path:
            continue
        ctype = SHEET_CT if "/worksheets/" in path else (
            COMMENTS_CT if "/comments" in path.split("/")[-1] or path.startswith("xl/comments")
            else DRAWING_CT if "/drawings/" in path else None
        )
        if ctype is None:
            continue
        ov = etree.SubElement(ct_tree, f"{CT}Override")
        ov.set("PartName", "/" + path)
        ov.set("ContentType", ctype)

    # calcChain 제거 (3곳) + fullCalcOnLoad
    drop_calc = "xl/calcChain.xml" in t_names
    if drop_calc:
        for ov in ct_tree.findall(f"{CT}Override"):
            if ov.get("PartName") == "/xl/calcChain.xml":
                ct_tree.remove(ov)
        for r_ in rels_tree.findall(f"{P}Relationship"):
            if r_.get("Target") == "calcChain.xml":
                rels_tree.remove(r_)
    calc_pr = wb_tree.find(f"{M}calcPr")
    if calc_pr is None:
        calc_pr = etree.SubElement(wb_tree, f"{M}calcPr")
    calc_pr.set("fullCalcOnLoad", "1")

    # ════════════════════════════════════════════════════════
    # 출력 ZIP 조립
    # ════════════════════════════════════════════════════════
    replaced = {
        "xl/workbook.xml": etree.tostring(wb_tree, xml_declaration=True, encoding="UTF-8", standalone=True),
        "xl/_rels/workbook.xml.rels": etree.tostring(rels_tree, xml_declaration=True, encoding="UTF-8", standalone=True),
        "[Content_Types].xml": etree.tostring(ct_tree, xml_declaration=True, encoding="UTF-8", standalone=True),
        **patched,
    }
    if sst_state["modified"]:
        n_items = len(sst.findall(f"{M}si"))
        sst.set("count", str(n_items))
        sst.set("uniqueCount", str(n_items))
        replaced["xl/sharedStrings.xml"] = etree.tostring(
            sst, xml_declaration=True, encoding="UTF-8", standalone=True)
        print(f"  sharedStrings 병합: {n_items}개 항목")
    if merger.modified:
        replaced["xl/styles.xml"] = merger.tobytes()
        print(f"  styles.xml 병합: cellXfs {len(merger.t.find(f'{M}cellXfs'))}개")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in src_t.infolist():
            if item.filename == "xl/calcChain.xml" and drop_calc:
                continue
            data = replaced.pop(item.filename, None)
            if data is None:
                data = src_t.read(item.filename)
            zout.writestr(item, data)
        for path, data in replaced.items():
            zout.writestr(path, data)
        for path, data in new_files.items():
            zout.writestr(path, data)
    OUTPUT.write_bytes(buf.getvalue())
    print(f"\n완료: {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
    print(f"  새 파일 {len(new_files)}개, 교체 {len(patched) + 3}개, calcChain 제거={drop_calc}")


if __name__ == "__main__":
    sys.exit(main())
