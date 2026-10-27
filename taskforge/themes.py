"""Theme palettes and shared visual-system tokens for the Qt stylesheet."""

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
    "Cyber Ocean": dict(bg="#06121b", panel="#0a1d2a", card="#0c2433", border="#174158", text="#e2f7ff",
                        muted="#76aabd", accent="#00b8d9", accent2="#2dd4bf", hover="#123246",
                        danger="#fb7185", ok="#34d399", warn="#fbbf24", sel="#0c4a6e"),
    "Solarized Dusk": dict(bg="#171a21", panel="#20242d", card="#272c36", border="#3c4350", text="#f2e9d8",
                           muted="#aaa18e", accent="#e6a15c", accent2="#6dc5c3", hover="#303642",
                           danger="#e06c75", ok="#98c379", warn="#e5c07b", sel="#5a402c"),
    "Royal Amethyst": dict(bg="#130d20", panel="#1d1430", card="#25193b", border="#493568", text="#f5edff",
                           muted="#ad94c9", accent="#c084fc", accent2="#f472b6", hover="#332249",
                           danger="#fb7185", ok="#86efac", warn="#fde047", sel="#563079"),
    "Slate Professional": dict(bg="#161b22", panel="#1f2630", card="#252e3a", border="#3b4756", text="#edf2f7",
                               muted="#9ba9ba", accent="#60a5fa", accent2="#94a3b8", hover="#303b49",
                               danger="#f87171", ok="#4ade80", warn="#fbbf24", sel="#314d73"),
}

TOKENS = {
    "space_1": 4,
    "space_2": 8,
    "space_3": 12,
    "space_4": 16,
    "space_5": 24,
    "space_6": 32,
    "radius_control": 7,
    "radius_card": 11,
    "radius_panel": 14,
    "control_height": 34,
    "table_row_height": 34,
}


