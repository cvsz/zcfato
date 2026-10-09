"""Launch the web status updater: GUI with no args, CLI passthrough otherwise."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from web_status_gui import main


if __name__ == "__main__":
    raise SystemExit(main())
