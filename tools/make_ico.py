"""Pack the PNG icon sizes into a Windows .ico (PNG-compressed entries, Windows Vista+).

    python3 tools/make_ico.py      -> data/draco.ico
"""

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZES = (16, 24, 32, 48, 64, 128, 256)


def main():
    images = [(s, (ROOT / "data" / "icons" / f"{s}.png").read_bytes()) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size          # 0 means 256 in the ICO format
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        blobs += png
    out = ROOT / "data" / "draco.ico"
    out.write_bytes(header + entries + blobs)
    print("wrote", out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
