"""pipeline.py の単体テスト。"""

from __future__ import annotations

import pytest

from handy_calendar.errors import PipelineError
from handy_calendar.pipeline import Stage, run_stage, run_stages


def test_run_stage_returns_action_value() -> None:
    assert run_stage("確認", lambda: "ok") == "ok"


def test_run_stage_wraps_unexpected_error_with_stage_name() -> None:
    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(PipelineError, match="iCal 取得 で失敗しました"):
        run_stage("iCal 取得", fail)


def test_run_stages_stops_after_failure() -> None:
    called: list[str] = []

    def fetch() -> None:
        called.append("fetch")

    def render() -> None:
        called.append("render")
        raise RuntimeError("描画失敗")

    def send() -> None:
        called.append("send")

    stages = (
        Stage("iCal 取得・解析", fetch),
        Stage("PNG 生成", render),
        Stage("Dot 送信", send),
    )

    with pytest.raises(PipelineError, match="PNG 生成"):
        run_stages(stages)

    assert called == ["fetch", "render"]
