"""
自动化工作台 v4.1 — Apple iOS / macOS 清晰简洁风

启动:
    python config_app_v2.py
"""

import sys
from pathlib import Path
from typing import List, Optional

import yaml

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget,
    QScrollArea, QLineEdit, QTextEdit, QComboBox,
    QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QSplitter, QDialog, QFormLayout, QGraphicsDropShadowEffect,
    QDateEdit, QSpinBox, QDoubleSpinBox,
)
from PySide6.QtCore import Qt, QEvent, QUrl, QRectF, QTimer
from PySide6.QtGui import (
    QFont, QColor, QCursor, QDesktopServices, QIcon, QPixmap,
    QPainter, QPen, QBrush, QPainterPath, QLinearGradient,
)

PROJECT_DIR = Path(__file__).parent
WORKFLOWS_DIR = PROJECT_DIR / "config" / "workflows"


# ============================================================
# 主题色表 — 重新调整：更高对比度、更清晰
# ============================================================
THEMES = {
    "light": {
        "name": "浅色",
        "primary": "#007AFF",
        "primary_dark": "#0057D9",

        "bg": "#F5F6FA",
        "card": "#FFFFFF",
        "surface": "#FFFFFF",
        "group": "#EEF0F5",

        "text": "#111827",
        "secondary": "#4B5563",
        "muted": "#6B7280",

        "border": "#D8DCE6",
        "separator": "#C8CDD8",

        "blue": "#007AFF",
        "orange": "#FF9500",
        "red": "#FF3B30",
        "warning": "#FFCC00",
        "green": "#34C759",

        "hover": "#EEF3FF",

        "btn_bg": "#E7F0FF",
        "btn_hover_bg": "#D8E8FF",
        "btn_text": "#0057D9",
        "btn_border": "#AFCBFF",

        "danger_bg": "#FFEAEA",
        "danger_text": "#D92D20",
        "danger_border": "#FFB4AE",

        "selection_bg": "#DCEBFF",
        "input_border": "#BFC6D4",

        "radius": 12,
        "card_radius": 20,
        "font": '"SF Pro Display", "Segoe UI", "Microsoft YaHei UI", sans-serif',
        "shadow_blur": 28,
        "shadow_alpha": 18,
    },
    "dark": {
        "name": "深色",
        "primary": "#0A84FF",
        "primary_dark": "#65B4FF",

        "bg": "#111318",
        "card": "#1C1F26",
        "surface": "#242832",
        "group": "#191C22",

        "text": "#F3F4F6",
        "secondary": "#D1D5DB",
        "muted": "#9CA3AF",

        "border": "#343A46",
        "separator": "#4B5563",

        "blue": "#0A84FF",
        "orange": "#FF9F0A",
        "red": "#FF453A",
        "warning": "#FFD60A",
        "green": "#30D158",

        "hover": "#2B3240",

        "btn_bg": "#123765",
        "btn_hover_bg": "#164A88",
        "btn_text": "#D6E9FF",
        "btn_border": "#2F6EA8",

        "danger_bg": "#3A1717",
        "danger_text": "#FFB4AE",
        "danger_border": "#713333",

        "selection_bg": "#123765",
        "input_border": "#5B6472",

        "radius": 12,
        "card_radius": 20,
        "font": '"SF Pro Display", "Segoe UI", "Microsoft YaHei UI", sans-serif',
        "shadow_blur": 36,
        "shadow_alpha": 44,
    },
}

DEFAULT_THEME = "light"

# Quiet jade palette shared by all existing editors and the new daily dashboard.
THEMES['light'].update(primary='#247A67', primary_dark='#185E50', bg='#F5F6F3',
    text='#203730', secondary='#52645D', muted='#6C7B74', border='#DEE5DF',
    group='#EFF3EF', hover='#EAF2ED', btn_bg='#EDF5F0', btn_hover_bg='#DDEDE3',
    btn_text='#185E50', btn_border='#C7DED1', selection_bg='#DDEDE3', input_border='#C6D3CB')
THEMES['dark'].update(primary='#7CD6B8', primary_dark='#A5E5CC', bg='#151D1A',
    card='#1D2823', surface='#26332D', group='#202C26', text='#E9F0EA',
    secondary='#BCCDC2', muted='#99B0A1', border='#35473C', hover='#2D4035',
    btn_bg='#293E32', btn_hover_bg='#354F40', btn_text='#BDEED4',
    btn_border='#496853', selection_bg='#354F40', input_border='#587262')

C_PRIMARY = ""
C_PRIMARY_DARK = ""
C_BG = ""
C_CARD = ""
C_SURFACE = ""
C_GROUP = ""
C_TEXT = ""
C_TEXT_SECONDARY = ""
C_BORDER = ""
C_SEPARATOR = ""
C_BLUE = ""
C_ORANGE = ""
C_RED = ""
C_WARNING = ""
C_GREEN = ""
C_HOVER = ""
C_BTN_BG = ""
C_BTN_HOVER_BG = ""
C_BTN_TEXT = ""
C_BTN_BORDER = ""
C_DANGER_BG = ""
C_DANGER_TEXT = ""
C_DANGER_BORDER = ""
C_SELECTION_BG = ""
C_INPUT_BORDER = ""


