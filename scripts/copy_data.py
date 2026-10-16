"""Copy the CRSP price panel and PIT macro file from regime-router into data/raw and write the manifest.

The source repo is read-only: files are copied byte-for-byte and verified by SHA-256.
"""

import shutil
from pathlib import Path

from buying_analysis.data import RAW_DIR, sha256, write_manifest

SRC = Path("/home/ryanf/classes/CS592/regime-router/data/processed")
FILES = ["prices_daily.parquet", "macro_pit.parquet"]


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src, dst = SRC / name, RAW_DIR / name
        if dst.exists() and sha256(dst) == sha256(src):
            print(f"{name}: already up to date")
            continue
        if dst.exists():
            dst.chmod(0o644)
        shutil.copy2(src, dst)
        if sha256(dst) != sha256(src):
            raise SystemExit(f"{name}: hash mismatch after copy")
        dst.chmod(0o444)
        print(f"{name}: copied")
    print(write_manifest({n: f"`{SRC / n}`" for n in FILES}))


if __name__ == "__main__":
    main()
