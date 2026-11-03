"""Draw assets/spyglass.ico (black tile, green magnifier). Run with the app's .venv (needs Pillow)."""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "spyglass.ico")
GREEN = (0, 255, 65, 255)

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((0, 0, S - 1, S - 1), radius=48, fill=(0, 0, 0, 255), outline=(13, 74, 31, 255), width=6)
d.ellipse((44, 44, 172, 172), outline=GREEN, width=20)
d.line((158, 158, 214, 214), fill=GREEN, width=30)
d.ellipse((199, 199, 229, 229), fill=GREEN)
for i, x in enumerate((78, 102, 126)):  # a few "digits" inside the lens
    d.rectangle((x, 92 + (i % 2) * 14, x + 10, 124 + (i % 2) * 14), fill=(0, 255, 65, 170))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
img.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", os.path.normpath(OUT))
