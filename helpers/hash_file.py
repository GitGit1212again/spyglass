"""Print a file's fingerprints (MD5, SHA-1, SHA-256), size and dates."""
import hashlib
import os
import sys
from datetime import datetime


def main(path: str) -> int:
    hs = [hashlib.md5(), hashlib.sha1(), hashlib.sha256()]
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            for h in hs:
                h.update(chunk)
    st = os.stat(path)
    print(f"File:      {os.path.basename(path)}")
    print(f"Size:      {st.st_size:,} bytes")
    print(f"Modified:  {datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M:%S} (on this PC)")
    print(f"MD5:       {hs[0].hexdigest()}")
    print(f"SHA-1:     {hs[1].hexdigest()}")
    print(f"SHA-256:   {hs[2].hexdigest()}")
    print("\nIf any byte of the file changes, these fingerprints change. SHA-256 is the one courts and")
    print("e-discovery platforms usually expect.")
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
