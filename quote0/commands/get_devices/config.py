"""デバイス一覧取得用の設定読み込み。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from quote0.config import ConfigError


def load_dot_api_token(env_file: str | Path | None = None) -> str:
    """`.env` から DOT_API_TOKEN だけ読み込む。

    例: DOT_API_TOKEN=token → "token"
    """
    load_dotenv(dotenv_path=env_file)

    dot_api_token = os.getenv("DOT_API_TOKEN", "").strip()
    if not dot_api_token:
        raise ConfigError("環境変数 DOT_API_TOKEN が未設定です。")

    return dot_api_token
