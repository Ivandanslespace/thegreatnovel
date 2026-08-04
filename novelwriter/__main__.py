"""支持 ``python -m novelwriter`` 运行。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
