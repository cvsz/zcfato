"""Launch the Marquee Status application."""
import os
import sys

os.environ["CAMFROG_APP_PROFILE"] = "status"

from status_marquee_gui import main


if __name__ == "__main__":
    sys.exit(main())
