"""Project-root launcher; keeps the src layout usable without installation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from tgn.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