# ============================================================
# 执行器配置字段
# ============================================================
EXECUTOR_CONFIG_FIELDS = {
    "wps_macro": [
        ("workbook", "文件路径", "必填 | 要打开的 xlsm/docm 文件路径"),
        ("macro", "宏名称", "选填 | JS宏名字，如 Module1.自动下单核对"),
        ("visible", "显示窗口", "选填 | true/false"),
        ("wait_complete", "等待完成", "选填 | true/false"),
    ],
    "run_python": [
        ("script", "脚本路径", "必填 | Python脚本完整路径"),
        ("args", "参数", "选填 | 逗号分隔参数列表"),
        ("mode", "运行模式", "选填 | inline / detached"),
        ("timeout", "超时(秒)", "选填 | 默认300"),
    ],
    "email_download": [
        ("keywords", "关键词", "必填 | 逗号分隔"),
        ("save_dir", "保存目录", "必填 | 附件保存路径"),
        ("mark_read", "标为已读", "选填 | true/false"),
    ],
    "file_ops": [
        ("action", "操作类型", "必填 | copy/move/sort_by_type/check_exists"),
        ("source_dir", "来源目录", "必填 | 源文件夹"),
        ("source_pattern", "匹配模式", "选填 | 如 *.xlsx"),
        ("dest_dir", "目标目录", "选填 | 目标文件夹"),
    ],
    "wms_download": [
        ("system", "WMS系统", "必填 | 系统名，如 yunkesys"),
        ("url", "系统网址", "必填 | 登录页面URL"),
        ("target_date", "目标日期", "选填 | YYYY-MM-DD"),
        ("save_dir", "保存目录", "必填 | 下载文件存放路径"),
        ("username", "用户名", "选填 | 留空则从凭据管理器读取"),
    ],
    "excel_ops": [
        ("workbook", "Excel文件", "必填 | 要操作的 xlsm 文件路径"),
        ("data_file", "数据源文件", "选填 | WMS导出文件"),
        ("sheet_name", "目标子表名", "选填 | 默认 Sheet1"),
        ("macro", "要执行的宏", "选填 | 如 Module1.自动下单核对"),
        ("visible", "显示WPS窗口", "选填 | true/false"),
    ],
    "mail_send": [
        ("to", "收件人", "必填 | 邮件收件人"),
        ("cc", "抄送", "选填 | 抄送"),
        ("subject", "主题", "选填 | 默认含日期"),
        ("body", "正文", "选填 | 可为空"),
        ("auto_send", "自动发送", "选填 | true/false"),
    ],
    "wechat_notify": [
        ("mention", "@提醒人", "选填 | 如 @王冬"),
        ("target_name", "称呼", "选填 | 如 冬哥"),
        ("hub_name", "仓库名", "选填 | 如 HUB"),
        ("template", "消息模板", "选填 | 用 {mention}{boxes} 占位"),
    ],
}

EXECUTOR_TYPES = [
    ("wps_macro", "WPS JS宏"),
    ("run_python", "Python脚本"),
    ("email_download", "邮件下载"),
    ("file_ops", "文件操作"),
    ("wms_download", "WMS数据下载"),
    ("excel_ops", "Excel操作"),
    ("mail_send", "邮件发送"),
    ("wechat_notify", "微信通知"),
]

TRIGGER_TYPES = [
    ("file_watch", "文件监控"),
    ("schedule", "定时"),
    ("manual", "手动"),
]


# ============================================================
# 主题管理器
# ============================================================
def apply_theme(app: QApplication, theme_name: str):
    global C_PRIMARY, C_PRIMARY_DARK, C_BG, C_CARD, C_SURFACE, C_GROUP
    global C_TEXT, C_TEXT_SECONDARY, C_BORDER, C_SEPARATOR
    global C_BLUE, C_ORANGE, C_RED, C_WARNING, C_GREEN, C_HOVER
    global C_BTN_BG, C_BTN_HOVER_BG, C_BTN_TEXT, C_BTN_BORDER
    global C_DANGER_BG, C_DANGER_TEXT, C_DANGER_BORDER
    global C_SELECTION_BG, C_INPUT_BORDER

    p = THEMES.get(theme_name, THEMES[DEFAULT_THEME])

    C_PRIMARY = p["primary"]
    C_PRIMARY_DARK = p["primary_dark"]
    C_BG = p["bg"]
    C_CARD = p["card"]
    C_SURFACE = p["surface"]
    C_GROUP = p["group"]
    C_TEXT = p["text"]
    C_TEXT_SECONDARY = p["secondary"]
    C_BORDER = p["border"]
    C_SEPARATOR = p["separator"]
    C_BLUE = p["blue"]
    C_ORANGE = p["orange"]
    C_RED = p["red"]
    C_WARNING = p["warning"]
    C_GREEN = p["green"]
    C_HOVER = p["hover"]
    C_BTN_BG = p["btn_bg"]
    C_BTN_HOVER_BG = p["btn_hover_bg"]
    C_BTN_TEXT = p["btn_text"]
    C_BTN_BORDER = p["btn_border"]
    C_DANGER_BG = p["danger_bg"]
    C_DANGER_TEXT = p["danger_text"]
    C_DANGER_BORDER = p["danger_border"]
    C_SELECTION_BG = p["selection_bg"]
    C_INPUT_BORDER = p["input_border"]

    app.setStyleSheet(_build_stylesheet(p))


