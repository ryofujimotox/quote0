"""アプリ全体で使う例外。"""

from __future__ import annotations


class HandyCalendarError(Exception):
    """原因を利用者へ説明できるアプリ内エラー。"""


class PipelineError(HandyCalendarError):
    """処理段階の失敗を表す例外。"""
