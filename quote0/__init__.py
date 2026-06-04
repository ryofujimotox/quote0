"""quote0 パッケージ。"""

from __future__ import annotations

import sys
from pathlib import Path

# vendor/quote0_client を import 可能にする（pytest.ini と同様）
_vendor_dir = Path(__file__).resolve().parent.parent / "vendor"
if _vendor_dir.is_dir():
    vendor_path = str(_vendor_dir)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
