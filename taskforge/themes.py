"""Theme palettes and the Qt stylesheet template they fill."""

THEMES = {
    "Midnight Violet": dict(bg="#0b0d12", panel="#12151e", card="#151a26", border="#232a3b", text="#e8edf5",
                            muted="#7f8ba3", accent="#8b5cf6", accent2="#22d3ee", hover="#1c2233",
                            danger="#dc2626", ok="#22c55e", warn="#f59e0b", sel="#2e1f5e"),
    "OLED Black": dict(bg="#000000", panel="#070707", card="#0d0d0d", border="#1d1d1d", text="#f2f2f2",
                       muted="#8a8a8a", accent="#3b82f6", accent2="#a3e635", hover="#151515",
                       danger="#ef4444", ok="#22c55e", warn="#eab308", sel="#10264d"),
    "Nord Frost": dict(bg="#2e3440", panel="#3b4252", card="#353c4a", border="#4c566a", text="#eceff4",
                       muted="#a3adbf", accent="#88c0d0", accent2="#a3be8c", hover="#434c5e",
                       danger="#bf616a", ok="#a3be8c", warn="#ebcb8b", sel="#4c566a"),
    "Ember Red": dict(bg="#110a0a", panel="#1a0f0f", card="#1f1313", border="#3a1d1d", text="#f6e9e6",
                      muted="#b08a84", accent="#f97316", accent2="#ef4444", hover="#2a1717",
                      danger="#b91c1c", ok="#84cc16", warn="#fbbf24", sel="#4a1d10"),
    "Matrix Green": dict(bg="#050b07", panel="#08130c", card="#0b1a10", border="#143321", text="#d7ffe4",
                         muted="#6fa384", accent="#22c55e", accent2="#a3e635", hover="#0f2416",
                         danger="#dc2626", ok="#4ade80", warn="#facc15", sel="#0f3d20"),
    "Arctic Light": dict(bg="#f4f6fb", panel="#ffffff", card="#ffffff", border="#d9dfeb", text="#1b2333",
                         muted="#64708a", accent="#4f46e5", accent2="#0891b2", hover="#eef1f8",
                         danger="#dc2626", ok="#16a34a", warn="#d97706", sel="#dfe3ff"),
}

QSS = """
* {{ font-family: 'Segoe UI'; font-size: 10pt; color: {text}; }}
QMainWindow, QDialog {{ background: {bg}; }}
QWidget#Root, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {bg}; }}
QToolTip {{ background: {card}; color: {text}; border: 1px solid {accent}; padding: 6px; }}

#Header {{ background: {panel}; border-bottom: 1px solid {border}; }}
#HeaderTitle {{ font-size: 15pt; font-weight: 800; letter-spacing: 3px; }}
#HeaderSub {{ color: {muted}; font-size: 8.5pt; }}
#Chip {{ background: {card}; border: 1px solid {border}; border-radius: 11px; padding: 3px 10px;
         color: {muted}; font-weight: 600; }}
#ChipAdmin {{ background: {ok}; color: #0b0d12; border-radius: 11px; padding: 3px 10px; font-weight: 700; }}
#ChipUser {{ background: {warn}; color: #0b0d12; border-radius: 11px; padding: 3px 10px; font-weight: 700; }}

#Sidebar {{ background: {panel}; border-right: 1px solid {border}; }}
#Sidebar QPushButton {{ background: transparent; color: {muted}; text-align: left; padding: 10px 16px;
    border: none; border-left: 3px solid transparent; font-weight: 600; font-size: 10.5pt; }}
#Sidebar QPushButton:hover {{ background: {hover}; color: {text}; }}
#Sidebar QPushButton:checked {{ background: {hover}; color: {accent}; border-left: 3px solid {accent}; }}
#SidebarFoot {{ color: {muted}; font-size: 8pt; }}

#PageTitle {{ font-size: 17pt; font-weight: 700; }}
#PageSub, #Muted {{ color: {muted}; }}
#Explain {{ color: {muted}; font-size: 9pt; }}
#BigValue {{ font-size: 18pt; font-weight: 700; color: {accent}; }}
#Value {{ font-weight: 700; color: {accent}; }}
#Warn {{ color: {warn}; }}
#Danger {{ color: {danger}; font-weight: 600; }}
#Ok {{ color: {ok}; font-weight: 600; }}

QGroupBox {{ background: {card}; border: 1px solid {border}; border-radius: 10px; margin-top: 14px;
    padding: 14px 12px 10px 12px; font-weight: 700; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {accent}; }}
#Card {{ background: {card}; border: 1px solid {border}; border-radius: 10px; }}

QPushButton {{ background: {hover}; border: 1px solid {border}; border-radius: 7px; padding: 7px 14px;
    font-weight: 600; }}
QPushButton:hover {{ border-color: {accent}; }}
QPushButton:disabled {{ color: {muted}; }}
QPushButton#AccentBtn {{ background: {accent}; color: #ffffff; border: none; }}
QPushButton#AccentBtn:hover {{ background: {accent2}; }}
QPushButton#DangerBtn {{ background: {danger}; color: #ffffff; border: none; }}

QLineEdit, QComboBox, QSpinBox {{ background: {panel}; border: 1px solid {border}; border-radius: 7px;
    padding: 6px 8px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {accent}; }}
QComboBox QAbstractItemView {{ background: {panel}; selection-background-color: {sel}; border: 1px solid {border}; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}

QTableWidget, QTreeWidget {{ background: {card}; alternate-background-color: {panel}; border: 1px solid {border};
    border-radius: 8px; gridline-color: transparent; selection-background-color: {sel}; selection-color: {text}; }}
QHeaderView::section {{ background: {panel}; color: {accent}; padding: 6px; border: none;
    border-bottom: 1px solid {border}; font-weight: 700; }}
QTableCornerButton::section {{ background: {panel}; border: none; }}

QProgressBar {{ background: {panel}; border: 1px solid {border}; border-radius: 5px; height: 12px;
    text-align: center; font-size: 8pt; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {accent}, stop:1 {accent2});
    border-radius: 4px; }}

QSlider::groove:horizontal {{ height: 6px; background: {border}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {text}; border: 2px solid {accent}; width: 14px; height: 14px;
    margin: -5px 0; border-radius: 8px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QMenu {{ background: {panel}; border: 1px solid {border}; padding: 4px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 4px; }}
QMenu::item:selected {{ background: {sel}; }}
QStatusBar {{ background: {panel}; color: {muted}; border-top: 1px solid {border}; }}
"""


def stylesheet(name: str) -> str:
    return QSS.format(**THEMES.get(name, THEMES["Midnight Violet"]))


def palette(name: str) -> dict:
    return THEMES.get(name, THEMES["Midnight Violet"])
