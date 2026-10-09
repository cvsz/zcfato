"""Launch the Random Status application."""
import os
import sys

os.environ["CAMFROG_APP_PROFILE"] = "status"

from status_random_gui import main


if __name__ == "__main__":
    sys.exit(main())
