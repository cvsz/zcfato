"""Launch the private IM auto-reply application."""
import os
import sys
from pathlib import Path

os.environ["CAMFROG_APP_PROFILE"] = "im_reply"
os.environ["CAMFROG_APP_DATA_DIR"] = str(
    Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else
    Path(__file__).resolve().parent / "im-autoreply-data")

from im_autoreply_gui import main


if __name__ == "__main__":
    sys.exit(main())
