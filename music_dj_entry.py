"""Launch the Music DJ application."""
import os
import sys
from pathlib import Path

os.environ["CAMFROG_APP_DATA_DIR"] = str(
    Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else
    Path(__file__).resolve().parent / "music-dj-data")

from camfrog_music_gui import main


if __name__ == "__main__":
    sys.exit(main())
