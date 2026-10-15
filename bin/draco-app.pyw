# Windows launcher (runs without a console window): double-click, or pythonw draco.pyw [URL]
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from draco.__main__ import main  # noqa: E402

sys.exit(main())
