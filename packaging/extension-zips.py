"""Write the browser-extension zips (Chromium + Firefox variants) into a folder.

    python3 packaging/extension-zips.py dist
"""

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "extension" / "chrome"


def write_zip(target, manifest):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(SRC.rglob("*")):
            if f.is_file() and f.name != "manifest.json":
                z.write(f, f.relative_to(SRC).as_posix())
        z.writestr("manifest.json", json.dumps(manifest, indent=2))


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    man = json.loads((SRC / "manifest.json").read_text())
    v = man["version"]
    write_zip(out / f"draco-extension-chromium-{v}.zip", man)
    ff = dict(man)
    ff.pop("key", None)
    ff["background"] = {"scripts": [man["background"]["service_worker"]]}
    ff["browser_specific_settings"] = {"gecko": {"id": "draco@draco.github.io", "strict_min_version": "115.0"}}
    write_zip(out / f"draco-extension-firefox-{v}.zip", ff)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dist")
