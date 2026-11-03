"""Writes tools/blursave_editor.ico, the icon of BlurSaveEditor.exe (own design: a night-blue tile with a glowing hexagon, the shape of the game's colour picker, and "bs").
Development tool, not part of the editor. Needs PIL.  Run:  py tools/make_app_icon.py"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "blursave_editor.ico")
S = 1024                                          # drawn large, then scaled down
BG, BLUE, BLUE_HI, CYAN, FG = "#0a1030", "#1852bf", "#2f7bff", "#17baff", "#eef4ff"


def hexagon(cx, cy, r):
    return [(cx + r * math.cos(math.radians(60 * i + 30)), cy + r * math.sin(math.radians(60 * i + 30))) for i in range(6)]


def font(size):
    for name in ("bahnschrift.ttf", "segoeuib.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((24, 24, S - 24, S - 24), radius=190, fill=BG, outline=BLUE, width=22)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).polygon(hexagon(S / 2, S / 2, 400), fill=CYAN)
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(46)))
    d = ImageDraw.Draw(img)
    d.polygon(hexagon(S / 2, S / 2, 392), fill=BLUE)
    d.polygon(hexagon(S / 2, S / 2, 392), outline=CYAN, width=20)
    d.polygon(hexagon(S / 2, S / 2, 318), fill="#0e1a4d")
    f = font(400)
    box = d.textbbox((0, 0), "bs", font=f)
    d.text((S / 2 - (box[0] + box[2]) / 2, S / 2 - (box[1] + box[3]) / 2 - 8), "bs", font=f, fill=FG)
    return img


if __name__ == "__main__":
    img = draw()
    img.save(OUT, sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(os.environ.get("TEMP", "."), "app_icon_256.png"))
    img.resize((32, 32), Image.LANCZOS).save(os.path.join(os.environ.get("TEMP", "."), "app_icon_32.png"))
    print("written", OUT, os.path.getsize(OUT), "bytes")
