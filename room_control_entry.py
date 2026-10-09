"""Launch the room-only Camfrog control application."""
import os
import sys
from pathlib import Path

os.environ["CAMFROG_APP_PROFILE"] = "room"
os.environ["CAMFROG_APP_DATA_DIR"] = str(
    Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else
    Path(__file__).resolve().parent / "room-control-data")

from room_control_gui import main


if __name__ == "__main__":
    sys.exit(main())
