import sys
from pathlib import Path

# Make the sibling `ai/` package importable locally (repo root).
_root = str(Path(__file__).resolve().parents[2])
if _root not in sys.path:
    sys.path.insert(0, _root)
