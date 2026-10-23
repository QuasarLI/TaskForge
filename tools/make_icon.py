"""Render the app icon to assets/taskforge.ico (multi-size)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QApplication
from PIL import Image
from taskforge import icon

app = QApplication([])
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
png = os.path.join(root, "taskforge.png")
icon.render(256).save(png, "PNG")
Image.open(png).save(os.path.join(root, "taskforge.ico"),
                     sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written")
