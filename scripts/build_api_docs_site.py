from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.main import app
SITE_API_DIR = REPO_ROOT / "docs" / "site" / "api"


def main() -> None:
    SITE_API_DIR.mkdir(parents=True, exist_ok=True)

    live_path = SITE_API_DIR / "openapi-live.json"
    next_path = SITE_API_DIR / "openapi-next.yaml"

    live_path.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    shutil.copyfile(REPO_ROOT / "docs" / "api" / "openapi-next.yaml", next_path)


if __name__ == "__main__":
    main()
