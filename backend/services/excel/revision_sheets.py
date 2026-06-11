"""수정집행 시트 관리 — 차수별 시트 복사, HLOOKUP 고정, 숨김 처리.

차수 발생 시 수행 작업:
1. 템플릿의 수정집행 7개 시트를 "(N차)" suffix로 복사
2. 복사된 시트 내 공통!E5 참조를 고정 숫자로 교체
3. 이전 차수 시트들을 숨김 처리
4. 공통 시트 해당 열에 집계표 참조 수식 삽입 (common_sheet.py에서 처리)
"""

from __future__ import annotations

import copy
import io
import re
import zipfile
from pathlib import Path

from lxml import etree

# 수정집행 시트 세트: (수정집행) suffix 버전 (복사 소스)
_REV_SHEET_TEMPLATE_NAMES = [
    "0. 집행계획(갑지) (수정집행)",
    "4. 집행예산집계표 (수정집행)",
    "5.집행예산산출내역서 (수정집행)",
    "5-1. 재료비산출내역 (수정집행)",
    "5-2. 회선비산출내역 (수정집행)",
    "5-3. 소모품비산출내역 (수정집행)",
    "5-4. 수수료산출내역 (수정집행)",
]

# 0차 역할을 하는 원본 시트 이름 → rename 대상 (suffix 없는 원본)
_ORIGINAL_SHEET_NAMES = [
    "0. 집행계획(갑지)",
    "4. 집행예산집계표",
    "5.집행예산산출내역서",
    "5-1. 재료비산출내역",
    "5-2. 회선비산출내역",
    "5-3. 소모품비산출내역",
    "5-4. 수수료산출내역",
]

_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"

_SHEET_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
_SHEET_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"


def _revision_sheet_name(template_name: str, revision: int) -> str:
    """'X (수정집행)' -> 'X (N차)'"""
    return template_name.replace("(수정집행)", f"({revision}차)")


def _replace_e5_in_formula(formula: str, revision: int) -> str:
    """수식 내 공통!E5 → 고정 숫자로 교체.

    공통!E5-1 → (revision-1)
    공통!E5   → revision
    """
    # 공통!E5-1 패턴 먼저 (더 긴 패턴 우선)
    result = re.sub(
        r'공통!E5\s*-\s*1',
        str(revision - 1),
        formula
    )
    # 나머지 공통!E5 (단독 혹은 다른 컨텍스트)
    result = re.sub(
        r'공통!E5(?![\w])',
        str(revision),
        result
    )
    return result


def _patch_sheet_refs_to_zero(xml_bytes: bytes) -> bytes:
    """원본 시트 XML에서 다른 원본 시트 참조를 (0차) suffix로 교체.

    예: '5.집행예산산출내역서'!G8 → '5.집행예산산출내역서 (0차)'!G8
    원본 시트들이 (0차)로 rename될 때 내부 수식도 함께 업데이트.
    XML 내 시트명이 엔티티 인코딩될 수 있으므로 lxml으로 파싱 후 수식 텍스트 교체.
    """
    tree = etree.fromstring(xml_bytes)
    ns = {'ns': _NS_MAIN}

    modified = False
    for c in tree.findall('.//ns:c', ns):
        f = c.find('ns:f', ns)
        if f is not None and f.text:
            new_formula = f.text
            for orig_name in _ORIGINAL_SHEET_NAMES:
                # '시트명'! 패턴
                old_ref = f"'{orig_name}'!"
                new_ref = f"'{orig_name} (0차)'!"
                if old_ref in new_formula:
                    new_formula = new_formula.replace(old_ref, new_ref)
                    modified = True
                # 따옴표 없는 패턴 (공백 없는 시트명)
                if ' ' not in orig_name:
                    if f"{orig_name}!" in new_formula:
                        new_formula = new_formula.replace(f"{orig_name}!", new_ref)
                        modified = True
            if new_formula != f.text:
                f.text = new_formula

    if not modified:
        return xml_bytes
    return etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)


def _patch_sheet_xml(xml_bytes: bytes, revision: int) -> bytes:
    """시트 XML에서 공통!E5 참조 및 (수정집행) 시트 참조를 (N차)로 교체."""
    tree = etree.fromstring(xml_bytes)
    ns = {'ns': _NS_MAIN}

    modified = False
    for c in tree.findall('.//ns:c', ns):
        f = c.find('ns:f', ns)
        if f is None or not f.text:
            continue
        new_formula = f.text

        # 공통!E5 → 고정 숫자
        if '공통' in new_formula and 'E5' in new_formula:
            new_formula = _replace_e5_in_formula(new_formula, revision)

        # '시트명 (수정집행)'! → '시트명 (N차)'!
        for tmpl_name in _REV_SHEET_TEMPLATE_NAMES:
            old_ref = f"'{tmpl_name}'!"
            new_ref = f"'{_revision_sheet_name(tmpl_name, revision)}'!"
            if old_ref in new_formula:
                new_formula = new_formula.replace(old_ref, new_ref)

        # 원본(0차) 시트 참조 → '(0차)' rename 반영
        # 예: 갑지(수정집행) F21~F27의 '0. 집행계획(갑지)'!F14~F20 (수주손익)
        for orig_name in _ORIGINAL_SHEET_NAMES:
            old_ref = f"'{orig_name}'!"
            new_ref = f"'{orig_name} (0차)'!"
            if old_ref in new_formula:
                new_formula = new_formula.replace(old_ref, new_ref)

        if new_formula != f.text:
            f.text = new_formula
            modified = True

    if not modified:
        return xml_bytes
    return etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)