def _build_stylesheet(p: dict) -> str:
    r = p["radius"]
    cr = p["card_radius"]
    font = p["font"]

    return f"""
    * {{
        font-family: {font};
        font-size: 15px;
        color: {p['text']};
        selection-background-color: {p['primary']};
        selection-color: #FFFFFF;
    }}

    QMainWindow, QDialog {{
        background: {p['bg']};
    }}

    QWidget {{
        color: {p['text']};
    }}

    QLabel {{
        color: {p['text']};
        background: transparent;
    }}

    QFrame#Card {{
        background: {p['card']};
        border-radius: {cr}px;
        border: 1px solid {p['border']};
    }}

    QFrame#GroupCard {{
        background: {p['group']};
        border-radius: {cr}px;
        border: 1px solid {p['border']};
    }}

    QFrame#SectionCard {{
        background: {p['surface']};
        border-radius: {r}px;
        border: 1px solid {p['border']};
    }}

    QPushButton {{
        background: {p['surface']};
        color: {p['text']};
        border: 1.5px solid {p['border']};
        border-radius: {r}px;
        padding: 9px 20px;
        font-size: 15px;
        font-weight: 400;
    }}

    QPushButton:hover {{
        background: {p['hover']};
        border-color: {p['primary']};
    }}

    QPushButton:pressed {{
        background: {p['btn_hover_bg']};
    }}

    QPushButton:disabled {{
        color: {p['muted']};
        background: {p['group']};
        border-color: {p['border']};
    }}

    QPushButton[active="true"] {{
        background: transparent;
        color: {p['primary']};
        font-weight: 400;
        border: none;
    }}

    QPushButton#NavBtn {{
        background: transparent;
        color: {p['text']};
        border: none;
        border-radius: {r}px;
        text-align: left;
        padding: 10px 14px;
        font-size: 15px;
        font-weight: 400;
    }}

    QPushButton#NavBtn:hover {{
        background: {p['hover']};
    }}

    QPushButton#NavBtn[active="true"] {{
        background: transparent;
        color: {p['primary']};
        font-weight: 400;
        border: none;
        border-left: 3px solid {p['primary']};
        padding-left: 11px;
    }}

    QPushButton#PrimaryBtn {{
        background: {p['btn_bg']};
        color: {p['btn_text']};
        border: 1.5px solid {p['btn_border']};
        border-radius: {r}px;
        padding: 10px 26px;
        font-size: 15px;
        font-weight: 400;
    }}

    QPushButton#PrimaryBtn:hover {{
        background: {p['btn_hover_bg']};
        border-color: {p['primary']};
    }}

    QPushButton#SecondaryBtn {{
        background: {p['surface']};
        color: {p['text']};
        border: 1.5px solid {p['border']};
        border-radius: {r}px;
        padding: 10px 26px;
        font-size: 15px;
        font-weight: 400;
    }}

    QPushButton#SecondaryBtn:hover {{
        background: {p['hover']};
        border-color: {p['primary']};
    }}

    QPushButton#DangerBtn {{
        background: {p['danger_bg']};
        color: {p['danger_text']};
        border: 1.5px solid {p['danger_border']};
        border-radius: {r}px;
        padding: 9px 20px;
        font-size: 14px;
        font-weight: 400;
    }}

    QPushButton#DangerBtn:hover {{
        background: {p['danger_border']};
    }}

    QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit {{
        background: {p['surface']};
        color: {p['text']};
        border: 1.8px solid {p['input_border']};
        border-radius: {r}px;
        padding: 9px 12px;
        font-size: 15px;
        min-height: 22px;
    }}

    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus, QDateTimeEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 2px solid {p['primary']};
        background: {p['surface']};
    }}

    QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{
        color: {p['muted']};
        background: {p['group']};
        border-color: {p['border']};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 28px;
    }}

    QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit {{ padding-right: 38px; }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin: border; subcontrol-position: top right;
        width: 28px; height: 20px; margin: 3px 5px 0px 0px;
        border: none; border-radius: 5px; background: transparent;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin: border; subcontrol-position: bottom right;
        width: 28px; height: 20px; margin: 0px 5px 3px 0px;
        border: none; border-radius: 5px; background: transparent;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{ background: {p['selection_bg']}; }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("{(PROJECT_DIR/'assets'/'input_plus.svg').as_posix()}"); width: 12px; height: 12px; }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("{(PROJECT_DIR/'assets'/'input_minus.svg').as_posix()}"); width: 12px; height: 12px; }}
    QDateEdit::drop-down, QDateTimeEdit::drop-down {{
        subcontrol-origin: padding; subcontrol-position: center right;
        width: 30px; border: none; background: transparent; border-radius: 6px;
    }}
    QDateEdit::drop-down:hover, QDateTimeEdit::drop-down:hover {{ background: {p['selection_bg']}; }}
    QDateEdit::down-arrow, QDateTimeEdit::down-arrow {{ image: url("{(PROJECT_DIR/'assets'/'input_calendar.svg').as_posix()}"); width: 18px; height: 18px; }}
    QCalendarWidget QWidget {{ color: {p['text']}; background: {p['surface']}; }}
    QCalendarWidget QToolButton {{ border: none; padding: 6px; color: {p['text']}; background: transparent; }}
    QCalendarWidget QAbstractItemView {{ selection-background-color: {p['selection_bg']}; selection-color: {p['text']}; }}

    QComboBox QAbstractItemView {{
        background: {p['surface']};
        border: 1.5px solid {p['input_border']};
        border-radius: {r}px;
        selection-background-color: {p['selection_bg']};
        selection-color: {p['text']};
        padding: 6px;
        outline: none;
    }}

    QCheckBox {{
        spacing: 8px;
        background: transparent;
        color: {p['text']};
        font-weight: 400;
    }}

    QCheckBox::indicator {{
        width: 20px;
        height: 20px;
        border-radius: 5px;
        border: 1.5px solid {p['separator']};
        background: {p['surface']};
    }}

    QCheckBox::indicator:hover {{
        border-color: {p['secondary']};
    }}

    QCheckBox::indicator:checked {{
        background: {p['green']};
        border: 1.5px solid {p['green']};
        image: url({_ensure_check_icon()});
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: {p['separator']};
        border-radius: 5px;
        min-height: 32px;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 0;
    }}

    QScrollBar::handle:horizontal {{
        background: {p['separator']};
        border-radius: 5px;
        min-width: 32px;
    }}

    QTreeWidget {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: {r}px;
        color: {p['text']};
        outline: none;
    }}

    QTreeWidget::item {{
        padding: 8px 10px;
        min-height: 34px;
        color: {p['text']};
    }}

    QTreeWidget::item:selected {{
        background: {p['selection_bg']};
        color: {p['text']};
    }}

    QTreeWidget::item:hover {{
        background: {p['hover']};
    }}

    QTreeWidget QHeaderView::section {{
        background: {p['group']};
        color: {p['secondary']};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {p['border']};
        font-weight: 400;
        font-size: 13px;
    }}

    QListWidget {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: {r}px;
        color: {p['text']};
        outline: none;
    }}

    QListWidget::item {{
        padding: 8px 10px;
        min-height: 32px;
        color: {p['text']};
    }}

    QListWidget::item:selected {{
        background: {p['selection_bg']};
        color: {p['text']};
    }}

    QListWidget::item:hover {{
        background: {p['hover']};
    }}

    QFrame#Separator {{
        background: {p['separator']};
        max-height: 1px;
        min-height: 1px;
    }}

    QSplitter::handle {{
        background: {p['border']};
    }}

    QSplitter::handle:horizontal {{
        width: 1px;
    }}
    """


