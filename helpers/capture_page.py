"""Save a dated copy of a web page into the case's files folder, with its SHA-256 fingerprint.

The fingerprint proves later that the saved copy has not been changed since it was captured.
Runs with the case's files folder as the working directory (the server sets that).
"""
import hashlib
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

try:
    import certifi
except ImportError:
    sys.exit("The 'certifi' Python package is missing. Run: python -m pip install -r requirements.txt")

# Windows' Python often lacks intermediate certificates; certifi's bundle has them.
SSL = ssl.create_default_context(cafile=certifi.where())

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def main(url: str) -> int:
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8,es;q=0.6"})
    when = datetime.now(timezone.utc)
    try:
        r = urllib.request.urlopen(req, timeout=40, context=SSL)
    except urllib.error.HTTPError as e:
        r = e  # still save what the server sent (a 403 or 404 page is evidence too)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"Could not reach the page: {getattr(e, 'reason', e)}")
        return 1
    with r:
        body = r.read()
        final = r.geturl()
        status = r.status
        ctype = r.headers.get("Content-Type", "")
    ext = ".html" if "html" in ctype or not ctype else ".pdf" if "pdf" in ctype else ".bin"
    host = re.sub(r"[^\w.-]", "_", final.split("/")[2])[:50]
    name = f"capture {when:%Y-%m-%d %H%M%S}Z {host}{ext}"
    with open(name, "wb") as f:
        f.write(body)
    sha = hashlib.sha256(body).hexdigest()
    record = (f"Page asked for:  {url}\nPage received:   {final}\nServer answer:   {status} ({ctype})\n"
              f"Captured (UTC):  {when:%Y-%m-%d %H:%M:%S}\nSaved as:        {name}\n"
              f"Size:            {len(body):,} bytes\nSHA-256:         {sha}\n")
    with open(name + ".sha256.txt", "w", encoding="utf-8") as f:
        f.write(record)
    print(record)
    print("The copy and its fingerprint are in this case's files folder.")
    print("Note: pages built by scripts or behind a login may save without their content;")
    print("for those, also use 'Save it in the Wayback Machine' or a screenshot.")
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:]).strip()))
