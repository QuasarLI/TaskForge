"""Render application and Gumroad assets from TaskForge's original programmatic icon."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QApplication
from PIL import Image, ImageDraw, ImageFont
from taskforge import icon

app = QApplication([])
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
png = os.path.join(root, "taskforge.png")
icon.render(256).save(png, "PNG")
Image.open(png).save(os.path.join(root, "taskforge.ico"),
                     sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

cover = Image.new("RGB", (1200, 675), "#050b07")
draw = ImageDraw.Draw(cover)
for x in range(0, 1200, 48):
    draw.line((x, 0, x, 675), fill="#0b1a10", width=1)
for y in range(0, 675, 48):
    draw.line((0, y, 1200, y), fill="#0b1a10", width=1)
matrix_icon = os.path.join(root, "_matrix-icon.png")
icon.render(420, "#22c55e", "#a3e635").save(matrix_icon, "PNG")
badge = Image.open(matrix_icon).convert("RGBA")
cover.paste(badge, (90, 125), badge)
os.remove(matrix_icon)
try:
    title_font = ImageFont.truetype("segoeuib.ttf", 104)
    sub_font = ImageFont.truetype("segoeui.ttf", 34)
except OSError:
    title_font = sub_font = ImageFont.load_default()
draw.text((560, 205), "TASKFORGE", fill="#d7ffe4", font=title_font)
draw.text((568, 335), "System Control Center", fill="#6fa384", font=sub_font)
draw.rounded_rectangle((565, 410, 1080, 480), radius=18, outline="#22c55e", width=3, fill="#08130c")
draw.text((603, 424), "CONTROL • MONITOR • RESTORE", fill="#a3e635", font=sub_font)
cover.save(os.path.join(root, "taskforge-gumroad-matrix-cover.png"), optimize=True)
print("application icon and 1200x675 Gumroad cover written")
