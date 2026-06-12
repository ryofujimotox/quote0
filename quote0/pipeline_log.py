"""バッチパイプラインの段階ログ（成功=stdout / 失敗=stderr）。"""

from __future__ import annotations

import sys


def log_info(message: str) -> None:
    print(message, flush=True)


def log_error(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def log_stage_start(stage: str, *, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    log_info(f"{stage} 開始{suffix}")


def log_stage_success(stage: str, *, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    log_info(f"{stage} 成功{suffix}")