def apply_revision_sheets(
    template_path: Path,
    output_path: Path,
    all_revisions: list[int],
) -> None:
    """템플릿 xlsx에 차수별 수정집행 시트를 추가해 output_path에 저장.

    all_revisions: 이전 차수 포함 현재 차수까지 오름차순 리스트. 예: [1], [1,2]
    0차(기본)는 포함하지 않음 — 0차 시트는 원본 그대로 유지.

    수행 내용:
    - all_revisions의 각 차수에 대해 "(N차)" suffix 시트 7개 추가
    - 각 시트 XML에서 공통!E5 → 고정 숫자로 교체
    - 최신 차수가 아닌 차수 시트들은 숨김 처리
    - 템플릿의 "(수정집행)" 원본 시트들은 숨김 처리
    """
    if not all_revisions:
        # 0차만 있으면 수정집행 시트 불필요 — 그냥 복사
        import shutil
        shutil.copy2(template_path, output_path)
        return

    latest_revision = max(all_revisions)

    with zipfile.ZipFile(template_path, 'r') as zin:
        all_names = set(zin.namelist())

        # workbook.xml 파싱
        wb_xml = zin.read('xl/workbook.xml')
        wb_tree = etree.fromstring(wb_xml)
        wb_ns = _NS_MAIN
        sheets_el = wb_tree.find(f'{{{wb_ns}}}sheets')

        # rels 파싱
        rels_xml = zin.read('xl/_rels/workbook.xml.rels')
        rels_tree = etree.fromstring(rels_xml)
        pkg_ns = _NS_PKG_REL

        # ContentTypes 파싱
        ct_xml = zin.read('[Content_Types].xml')
        ct_tree = etree.fromstring(ct_xml)

        # 현재 최대 sheetId, rId 계산
        max_sheet_id = max(
            int(s.get('sheetId', 0))
            for s in sheets_el.findall(f'{{{wb_ns}}}sheet')
        )
        existing_rids = {
            r.get('Id') for r in rels_tree.findall(f'{{{pkg_ns}}}Relationship')
        }
        max_rid_num = 0
        for rid in existing_rids:
            m = re.match(r'rId(\d+)', rid or '')
            if m:
                max_rid_num = max(max_rid_num, int(m.group(1)))

        # 현재 최대 sheet 파일 번호
        max_sheet_file_num = 0
        for name in all_names:
            m = re.match(r'xl/worksheets/sheet(\d+)\.xml', name)
            if m:
                max_sheet_file_num = max(max_sheet_file_num, int(m.group(1)))

        # 템플릿 수정집행 시트 정보 수집
        template_sheet_info: dict[str, dict] = {}
        for s in sheets_el.findall(f'{{{wb_ns}}}sheet'):
            sname = s.get('name', '')
            if sname in _REV_SHEET_TEMPLATE_NAMES:
                rid = s.get(f'{{{_NS_REL}}}id')
                rel_el = rels_tree.find(f'{{{pkg_ns}}}Relationship[@Id="{rid}"]')
                if rel_el is not None:
                    template_sheet_info[sname] = {
                        'rid': rid,
                        'file': rel_el.get('Target'),  # e.g. worksheets/sheet16.xml
                        'sheet_id': s.get('sheetId'),
                    }

        # 새로 추가할 시트들 계획
        new_sheets: list[dict] = []
        counter_sheet_id = max_sheet_id + 1
        counter_rid_num = max_rid_num + 1
        counter_file_num = max_sheet_file_num + 1

        for revision in sorted(all_revisions):
            for tmpl_name in _REV_SHEET_TEMPLATE_NAMES:
                if tmpl_name not in template_sheet_info:
                    continue
                info = template_sheet_info[tmpl_name]
                new_name = _revision_sheet_name(tmpl_name, revision)
                new_rid = f'rId{counter_rid_num}'
                new_file = f'worksheets/sheet{counter_file_num}.xml'
                is_visible = (revision == latest_revision)
                new_sheets.append({
                    'name': new_name,
                    'revision': revision,
                    'source_file': info['file'],  # xl/ 상대경로 아님, workbook.xml 기준
                    'new_file': new_file,
                    'new_rid': new_rid,
                    'sheet_id': counter_sheet_id,
                    'visible': is_visible,
                })
                counter_sheet_id += 1
                counter_rid_num += 1
                counter_file_num += 1

        # 원본 시트들의 파일 경로 수집 (rename 후 내부 수식 교체 대상)
        original_sheet_files: set[str] = set()
        for s in sheets_el.findall(f'{{{wb_ns}}}sheet'):
            sname = s.get('name', '')
            if sname in _ORIGINAL_SHEET_NAMES:
                rid = s.get(f'{{{_NS_REL}}}id')
                rel_el = rels_tree.find(f'{{{pkg_ns}}}Relationship[@Id="{rid}"]')
                if rel_el is not None:
                    # Target이 '/xl/worksheets/sheetN.xml' 또는 'worksheets/sheetN.xml' 형태
                    target = rel_el.get('Target', '').lstrip('/')
                    if not target.startswith('xl/'):
                        target = 'xl/' + target
                    original_sheet_files.add(target)

        # Output zip 생성
        output_buf = io.BytesIO()
        with zipfile.ZipFile(output_buf, 'w', compression=zipfile.ZIP_DEFLATED) as zout:

            # 기존 파일 복사 (workbook.xml, rels, ContentTypes는 나중에 교체)
            # 원본 시트 파일은 내부 수식의 시트 참조를 (0차)로 교체
            skip_files = {'xl/workbook.xml', 'xl/_rels/workbook.xml.rels', '[Content_Types].xml'}
            for item in zin.infolist():
                if item.filename in skip_files:
                    continue
                data = zin.read(item.filename)
                # 원본 시트 파일이면 내부 시트참조를 (0차)로 교체
                # original_sheet_files는 'xl/worksheets/sheetN.xml' 형태
                if item.filename in original_sheet_files:
                    data = _patch_sheet_refs_to_zero(data)
                zout.writestr(item.filename, data)

            # 새 시트 XML 추가 (E5 교체 포함)
            for ns_info in new_sheets:
                src_path = f'xl/{ns_info["source_file"]}'
                src_xml = zin.read(src_path)
                patched_xml = _patch_sheet_xml(src_xml, ns_info['revision'])
                zout.writestr(f'xl/{ns_info["new_file"]}', patched_xml)

            # workbook.xml 수정
            # 1. 원본 시트들을 "(0차)"로 rename + 숨김 처리
            for s in sheets_el.findall(f'{{{wb_ns}}}sheet'):
                sname = s.get('name', '')
                if sname in _ORIGINAL_SHEET_NAMES:
                    s.set('name', sname + ' (0차)')
                    s.set('state', 'hidden')

            # 2. 템플릿 (수정집행) 시트들 숨김 처리
            for s in sheets_el.findall(f'{{{wb_ns}}}sheet'):
                sname = s.get('name', '')
                if sname in _REV_SHEET_TEMPLATE_NAMES:
                    s.set('state', 'hidden')

            # 3. 이전 차수 시트들도 숨김 처리 (이미 있는 경우)
            for s in sheets_el.findall(f'{{{wb_ns}}}sheet'):
                sname = s.get('name', '')
                for rev in all_revisions:
                    if rev == latest_revision:
                        continue
                    for tmpl_name in _REV_SHEET_TEMPLATE_NAMES:
                        if sname == _revision_sheet_name(tmpl_name, rev):
                            s.set('state', 'hidden')

            # 3. 새 시트 등록
            for ns_info in new_sheets:
                new_el = etree.SubElement(sheets_el, f'{{{wb_ns}}}sheet')
                new_el.set('name', ns_info['name'])
                new_el.set('sheetId', str(ns_info['sheet_id']))
                if not ns_info['visible']:
                    new_el.set('state', 'hidden')
                new_el.set(f'{{{_NS_REL}}}id', ns_info['new_rid'])

            wb_xml_out = etree.tostring(wb_tree, xml_declaration=True, encoding='UTF-8', standalone=True)
            zout.writestr('xl/workbook.xml', wb_xml_out)

            # workbook.xml.rels 수정
            for ns_info in new_sheets:
                rel_el = etree.SubElement(rels_tree, f'{{{pkg_ns}}}Relationship')
                rel_el.set('Id', ns_info['new_rid'])
                rel_el.set('Type', _SHEET_REL_TYPE)
                rel_el.set('Target', ns_info['new_file'])

            rels_xml_out = etree.tostring(rels_tree, xml_declaration=True, encoding='UTF-8', standalone=True)
            zout.writestr('xl/_rels/workbook.xml.rels', rels_xml_out)

            # ContentTypes 수정
            for ns_info in new_sheets:
                override_el = etree.SubElement(ct_tree, f'{{{_NS_CT}}}Override')
                override_el.set('PartName', f'/xl/{ns_info["new_file"]}')
                override_el.set('ContentType', _SHEET_CT)

            ct_xml_out = etree.tostring(ct_tree, xml_declaration=True, encoding='UTF-8', standalone=True)
            zout.writestr('[Content_Types].xml', ct_xml_out)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output_buf.getvalue())