def _luminance(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_foreground(color: str) -> str:
    """Choose readable button text for either light or dark theme accents."""
    return "#111827" if _luminance(color) > 0.38 else "#ffffff"


def design_tokens(name: str) -> dict:
    colors = THEMES.get(name, THEMES["Midnight Violet"])
    return {
        **TOKENS,
        **colors,
        "accent_text": contrast_foreground(colors["accent"]),
        "accent2_text": contrast_foreground(colors["accent2"]),
        "danger_text": contrast_foreground(colors["danger"]),
        "ok_text": contrast_foreground(colors["ok"]),
        "warn_text": contrast_foreground(colors["warn"]),
        "selected_text": contrast_foreground(colors["sel"]),
    }


QSS = """
* {{ font-family: 'Segoe UI'; font-size: 10pt; color: {text}; }}
QMainWindow, QDialog {{ background: {bg}; }}
QWidget#Root, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {bg}; }}
QToolTip {{ background: {card}; color: {text}; border: 1px solid {border}; border-radius: {radius_control}px;
    padding: {space_2}px {space_3}px; }}

#Header {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {panel}, stop:1 {bg});
    border-bottom: 1px solid {border}; }}
#HeaderTitle {{ font-size: 15pt; font-weight: 800; }}
#HeaderSub {{ color: {muted}; font-size: 9pt; }}
#Chip {{ background: {card}; border: 1px solid {border}; border-radius: 12px; padding: 4px 10px;
         color: {muted}; font-weight: 600; }}
#ChipAdmin {{ background: {ok}; color: {ok_text}; border-radius: 12px; padding: 4px 10px; font-weight: 700; }}
#ChipUser {{ background: {warn}; color: {warn_text}; border-radius: 12px; padding: 4px 10px; font-weight: 700; }}

#Sidebar {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {panel}, stop:1 {bg});
    border-right: 1px solid {border}; }}
#Sidebar QPushButton {{ background: transparent; color: {muted}; text-align: left;
    padding: {space_2}px {space_3}px;
    min-height: 20px; border: 1px solid transparent; border-left: 3px solid transparent;
    border-radius: {radius_control}px; font-weight: 600; }}
#Sidebar QPushButton:hover {{ background: {hover}; color: {text}; border-color: {border}; }}
#Sidebar QPushButton:checked {{ background: {sel}; color: {selected_text}; border: 1px solid {accent};
    border-left: 3px solid {accent}; }}
#Sidebar QPushButton:focus {{ border: 2px solid {accent}; }}
#Sidebar[compact="true"] QPushButton {{ text-align: center; padding: 8px 3px; }}
#SidebarFoot {{ color: {muted}; font-size: 8.5pt; }}
#SidebarToggle {{ background: {card}; color: {muted}; }}

#PageHeader {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {panel}, stop:1 {bg});
    border: 1px solid {border}; border-left: 3px solid {accent}; border-radius: {radius_panel}px; }}
#PageTitle {{ font-size: 18pt; font-weight: 700; }}
#PageSub, #Muted {{ color: {muted}; }}
#PageSub {{ font-size: 9.5pt; }}
#Explain {{ color: {muted}; font-size: 9pt; }}
#BigValue {{ font-size: 19pt; font-weight: 700; color: {accent}; }}
#Value {{ font-weight: 700; color: {accent}; }}
#Warn {{ color: {warn}; }}
#Danger {{ color: {danger}; font-weight: 600; }}
#Ok {{ color: {ok}; font-weight: 600; }}
#SectionKicker {{ color: {muted}; font-size: 8.5pt; font-weight: 700; }}

QGroupBox {{ background: {card}; border: 1px solid {border}; border-radius: {radius_card}px;
    margin-top: {space_4}px; padding: {space_3}px {space_3}px {space_2}px {space_3}px; font-weight: 700; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 7px; color: {text}; }}
#Card, #MetricCard {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {card}, stop:1 {panel});
    border: 1px solid {border}; border-radius: {radius_card}px; }}
#MetricCard {{ border-top: 2px solid {accent}; }}

QPushButton {{ background: {hover}; border: 1px solid {border}; border-radius: {radius_control}px;
    padding: {space_2}px {space_3}px; min-height: {control_height}px; font-weight: 600; }}
QPushButton:hover {{ background: {sel}; color: {selected_text}; border-color: {accent}; }}
QPushButton:pressed {{ background: {panel}; }}
QPushButton:disabled {{ background: {panel}; color: {muted}; border-color: {border}; }}
QPushButton:focus {{ border: 2px solid {accent}; }}
QPushButton#AccentBtn, QPushButton[variant="primary"] {{ background: {accent}; color: {accent_text}; border: 1px solid {accent}; }}
QPushButton#AccentBtn:hover, QPushButton[variant="primary"]:hover {{ background: {accent2}; color: {accent2_text}; }}
QPushButton#DangerBtn, QPushButton[variant="danger"] {{ background: {danger}; color: {danger_text}; border: 1px solid {danger}; }}
QPushButton#DangerBtn:hover, QPushButton[variant="danger"]:hover {{ border: 2px solid {text}; }}
QPushButton#QuietBtn {{ background: transparent; border-color: transparent; color: {muted}; }}
QPushButton#QuietBtn:hover {{ background: {hover}; color: {text}; }}
QPushButton#SplashHide {{ padding: 3px 9px; min-height: 20px; }}

QLineEdit, QComboBox, QSpinBox {{ background: {panel}; border: 1px solid {border}; border-radius: {radius_control}px;
    padding: {space_1}px {space_2}px; min-height: 24px; selection-background-color: {sel}; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color: {muted}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 2px solid {accent}; }}
QComboBox QAbstractItemView {{ background: {panel}; selection-background-color: {sel};
    selection-color: {selected_text}; border: 1px solid {border}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
QCheckBox:focus::indicator, QRadioButton:focus::indicator {{ border: 2px solid {accent}; }}

QTableWidget, QTreeWidget {{ background: {card}; alternate-background-color: {panel}; border: 1px solid {border};
    border-radius: {radius_control}px; gridline-color: transparent; selection-background-color: {sel};
    selection-color: {selected_text}; }}
QTableWidget:focus, QTreeWidget:focus {{ border: 2px solid {accent}; }}
QTableWidget::item, QTreeWidget::item {{ padding: {space_1}px {space_2}px;
    min-height: {table_row_height}px; border-bottom: 1px solid {border}; }}
QTableWidget::item:hover, QTreeWidget::item:hover {{ background: {hover}; }}
QTableWidget::item:selected, QTreeWidget::item:selected {{ background: {sel}; color: {text}; }}
QHeaderView::section {{ background: {panel}; color: {text}; padding: 8px 7px; border: none;
    border-bottom: 2px solid {border}; font-weight: 700; }}
QHeaderView::section:hover {{ color: {accent}; background: {hover}; }}
QHeaderView::section:checked {{ border-bottom-color: {accent}; }}
QHeaderView::section:focus {{ border-bottom: 2px solid {accent}; }}
QTableCornerButton::section {{ background: {panel}; border: none; }}

QProgressBar {{ background: {panel}; border: 1px solid {border}; border-radius: 5px; height: 13px;
    text-align: center; font-size: 8pt; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {accent}, stop:1 {accent2});
    border-radius: 4px; }}

QSlider::groove:horizontal {{ height: 6px; background: {border}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {text}; border: 2px solid {accent}; width: 14px; height: 14px;
    margin: -5px 0; border-radius: 8px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {muted}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 5px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QMenu {{ background: {panel}; border: 1px solid {border}; padding: 5px; }}
QMenu::item {{ padding: {space_2}px {space_5}px; border-radius: 4px; }}
QMenu::item:selected {{ background: {sel}; color: {selected_text}; }}
QStatusBar {{ background: {panel}; color: {muted}; border-top: 1px solid {border}; }}
QStatusBar::item {{ border: none; }}
"""


def stylesheet(name: str) -> str:
    return QSS.format(**design_tokens(name))


def palette(name: str) -> dict:
    return design_tokens(name)
