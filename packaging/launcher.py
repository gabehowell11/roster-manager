"""PyInstaller entry point. It needs a script file, so this just calls the app's main."""

import sys

from rostermanager.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
