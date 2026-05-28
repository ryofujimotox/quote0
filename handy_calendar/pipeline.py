"""iCal 取得から Dot 送信までの実行順を管理する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from .errors import HandyCalendarError, PipelineError


T = TypeVar("T")


@dataclass(frozen=True)
class Stage:
    """単発実行パイプラインの 1 段階。"""

    name: str
    action: Callable[[], object]


def run_stage(name: str, action: Callable[[], T]) -> T:
    """段階名を付けて処理を実行し、失敗原因を追える例外にする。"""
    try:
        return action()
    except HandyCalendarError:
        raise
    except Exception as exc:
        raise PipelineError(f"{name} で失敗しました: {exc}") from exc


def run_stages(stages: tuple[Stage, ...]) -> None:
    """前段が成功したときだけ次段を実行する。"""
    for stage in stages:
        run_stage(stage.name, stage.action)
