"""Read where and when a photo was taken from its hidden details (uses ExifTool)."""
import json
import shutil
import subprocess
import sys


def main(path: str) -> int:
    exe = shutil.which("exiftool")
    if not exe:
        hint = {"win32": "winget install OliverBetz.ExifTool", "darwin": "brew install exiftool"}.get(
            sys.platform, "install ExifTool from https://exiftool.org")
        print(f"ExifTool is not installed. Install it with: {hint}")
        return 1
    out = subprocess.run([exe, "-j", "-n", "-GPSLatitude", "-GPSLongitude", "-GPSAltitude",
                          "-DateTimeOriginal", "-CreateDate", "-OffsetTimeOriginal", "-Make", "-Model",
                          "-Software", path], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        d = json.loads(out.stdout)[0]
    except (ValueError, IndexError):
        print(out.stdout or out.stderr)
        return 1
    taken = d.get("DateTimeOriginal") or d.get("CreateDate")
    print(f"Taken:     {taken or 'no date stored'} {d.get('OffsetTimeOriginal', '')}".rstrip())
    cam = " ".join(str(d[k]) for k in ("Make", "Model") if d.get(k))
    print(f"Device:    {cam or 'not stored'}")
    if d.get("Software"):
        print(f"Software:  {d['Software']}  (an editing app here can mean the photo was changed)")
    lat, lon = d.get("GPSLatitude"), d.get("GPSLongitude")
    if lat is None or lon is None:
        print("Location:  none stored. Most social media sites strip it when a photo is uploaded.")
        return 0
    print(f"Location:  {lat:.6f}, {lon:.6f}")
    if d.get("GPSAltitude") is not None:
        print(f"Altitude:  {d['GPSAltitude']:.0f} m")
    print(f"Map:       https://www.google.com/maps?q={lat:.6f},{lon:.6f}")
    print(f"Map (OSM): https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=17/{lat:.6f}/{lon:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