def add_shadow(widget: QWidget, theme: str = DEFAULT_THEME):
    p = THEMES.get(theme, THEMES[DEFAULT_THEME])
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(p["shadow_blur"])
    effect.setOffset(0, 4)
    effect.setColor(QColor(0, 0, 0, p["shadow_alpha"]))
    widget.setGraphicsEffect(effect)


def _create_app_icon() -> QIcon:
    """程序化生成应用图标：蓝色渐变圆角方块 + 白色对号"""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, 64, 64)
    grad.setColorAt(0, QColor("#6AA5FF"))
    grad.setColorAt(1, QColor("#2E6BE6"))
    path = QPainterPath()
    path.addRoundedRect(QRectF(2, 2, 60, 60), 15, 15)
    p.fillPath(path, QBrush(grad))
    pen = QPen(QColor("#FFFFFF"), 6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.drawLine(18, 33, 28, 43)
    p.drawLine(28, 43, 46, 21)
    p.end()
    return QIcon(pm)


def _ensure_check_icon() -> str:
    """生成复选框选中态的白色对号图标，返回文件路径"""
    import tempfile
    d = Path(tempfile.gettempdir()) / "workbench_assets"
    d.mkdir(parents=True, exist_ok=True)
    fp = d / "cb_checked.png"
    if not fp.exists():
        pm = QPixmap(20, 20)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#FFFFFF"), 3.4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawLine(4, 10.5, 8.5, 15)
        p.drawLine(8.5, 15, 16, 5.5)
        p.end()
        pm.save(str(fp))
    return fp.as_posix()


def make_text_selectable(widget: QWidget, exclude_cls_names=None):
    """递归设置所有 QLabel 为可选中复制，含链接自动检测。
    exclude_cls_names: 跳过的父容器类名列表（如 TodoCard 点击卡片不应被拦截）"""
    import re
    url_pattern = re.compile(
        r'(https?://[^\s<>"\']+)'
    )

    if exclude_cls_names is None:
        exclude_cls_names = {"TodoCard"}

    for child in widget.findChildren(QLabel):
        p = child.parent()
        skip = False
        while p is not None:
            if type(p).__name__ in exclude_cls_names or p.objectName() in exclude_cls_names:
                skip = True
                break
            p = p.parent()
        if skip:
            continue

        text = child.text()
        if text and not child.textFormat() == Qt.RichText:
            urls = url_pattern.findall(text)
            if urls:
                escaped = text
                for url in urls:
                    escaped = escaped.replace(
                        url,
                        f'<a href="{url}" style="color: {C_PRIMARY};">{url}</a>'
                    )
                child.setTextFormat(Qt.RichText)
                child.setText(escaped)
                child.setOpenExternalLinks(True)
                child.setTextInteractionFlags(
                    Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
                )
            else:
                child.setTextInteractionFlags(Qt.TextSelectableByMouse)

        child.setCursor(Qt.IBeamCursor)

    for child in widget.findChildren(QTextEdit):
        child.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )


