"""Excel 시트 공용 유틸리티 — _rev_col 등 중복 로직 통합."""

from __future__ import annotations


def rev_col(revision: int) -> str:
    """차수 → 열 문자 변환. E=0차, F=1차, ..., P=11차."""
    return chr(ord("E") + revision)