# ============================================================
# 顶部标题栏
# ============================================================
class CustomTitleBar(QFrame):
    def __init__(self, parent_window):
        super().__init__()
        self.window = parent_window
        self.setObjectName("TitleBar")
        self.setFixedHeight(56)

        self.setStyleSheet(f"""
            #TitleBar {{
                background: {C_CARD};
                border-bottom: 1px solid {C_BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 14, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignVCenter)

        sidebar = QPushButton("≡")
        sidebar.setFixedSize(34, 34)
        sidebar.setToolTip("展开 / 隐藏导航")
        sidebar.clicked.connect(self.window._toggle_sidebar)
        layout.addWidget(sidebar)

        brand = QLabel("自动化工作台")
        brand.setFont(QFont("Segoe UI", 14, QFont.Normal))
        brand.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        layout.addWidget(brand)

        subtitle = QLabel("今日任务 · 自动化 · 每一步都有进展")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet(f"color: {C_TEXT_SECONDARY}; background: transparent;")
        layout.addWidget(subtitle)

        layout.addStretch()

        self._add_window_btn(layout, "–", self.window._minimize_window)
        self._add_window_btn(layout, "□", self.window._toggle_fullscreen)
        self._add_window_btn(layout, "×", self.window.close)

    def _add_window_btn(self, layout, text, slot):
        btn = QPushButton(text)
        label = {"–": "最小化", "□": "全屏 / 恢复窗口", "×": "关闭工作台"}.get(text, text)
        btn.setToolTip(label)
        btn.setAccessibleName(label)
        btn.setFixedSize(36, 36)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C_TEXT_SECONDARY};
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: 400;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {C_HOVER};
                color: {C_TEXT};
            }}
        """)
        btn.clicked.connect(slot)
        layout.addWidget(btn, 0, Qt.AlignVCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window.windowHandle().startSystemMove()


# ============================================================
# 步骤编辑弹窗
# ============================================================
class StepEditDialog(QDialog):
    def __init__(self, step: dict, parent=None):
        super().__init__(parent)
        self.step = step
        self.config = step.get("config", {})
        self.config_widgets = {}
        self.setWindowTitle("编辑步骤")
        self.setMinimumSize(620, 520)
        self.setModal(True)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)

        title = QLabel("编辑步骤")
        title.setFont(QFont("Segoe UI", 22, QFont.Normal))
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        add_shadow(card)
        form = QFormLayout(card)
        form.setContentsMargins(22, 22, 22, 22)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)

        self.name_edit = QLineEdit(self.step.get("name", ""))
        form.addRow("名称", self.name_edit)

        self.type_combo = QComboBox()
        for t_id, t_name in EXECUTOR_TYPES:
            self.type_combo.addItem(t_name, t_id)
        idx = self.type_combo.findData(self.step.get("type", "wps_macro"))
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentIndexChanged.connect(self._rebuild_config)
        form.addRow("类型", self.type_combo)

        layout.addWidget(card)

        config_card = QFrame()
        config_card.setObjectName("Card")
        add_shadow(config_card)
        self.config_layout = QFormLayout(config_card)
        self.config_layout.setContentsMargins(22, 22, 22, 22)
        self.config_layout.setSpacing(14)
        self.config_layout.setLabelAlignment(Qt.AlignRight)
        layout.addWidget(config_card, 1)

        self._rebuild_config()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton("取消")
        cancel.setObjectName("SecondaryBtn")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("保存")
        save.setObjectName("PrimaryBtn")
        save.clicked.connect(self._save)
        btn_row.addWidget(save)

        layout.addLayout(btn_row)

    def _rebuild_config(self):
        while self.config_layout.count():
            item = self.config_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.config_widgets.clear()
        step_type = self.type_combo.currentData()
        fields = EXECUTOR_CONFIG_FIELDS.get(step_type, [])

        for field_name, label, hint in fields:
            old_val = self.config.get(field_name, "")
            if isinstance(old_val, list):
                old_val = ", ".join(str(x) for x in old_val)
            elif isinstance(old_val, bool):
                old_val = "true" if old_val else "false"

            edit = QLineEdit(str(old_val) if old_val else "")
            edit.setPlaceholderText(hint)
            self.config_widgets[field_name] = edit

            if field_name in ("workbook", "script"):
                row = QHBoxLayout()
                row.setSpacing(8)
                row.addWidget(edit)
                btn = QPushButton("浏览")
                btn.setFixedHeight(38)
                btn.clicked.connect(lambda checked=False, w=edit: self._browse_file(w))
                row.addWidget(btn)
                box = QWidget()
                box.setLayout(row)
                self.config_layout.addRow(label, box)
            elif field_name in ("source_dir", "dest_dir", "save_dir"):
                row = QHBoxLayout()
                row.setSpacing(8)
                row.addWidget(edit)
                btn = QPushButton("浏览")
                btn.setFixedHeight(38)
                btn.clicked.connect(lambda checked=False, w=edit: self._browse_dir(w))
                row.addWidget(btn)
                box = QWidget()
                box.setLayout(row)
                self.config_layout.addRow(label, box)
            else:
                self.config_layout.addRow(label, edit)

    def _browse_file(self, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if path:
            edit.setText(path)

    def _browse_dir(self, edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            edit.setText(path)

    def _save(self):
        self.step["name"] = self.name_edit.text().strip()
        self.step["type"] = self.type_combo.currentData()

        new_config = {}
        for field_name, widget in self.config_widgets.items():
            raw = widget.text().strip()
            if not raw:
                continue
            if raw.lower() == "true":
                new_config[field_name] = True
            elif raw.lower() == "false":
                new_config[field_name] = False
            elif field_name in ("args", "keywords"):
                new_config[field_name] = [x.strip() for x in raw.split(",") if x.strip()]
            else:
                new_config[field_name] = raw

        self.step["config"] = new_config
        self.accept()


# ============================================================
# 主窗口
# ============================================================
class ConfigApp(QMainWindow):
    _theme = DEFAULT_THEME

    def __init__(self):
        super().__init__()
        self.setWindowTitle("自动化工作台")
        self.setMinimumSize(860, 680)
        self.resize(1240, 820)
        self.setWindowFlags(Qt.FramelessWindowHint)

        self._maximized = False
        self._normal_geometry = None
        self._edge = 8

        self.workflows: List[dict] = []
        self.modified = False

        self._load_theme_pref()
        apply_theme(QApplication.instance(), self._theme)

        QApplication.instance().installEventFilter(self)

        self._build_ui()
        self._load_workflows()
        self._refresh_list()
        self._switch_page('routine_page')

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _minimize_window(self):
        # Windows frameless fullscreen windows need to leave fullscreen first.
        if self.isFullScreen():
            self.showNormal()
        QTimer.singleShot(0, self.showMinimized)

    def _toggle_sidebar(self):
        hidden = self._nav.isVisible()
        self._nav.setVisible(not hidden)
        self.routine_page.store.set_setting('sidebar_hidden', 'yes' if hidden else 'no')

    def _toggle_maximize(self):
        if self._maximized:
            self._maximized = False
            if self._normal_geometry:
                self.setGeometry(self._normal_geometry)
            self.showNormal()
        else:
            self._normal_geometry = self.geometry()
            self._maximized = True
            screen = self.screen().availableGeometry()
            margin = 6
            self.setGeometry(
                screen.x() + margin,
                screen.y() + margin,
                screen.width() - margin * 2,
                screen.height() - margin * 2,
            )

    def eventFilter(self, obj, event):
        et = event.type()

        # 拦截日期/下拉/数字框的滚轮事件，防止鼠标滑过误改值
        if et == QEvent.Wheel:
            if isinstance(obj, (QDateEdit, QComboBox, QSpinBox, QDoubleSpinBox)):
                return True

        # 无边框窗口边缘拖拽缩放
        if et in (QEvent.MouseMove, QEvent.MouseButtonPress):
            if self._handle_edge_event(event, et):
                return True

        return super().eventFilter(obj, event)

    def _handle_edge_event(self, event, et) -> bool:
        if self._maximized or not self.isVisible():
            return False

        g = self.geometry()
        e = self._edge
        gp = event.globalPosition().toPoint()

        near = g.adjusted(-e, -e, e, e).contains(gp)
        if not near:
            if et == QEvent.MouseMove and event.buttons() == Qt.NoButton:
                self.setCursor(Qt.ArrowCursor)
            return False

        left = abs(gp.x() - g.left()) <= e
        right = abs(gp.x() - g.right()) <= e
        top = abs(gp.y() - g.top()) <= e
        bottom = abs(gp.y() - g.bottom()) <= e

        edges = Qt.Edges()
        if left:
            edges |= Qt.LeftEdge
        if right:
            edges |= Qt.RightEdge
        if top:
            edges |= Qt.TopEdge
        if bottom:
            edges |= Qt.BottomEdge
        if not edges:
            return False

        if et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            wh = self.windowHandle()
            if wh:
                wh.startSystemResize(edges)
                return True
        elif et == QEvent.MouseMove and event.buttons() == Qt.NoButton:
            h = left or right
            v = top or bottom
            if h and v:
                shape = Qt.SizeFDiagCursor if (left == top) else Qt.SizeBDiagCursor
            elif h:
                shape = Qt.SizeHorCursor
            else:
                shape = Qt.SizeVerCursor
            self.setCursor(shape)

        return False

    def _load_theme_pref(self):
        import configparser
        cp = configparser.ConfigParser()
        cp.read(str(PROJECT_DIR / "config" / "settings.ini"), encoding="utf-8")
        if cp.has_option("ui", "theme"):
            val = cp.get("ui", "theme")
            self._theme = val if val in THEMES else DEFAULT_THEME

    def set_theme(self, name: str):
        if self.modified:
            QMessageBox.information(self, '先保存配置', '请先保存工作流修改，再切换外观。')
            return
        page_index = self.page_stack.currentIndex()
        self._theme = name
        apply_theme(QApplication.instance(), name)

        import configparser
        cp = configparser.ConfigParser()
        cp["ui"] = {"theme": name}
        (PROJECT_DIR / "config").mkdir(exist_ok=True)
        with open(PROJECT_DIR / "config" / "settings.ini", "w", encoding="utf-8") as f:
            cp.write(f)

        for timer in self._central.findChildren(QTimer):
            timer.stop()
        self._build_ui()
        self._refresh_list()
        self._switch_page(['workflow_page', 'todo_page', 'routine_page'][page_index])

    def _build_ui(self):
        self._central = QWidget()
        self._central.setObjectName('AppRoot')
        self.setCentralWidget(self._central)

        outer = QVBoxLayout(self._central)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        self._central.setStyleSheet(f"#AppRoot {{ background: {C_BORDER}; }}")

        inner = QWidget()
        inner.setObjectName("MainContent")
        inner.setStyleSheet(f"#MainContent {{ background: {C_BG}; }}")
        outer.addWidget(inner)

        root = QVBoxLayout(inner)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.title_bar = CustomTitleBar(self)
        root.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        self._nav = QFrame()
        self._nav.setObjectName("NavPanel")
        self._nav.setFixedWidth(176)
        self._nav.setStyleSheet(f"""
            #NavPanel {{
                background: {C_CARD};
                border-right: 1px solid {C_BORDER};
            }}
        """)
        nav_layout = QVBoxLayout(self._nav)
        nav_layout.setContentsMargins(12, 18, 12, 18)
        nav_layout.setSpacing(6)

        self.nav_buttons = []
        brand = QLabel('WORKBENCH')
        brand.setStyleSheet(f'color:{C_TEXT};font-size:15px;padding:8px 8px 20px;background:transparent;')
        nav_layout.addWidget(brand)
        nav_items = [
            ("◎", "今日任务", "routine_page"),
            ("◇", "自动化配置", "workflow_page"),
        ]

        for icon, label, page_id in nav_items:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setObjectName("NavBtn")
            btn.setFixedHeight(44)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("active", page_id == "workflow_page")
            btn.clicked.connect(lambda checked=False, pid=page_id: self._switch_page(pid))
            nav_layout.addWidget(btn)
            self.nav_buttons.append((btn, page_id))

        nav_layout.addStretch()

        settings_btn = QPushButton("  设置")
        settings_btn.setObjectName("NavBtn")
        settings_btn.setFixedHeight(44)
        settings_btn.clicked.connect(lambda: self.routine_page.settings())
        nav_layout.addWidget(settings_btn)

        body.addWidget(self._nav)

        self.page_stack = QStackedWidget()
        self.workflow_page = self._build_workflow_page()
        self.page_stack.addWidget(self.workflow_page)

        self.todo_page = QWidget()  # 保留旧页面索引；任务统一到今日任务
        self.page_stack.addWidget(self.todo_page)

        from pasture_page import PasturePage
        self.routine_page = PasturePage(self._theme)
        self.page_stack.addWidget(self.routine_page)
        self._nav.setVisible(self.routine_page.store.setting('sidebar_hidden', 'no') != 'yes')

        body.addWidget(self.page_stack, 1)

        make_text_selectable(self._central)

    def _switch_page(self, page_id: str):
        page_index = {
            "workflow_page": 0,
            "todo_page": 1,
            "routine_page": 2,
        }
        self.page_stack.setCurrentIndex(page_index.get(page_id, 0))
        for btn, pid in self.nav_buttons:
            btn.setProperty("active", pid == page_id)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _build_workflow_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setStyleSheet(f"background: {C_BG};")
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(24, 18, 24, 18)
        tl.setSpacing(10)

        title = QLabel("🛠️ 工作流配置")
        title.setFont(QFont("Segoe UI", 20, QFont.Normal))
        tl.addWidget(title)
        tl.addStretch()

        self.save_btn = QPushButton("保存全部")
        self.save_btn.setObjectName("PrimaryBtn")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_all)
        tl.addWidget(self.save_btn)

        reload_btn = QPushButton("重新加载")
        reload_btn.setObjectName("SecondaryBtn")
        reload_btn.clicked.connect(self._reload)
        tl.addWidget(reload_btn)

        layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        layout.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(24, 14, 12, 16)
        left_layout.setSpacing(10)

        left_label = QLabel("工作流列表")
        left_label.setFont(QFont("Segoe UI", 16, QFont.Normal))
        left_layout.addWidget(left_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for text, slot in [
            ("+ 新建", self._add_wf),
            ("- 删除", self._delete_wf),
            ("重命名", self._rename_wf),
        ]:
            btn = QPushButton(text)
            btn.setMinimumHeight(36)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        left_layout.addLayout(btn_row)

        self.wf_list = QTreeWidget()
        self.wf_list.setHeaderHidden(True)
        self.wf_list.setRootIsDecorated(False)
        self.wf_list.currentItemChanged.connect(self._on_wf_changed)
        left_layout.addWidget(self.wf_list)

        splitter.addWidget(left)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)

        self.edit_widget = QWidget()
        self.edit_layout = QVBoxLayout(self.edit_widget)
        self.edit_layout.setContentsMargins(14, 14, 24, 14)
        self.edit_layout.setSpacing(16)
        self._show_empty_hint()

        right_scroll.setWidget(self.edit_widget)
        splitter.addWidget(right_scroll)
        splitter.setSizes([340, 840])

        return page

    def _show_empty_hint(self):
        self._clear_edit_layout()
        hint = QLabel("← 选择一个工作流开始编辑")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 17px; font-weight: 400;")
        self.edit_layout.addStretch()
        self.edit_layout.addWidget(hint)
        self.edit_layout.addStretch()

    def _clear_edit_layout(self):
        while self.edit_layout.count():
            item = self.edit_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _load_workflows(self):
        self.workflows = []
        if WORKFLOWS_DIR.exists():
            for yf in sorted(WORKFLOWS_DIR.glob("*.yaml")):
                try:
                    with open(yf, "r", encoding="utf-8") as f:
                        wf = yaml.safe_load(f) or {}
                    wf["_file"] = str(yf)
                    wf["_filename"] = yf.name
                    self.workflows.append(wf)
                except Exception as e:
                    print(f"Load error: {yf} -> {e}")

    def _refresh_list(self):
        self.wf_list.clear()
        for wf in self.workflows:
            name = wf.get("name", "未命名")
            steps = len(wf.get("steps", []))
            item = QTreeWidgetItem([f"  {name}    {steps} 步骤"])
            item.setData(0, Qt.UserRole, wf)
            self.wf_list.addTopLevelItem(item)

    def _reload(self):
        if self.modified:
            if QMessageBox.question(self, "确认", "有未保存修改，确定丢弃吗？") != QMessageBox.Yes:
                return
        self._load_workflows()
        self._refresh_list()
        self._show_empty_hint()
        self.set_modified(False)

    def _on_wf_changed(self, current, previous):
        if current:
            self._build_edit_view(current.data(0, Qt.UserRole))

    def _add_wf(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "新建工作流", "输入工作流名称:")
        if not ok or not name.strip():
            return

        safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name.strip())
        wf = {
            "name": name.strip(),
            "description": "",
            "trigger": {"type": "manual"},
            "tags": [],
            "steps": [],
            "_file": str(WORKFLOWS_DIR / f"{safe}.yaml"),
            "_filename": f"{safe}.yaml",
        }
        self.workflows.append(wf)
        self._refresh_list()
        self.wf_list.setCurrentItem(self.wf_list.topLevelItem(len(self.workflows) - 1))
        self.set_modified(True)

    def _delete_wf(self):
        current = self.wf_list.currentItem()
        if not current:
            return
        wf = current.data(0, Qt.UserRole)
        if QMessageBox.question(self, "确认删除", f"确定删除「{wf.get('name')}」吗？") != QMessageBox.Yes:
            return
        self.workflows.remove(wf)
        self._refresh_list()
        self._show_empty_hint()
        self.set_modified(True)

    def _rename_wf(self):
        current = self.wf_list.currentItem()
        if not current:
            return
        wf = current.data(0, Qt.UserRole)
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "重命名", "新名称:", text=wf.get("name", ""))
        if not ok or not name.strip():
            return
        wf["name"] = name.strip()
        self._refresh_list()
        self.set_modified(True)

    def _build_edit_view(self, wf: dict):
        self._clear_edit_layout()

        info = QFrame()
        info.setObjectName("Card")
        add_shadow(info, self._theme)
        form = QFormLayout(info)
        form.setContentsMargins(24, 22, 24, 22)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)

        self.var_name = QLineEdit(wf.get("name", ""))
        self.var_name.textChanged.connect(lambda: self._on_change("name"))
        form.addRow("名称", self.var_name)

        self.var_desc = QTextEdit()
        self.var_desc.setMaximumHeight(86)
        self.var_desc.setPlainText(wf.get("description", ""))
        self.var_desc.textChanged.connect(lambda: self._on_change("description"))
        form.addRow("描述", self.var_desc)

        self.var_tags = QLineEdit(", ".join(wf.get("tags", [])))
        self.var_tags.textChanged.connect(lambda: self._on_change("tags"))
        form.addRow("标签", self.var_tags)

        self.edit_layout.addWidget(info)

        tr_card = QFrame()
        tr_card.setObjectName("Card")
        add_shadow(tr_card, self._theme)
        tr_form = QFormLayout(tr_card)
        tr_form.setContentsMargins(24, 22, 24, 22)
        tr_form.setSpacing(14)
        tr_form.setLabelAlignment(Qt.AlignRight)

        tr = wf.get("trigger", {})
        self.var_tr_type = QComboBox()
        for t_id, t_name in TRIGGER_TYPES:
            self.var_tr_type.addItem(t_name, t_id)
        idx = self.var_tr_type.findData(tr.get("type", "manual"))
        if idx >= 0:
            self.var_tr_type.setCurrentIndex(idx)
        self.var_tr_type.currentIndexChanged.connect(lambda: self._on_change("trigger"))
        tr_form.addRow("触发方式", self.var_tr_type)

        self.var_tr_path = QLineEdit(tr.get("path", ""))
        self.var_tr_path.textChanged.connect(lambda: self._on_change("trigger"))
        path_row = QHBoxLayout()
        path_row.addWidget(self.var_tr_path)
        browse = QPushButton("浏览")
        browse.setFixedHeight(38)
        browse.clicked.connect(lambda: self._browse_dir(self.var_tr_path))
        path_row.addWidget(browse)
        box = QWidget()
        box.setLayout(path_row)
        tr_form.addRow("监控路径", box)

        self.var_tr_pattern = QLineEdit(tr.get("pattern", "*"))
        self.var_tr_pattern.textChanged.connect(lambda: self._on_change("trigger"))
        tr_form.addRow("文件匹配", self.var_tr_pattern)

        self.var_tr_filter = QLineEdit(tr.get("filter", ""))
        self.var_tr_filter.setPlaceholderText("如 COSCO|账单")
        self.var_tr_filter.textChanged.connect(lambda: self._on_change("trigger"))
        tr_form.addRow("名称过滤", self.var_tr_filter)

        self.edit_layout.addWidget(tr_card)

        st_card = QFrame()
        st_card.setObjectName("Card")
        add_shadow(st_card, self._theme)
        st_layout = QVBoxLayout(st_card)
        st_layout.setContentsMargins(24, 22, 24, 22)
        st_layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("步骤列表")
        title.setFont(QFont("Segoe UI", 16, QFont.Normal))
        header.addWidget(title)
        header.addStretch()

        for text, slot in [
            ("+ 添加", self._step_add),
            ("- 删除", self._step_del),
            ("↑ 上移", self._step_up),
            ("↓ 下移", self._step_down),
        ]:
            btn = QPushButton(text)
            btn.setFixedHeight(36)
            btn.clicked.connect(slot)
            header.addWidget(btn)

        st_layout.addLayout(header)

        self.step_tree = QTreeWidget()
        self.step_tree.setHeaderLabels(["#", "步骤名称", "执行器", "关键配置"])
        self.step_tree.setColumnWidth(0, 46)
        self.step_tree.setColumnWidth(1, 180)
        self.step_tree.setColumnWidth(2, 120)
        self.step_tree.setMinimumHeight(220)
        self.step_tree.itemDoubleClicked.connect(self._step_edit)
        self._refresh_steps(wf)

        st_layout.addWidget(self.step_tree)
        self.edit_layout.addWidget(st_card)
        self.edit_layout.addStretch()

    def _selected_step(self) -> Optional[dict]:
        current = self.wf_list.currentItem()
        if not current:
            return None
        wf = current.data(0, Qt.UserRole)
        sel = self.step_tree.currentItem()
        if not sel:
            return None
        idx = sel.data(0, Qt.UserRole)
        return wf["steps"][idx]

    def _refresh_steps(self, wf: dict):
        self.step_tree.clear()
        for i, s in enumerate(wf.get("steps", [])):
            cfg = s.get("config", {})
            st = s.get("type", "")
            summary = ""
            if st == "wps_macro":
                summary = f"文件: {Path(cfg.get('workbook', '')).name}  宏: {cfg.get('macro', '')}"
            elif st == "run_python":
                summary = f"脚本: {Path(cfg.get('script', '')).name}"
            elif st == "email_download":
                summary = f"关键词: {','.join(cfg.get('keywords', []))}"
            elif st == "file_ops":
                summary = f"操作: {cfg.get('action', '')}"
            item = QTreeWidgetItem([str(i + 1), s.get("name", ""), st, summary])
            item.setData(0, Qt.UserRole, i)
            self.step_tree.addTopLevelItem(item)

    def _step_add(self):
        current = self.wf_list.currentItem()
        if not current:
            return
        wf = current.data(0, Qt.UserRole)
        wf.setdefault("steps", [])
        wf["steps"].append({
            "name": f"步骤{len(wf['steps']) + 1}",
            "type": "wps_macro",
            "config": {},
        })
        self._refresh_steps(wf)
        self.set_modified(True)

    def _step_del(self):
        current = self.wf_list.currentItem()
        if not current:
            return
        wf = current.data(0, Qt.UserRole)
        step = self._selected_step()
        if step:
            wf["steps"].remove(step)
            self._refresh_steps(wf)
            self.set_modified(True)

    def _step_up(self):
        current = self.wf_list.currentItem()
        if not current:
            return
        wf = current.data(0, Qt.UserRole)
        sel = self.step_tree.currentItem()
        if not sel:
            return
        idx = sel.data(0, Qt.UserRole)
        if idx <= 0:
            return
        wf["steps"][idx], wf["steps"][idx - 1] = wf["steps"][idx - 1], wf["steps"][idx]
        self._refresh_steps(wf)
        self.set_modified(True)

    def _step_down(self):
        current = self.wf_list.currentItem()
        if not current:
            return
        wf = current.data(0, Qt.UserRole)
        sel = self.step_tree.currentItem()
        if not sel:
            return
        idx = sel.data(0, Qt.UserRole)
        if idx >= len(wf["steps"]) - 1:
            return
        wf["steps"][idx], wf["steps"][idx + 1] = wf["steps"][idx + 1], wf["steps"][idx]
        self._refresh_steps(wf)
        self.set_modified(True)

    def _step_edit(self, item, col):
        current = self.wf_list.currentItem()
        if not current:
            return
        wf = current.data(0, Qt.UserRole)
        idx = item.data(0, Qt.UserRole)
        dialog = StepEditDialog(wf["steps"][idx], self)
        if dialog.exec():
            self._refresh_steps(wf)
            self.set_modified(True)

    def _save_all(self):
        WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
        for wf in self.workflows:
            file_path = Path(wf.get("_file", ""))
            clean = {
                "name": wf.get("name", ""),
                "description": wf.get("description", ""),
                "trigger": wf.get("trigger", {}),
                "tags": wf.get("tags", []),
                "steps": wf.get("steps", []),
            }
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.dump(clean, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            except Exception as e:
                QMessageBox.critical(self, "保存错误", f"保存 {file_path.name} 失败:\n{e}")
                return

        self.set_modified(False)
        self._refresh_list()
        QMessageBox.information(self, "保存成功", "所有工作流已保存。")

    def _on_change(self, field: str):
        current = self.wf_list.currentItem()
        if not current:
            return
        wf = current.data(0, Qt.UserRole)

        if field == "name":
            wf["name"] = self.var_name.text()
        elif field == "description":
            wf["description"] = self.var_desc.toPlainText()
        elif field == "tags":
            wf["tags"] = [x.strip() for x in self.var_tags.text().split(",") if x.strip()]
        elif field == "trigger":
            wf["trigger"] = {
                "type": self.var_tr_type.currentData(),
                "path": self.var_tr_path.text(),
                "pattern": self.var_tr_pattern.text(),
                "filter": self.var_tr_filter.text(),
            }

        self.set_modified(True)

    def set_modified(self, m: bool):
        self.modified = m
        self.save_btn.setEnabled(m)

    def _browse_dir(self, edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            edit.setText(path)


def main():
    app = QApplication(sys.argv)
    icon_path=PROJECT_DIR/'assets'/'workbench_shortcut_v1.ico'
    app.setWindowIcon(QIcon(str(icon_path)) if icon_path.exists() else _create_app_icon())
    window = ConfigApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
