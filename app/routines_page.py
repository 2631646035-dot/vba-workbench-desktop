"""
周期事项 v1.0 — 每日 / 每周 / 每月 例行事项管理

功能：
1. 三种周期：每日（每天打开就展示）、每周（指定星期几）、每月（指定几号）
2. 卡片视图 / 列表视图 可切换
3. 标签系统：负责人、跟进人、供应商等，直接显示在卡片上
4. 今日完成勾选：按日期记录，隔天自动重置
5. 到期提醒：应用内弹窗（可扩展微信/邮件通知，暂存配置）
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLineEdit, QComboBox, QCheckBox, QDialog, QTextEdit,
    QMessageBox, QSizePolicy, QLayout, QGridLayout, QSpacerItem,
)
from PySide6.QtCore import Qt, QTimer, QDate, QRect, QSize, QPoint, Signal
from PySide6.QtGui import QColor, QFont

try:
    from config_app_v2 import THEMES, DEFAULT_THEME
except Exception:
    import __main__ as main_mod
    THEMES = main_mod.THEMES
    DEFAULT_THEME = main_mod.DEFAULT_THEME

PROJECT_DIR = Path(__file__).parent
ROUTINE_FILE = PROJECT_DIR / "config" / "routines.json"

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

REPEAT_TYPES = [
    ("daily", "每日"),
    ("weekly", "每周"),
    ("monthly", "每月"),
]

# 标签 key -> 主题色键
TAG_COLOR_KEYS = {
    "负责人": "blue",
    "跟进人": "green",
    "供应商": "orange",
    "客户": "red",
}


def _p(theme_name: str) -> dict:
    return THEMES.get(theme_name, THEMES[DEFAULT_THEME])


# ============================================================
# 存储层
# ============================================================
def load_routines() -> List[dict]:
    if ROUTINE_FILE.exists():
        try:
            raw = json.loads(ROUTINE_FILE.read_text(encoding="utf-8"))
            routines = []
            for r in raw:
                r.setdefault("id", f"r_{datetime.now().timestamp()}")
                r.setdefault("title", "")
                r.setdefault("repeat", "daily")
                r.setdefault("weekdays", [])
                r.setdefault("month_days", [])
                r.setdefault("tags", [])
                r.setdefault("note", "")
                r.setdefault("enabled", True)
                r.setdefault("notify", ["app"])
                r.setdefault("check_log", {})
                r.setdefault("created_at", datetime.now().isoformat())
                routines.append(r)
            return routines
        except Exception:
            return []
    return []


def save_routines(routines: List[dict]):
    ROUTINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    clean = []
    for r in routines:
        item = {k: v for k, v in r.items() if not k.startswith("_")}
        clean.append(item)
    temporary = ROUTINE_FILE.with_suffix('.json.tmp')
    temporary.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(ROUTINE_FILE)


# ============================================================
# 周期逻辑
# ============================================================
def is_due_today(r: dict, today: QDate = None) -> bool:
    """今天是否需要处理该事项"""
    if not r.get("enabled", True):
        return False
    today = today or QDate.currentDate()
    rep = r.get("repeat", "daily")
    if rep == "daily":
        return True
    if rep == "weekly":
        return today.dayOfWeek() in (r.get("weekdays") or [])
    if rep == "monthly":
        return today.day() in (r.get("month_days") or [])
    return False


def is_done_today(r: dict, today_str: str = None) -> bool:
    """今天是否已完成"""
    today_str = today_str or QDate.currentDate().toString("yyyy-MM-dd")
    log = r.get("check_log") or {}
    rec = log.get(today_str) or {}
    return bool(rec.get("done"))


def repeat_text(r: dict) -> str:
    """周期的中文描述"""
    rep = r.get("repeat", "daily")
    if rep == "daily":
        return "每天"
    if rep == "weekly":
        wd = r.get("weekdays") or []
        if not wd:
            return "每周（未设置）"
        if len(wd) == 7:
            return "每天"
        return "每周" + "、".join(WEEKDAY_NAMES[d - 1] for d in sorted(wd))
    if rep == "monthly":
        md = r.get("month_days") or []
        if not md:
            return "每月（未设置）"
        return "每月" + "、".join(f"{d}号" for d in sorted(md))
    return "每天"


def _rgba(hex_color: str, alpha: int) -> str:
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def _chip_style(color_hex: str, pal: dict) -> str:
    """标签小圆角底片样式：浅色底 + 彩色字"""
    return f"""
        QLabel {{
            color: {color_hex};
            background: {_rgba(color_hex, 26)};
            border: 1px solid {_rgba(color_hex, 60)};
            border-radius: 10px;
            padding: 3px 10px;
            font-size: 12px;
            font-weight: 400;
        }}
    """


def _badge_style(bg_hex: str, text_hex: str) -> str:
    return f"""
        QLabel {{
            color: {text_hex};
            background: {bg_hex};
            border: none;
            border-radius: 9px;
            padding: 3px 10px;
            font-size: 12px;
            font-weight: 400;
        }}
    """


# ============================================================
# 流式布局（每月 31 天按钮换行用）
# ============================================================
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = effective.x(), effective.y()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + m.bottom()


# ============================================================
# 切换小按钮（星期/日期/视图切换用）
# ============================================================
class ChipButton(QPushButton):
    def __init__(self, text: str, pal: dict, checked: bool = False, min_w: int = 44):
        super().__init__(text)
        self.pal = pal
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(min_w, 30)
        self._apply()

    def _apply(self):
        if self.isChecked():
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {self.pal['primary']};
                    color: #FFFFFF;
                    border: 1px solid {self.pal['primary']};
                    border-radius: 8px;
                    padding: 4px 8px;
                    font-size: 13px;
                    font-weight: 400;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {self.pal['surface']};
                    color: {self.pal['text']};
                    border: 1.5px solid {self.pal['input_border']};
                    border-radius: 8px;
                    padding: 4px 8px;
                    font-size: 13px;
                    font-weight: 400;
                }}
                QPushButton:hover {{
                    border-color: {self.pal['primary']};
                }}
            """)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._apply()


# ============================================================
# 标签编辑行
# ============================================================
class TagEditRow(QWidget):
    deleted = Signal(object)

    def __init__(self, key: str = "", value: str = "", pal: dict = None, parent=None):
        super().__init__(parent)
        self.pal = pal or _p(DEFAULT_THEME)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.key_combo = QComboBox()
        self.key_combo.setEditable(True)
        self.key_combo.addItems(["负责人", "跟进人", "供应商", "客户"])
        if key:
            self.key_combo.setCurrentText(key)
        self.key_combo.setFixedWidth(130)
        lay.addWidget(self.key_combo)

        self.value_edit = QLineEdit(value)
        self.value_edit.setPlaceholderText("内容，如：胡总 / COSCO")
        lay.addWidget(self.value_edit, 1)

        del_btn = QPushButton("×")
        del_btn.setFixedSize(30, 30)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                color: {self.pal['secondary']};
                background: transparent;
                border: none;
                border-radius: 15px;
                font-size: 16px;
                font-weight: 400;
            }}
            QPushButton:hover {{
                background: {self.pal['danger_bg']};
                color: {self.pal['danger_text']};
            }}
        """)
        del_btn.clicked.connect(lambda: self.deleted.emit(self))
        lay.addWidget(del_btn)

    def tag(self) -> dict:
        return {
            "key": self.key_combo.currentText().strip(),
            "value": self.value_edit.text().strip(),
        }


# ============================================================
# 新增/编辑 弹窗
# ============================================================
class RoutineEditDialog(QDialog):
    def __init__(self, data: dict, theme_name: str = DEFAULT_THEME, parent=None):
        super().__init__(parent)
        self.data = data
        self.theme_name = theme_name
        self.pal = _p(theme_name)
        self.tag_rows: List[TagEditRow] = []
        self.week_chips: List[ChipButton] = []
        self.day_chips: List[ChipButton] = []

        self.setWindowTitle("周期事项")
        self.setMinimumSize(640, 640)
        self._build()

    def _build(self):
        pal = self.pal

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(14)

        title = QLabel("编辑周期事项" if self.data.get("title") else "新增周期事项")
        title.setFont(QFont("Segoe UI", 21, QFont.Normal))
        layout.addWidget(title)

        # ---- 基本信息卡片 ----
        card1 = QFrame()
        card1.setObjectName("Card")
        card1.setStyleSheet(f"""
            #Card {{
                background: {pal['card']};
                border-radius: {pal['card_radius']}px;
                border: 1px solid {pal['border']};
            }}
        """)
        f1 = QGridLayout(card1)
        f1.setContentsMargins(22, 20, 22, 20)
        f1.setHorizontalSpacing(14)
        f1.setVerticalSpacing(12)

        lbl_title = QLabel("标题")
        lbl_title.setStyleSheet("font-size: 14px;")
        self.title_edit = QLineEdit(self.data.get("title", ""))
        self.title_edit.setPlaceholderText("例如：提醒胡总确认发货计划")
        f1.addWidget(lbl_title, 0, 0)
        f1.addWidget(self.title_edit, 0, 1)

        lbl_rep = QLabel("重复周期")
        lbl_rep.setStyleSheet("font-size: 14px;")
        self.repeat_combo = QComboBox()
        for rid, rname in REPEAT_TYPES:
            self.repeat_combo.addItem(rname, rid)
        idx = self.repeat_combo.findData(self.data.get("repeat", "daily"))
        if idx >= 0:
            self.repeat_combo.setCurrentIndex(idx)
        self.repeat_combo.currentIndexChanged.connect(self._on_repeat_changed)
        f1.addWidget(lbl_rep, 1, 0)
        f1.addWidget(self.repeat_combo, 1, 1)

        lbl_week = QLabel("每周几")
        lbl_week.setStyleSheet("font-size: 14px;")
        self.week_widget = QWidget()
        wl = FlowLayout(self.week_widget, spacing=6)
        for i, name in enumerate(WEEKDAY_NAMES, start=1):
            chip = ChipButton(name, pal, checked=i in (self.data.get("weekdays") or []))
            self.week_chips.append(chip)
            wl.addWidget(chip)
        f1.addWidget(lbl_week, 2, 0)
        f1.addWidget(self.week_widget, 2, 1)

        lbl_day = QLabel("每月几号")
        lbl_day.setStyleSheet("font-size: 14px;")
        self.day_widget = QWidget()
        dl = FlowLayout(self.day_widget, spacing=6)
        for d in range(1, 32):
            chip = ChipButton(f"{d}", pal, checked=d in (self.data.get("month_days") or []), min_w=38)
            self.day_chips.append(chip)
            dl.addWidget(chip)
        f1.addWidget(lbl_day, 3, 0)
        f1.addWidget(self.day_widget, 3, 1)

        self.enabled_check = QCheckBox("启用该事项")
        self.enabled_check.setChecked(self.data.get("enabled", True))
        f1.addWidget(self.enabled_check, 4, 1)

        layout.addWidget(card1)

        # ---- 标签卡片 ----
        card2 = QFrame()
        card2.setObjectName("Card")
        card2.setStyleSheet(card1.styleSheet())
        v2 = QVBoxLayout(card2)
        v2.setContentsMargins(22, 18, 22, 18)
        v2.setSpacing(10)

        tags_header = QHBoxLayout()
        tags_title = QLabel("标签（负责人 / 跟进人 / 供应商等，显示在卡片上）")
        tags_title.setStyleSheet("font-size: 14px;")
        tags_header.addWidget(tags_title)
        tags_header.addStretch()
        add_tag_btn = QPushButton("+ 添加标签")
        add_tag_btn.setCursor(Qt.PointingHandCursor)
        add_tag_btn.setStyleSheet(f"""
            QPushButton {{
                color: {pal['primary']};
                background: transparent;
                border: 1.5px dashed {pal['input_border']};
                border-radius: 8px;
                padding: 5px 12px;
                font-size: 13px;
                font-weight: 400;
            }}
            QPushButton:hover {{
                border-color: {pal['primary']};
                background: {pal['hover']};
            }}
        """)
        add_tag_btn.clicked.connect(lambda: self._add_tag_row())
        tags_header.addWidget(add_tag_btn)
        v2.addLayout(tags_header)

        self.tags_container = QWidget()
        self.tags_layout = QVBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(8)
        v2.addWidget(self.tags_container)

        for tag in (self.data.get("tags") or []):
            self._add_tag_row(tag.get("key", ""), tag.get("value", ""))

        layout.addWidget(card2)

        # ---- 提醒方式卡片 ----
        card3 = QFrame()
        card3.setObjectName("Card")
        card3.setStyleSheet(card1.styleSheet())
        v3 = QVBoxLayout(card3)
        v3.setContentsMargins(22, 16, 22, 16)
        v3.setSpacing(10)

        notify_title = QLabel("到期提醒方式")
        notify_title.setStyleSheet("font-size: 14px;")
        v3.addWidget(notify_title)

        notify_row = QHBoxLayout()
        notify_row.setSpacing(20)
        self.notify_checks = {}
        notify_items = [
            ("app", "应用内弹窗"),
            ("wechat", "微信通知"),
            ("mail", "邮件通知"),
        ]
        saved_notify = self.data.get("notify") or ["app"]
        for nid, nname in notify_items:
            cb = QCheckBox(nname)
            cb.setChecked(nid in saved_notify)
            self.notify_checks[nid] = cb
            notify_row.addWidget(cb)
        notify_row.addStretch()
        v3.addLayout(notify_row)

        hint = QLabel("微信 / 邮件通知需对应执行器配置完成后自动生效，现阶段以应用内弹窗为主。")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {pal['muted']}; font-size: 12px;")
        v3.addWidget(hint)

        layout.addWidget(card3)

        # ---- 备注 ----
        lbl_note = QLabel("备注")
        lbl_note.setStyleSheet("font-size: 14px;")
        layout.addWidget(lbl_note)
        self.note_edit = QTextEdit(self.data.get("note", ""))
        self.note_edit.setMaximumHeight(80)
        layout.addWidget(self.note_edit)

        # ---- 按钮 ----
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
        layout.addStretch()

        self._on_repeat_changed()

    def _on_repeat_changed(self):
        rep = self.repeat_combo.currentData()
        self.week_widget.setVisible(rep == "weekly")
        self.day_widget.setVisible(rep == "monthly")

    def _add_tag_row(self, key: str = "", value: str = ""):
        row = TagEditRow(key, value, self.pal, self.tags_container)
        row.deleted.connect(self._remove_tag_row)
        self.tags_layout.addWidget(row)
        self.tag_rows.append(row)

    def _remove_tag_row(self, row):
        if row in self.tag_rows:
            self.tag_rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    def _save(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请填写标题。")
            return

        rep = self.repeat_combo.currentData()
        if rep == "weekly" and not self._selected_weekdays():
            QMessageBox.warning(self, "提示", "每周事项请至少选择一个星期。")
            return
        if rep == "monthly" and not self._selected_days():
            QMessageBox.warning(self, "提示", "每月事项请至少选择一个日期。")
            return

        tags = [r.tag() for r in self.tag_rows if r.tag()["key"] and r.tag()["value"]]

        self.data["title"] = title
        self.data["repeat"] = rep
        self.data["weekdays"] = self._selected_weekdays()
        self.data["month_days"] = self._selected_days()
        self.data["tags"] = tags
        self.data["note"] = self.note_edit.toPlainText().strip()
        self.data["enabled"] = self.enabled_check.isChecked()
        self.data["notify"] = [nid for nid, cb in self.notify_checks.items() if cb.isChecked()] or ["app"]
        self.data.setdefault("check_log", {})

        self.accept()

    def _selected_weekdays(self) -> List[int]:
        return [i for i, chip in enumerate(self.week_chips, start=1) if chip.isChecked()]

    def _selected_days(self) -> List[int]:
        return [d for d, chip in enumerate(self.day_chips, start=1) if chip.isChecked()]


# ============================================================
# 周期事项卡片
# ============================================================
class RoutineCard(QFrame):
    toggled = Signal(dict)
    deleted = Signal(dict)
    clicked = Signal(dict)

    def __init__(self, data: dict, theme_name: str = DEFAULT_THEME, parent=None):
        super().__init__(parent)
        self.data = data
        self.theme_name = theme_name
        self.pal = _p(theme_name)
        self.setCursor(Qt.PointingHandCursor)
        self._build()

    def _build(self):
        pal = self.pal
        today = QDate.currentDate()
        today_str = today.toString("yyyy-MM-dd")
        due = is_due_today(self.data, today)
        done = is_done_today(self.data, today_str)
        enabled = self.data.get("enabled", True)

        main = QVBoxLayout(self)
        main.setContentsMargins(18, 14, 18, 14)
        main.setSpacing(8)

        # 顶部：勾选框 + 标题 + 删除
        top = QHBoxLayout()
        top.setSpacing(10)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(done)
        self.checkbox.setEnabled(due and enabled)
        self.checkbox.stateChanged.connect(self._on_toggle)
        top.addWidget(self.checkbox, 0, Qt.AlignTop)

        title_label = QLabel(self.data.get("title", ""))
        title_label.setWordWrap(True)
        if not enabled:
            title_color = pal["muted"]
        elif done:
            title_color = pal["muted"]
        else:
            title_color = pal["text"]
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {title_color};
                font-size: 15px;
                font-weight: 400;
                {'text-decoration: line-through;' if done else ''}
            }}
        """)
        top.addWidget(title_label, 1)
        title_label.installEventFilter(self)

        del_btn = QPushButton("×")
        del_btn.setFixedSize(28, 28)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                color: {pal['secondary']};
                background: transparent;
                border: none;
                border-radius: 14px;
                font-size: 16px;
                font-weight: 400;
            }}
            QPushButton:hover {{
                background: {pal['danger_bg']};
                color: {pal['danger_text']};
            }}
        """)
        del_btn.clicked.connect(self._on_delete)
        top.addWidget(del_btn, 0, Qt.AlignTop)

        main.addLayout(top)

        # 状态行：周期徽章 + 今日状态
        status = QHBoxLayout()
        status.setContentsMargins(34, 0, 0, 0)
        status.setSpacing(8)

        rep_badge = QLabel(repeat_text(self.data))
        rep_badge.setStyleSheet(_badge_style(pal["group"], pal["secondary"]))
        status.addWidget(rep_badge)

        if not enabled:
            badge = QLabel("已停用")
            badge.setStyleSheet(_badge_style(pal["group"], pal["muted"]))
            status.addWidget(badge)
        elif done:
            badge = QLabel("✓ 今日已完成")
            badge.setStyleSheet(_badge_style(_rgba(pal["green"], 26), pal["green"]))
            status.addWidget(badge)
        elif due:
            badge = QLabel("● 今日待处理")
            badge.setStyleSheet(_badge_style(_rgba(pal["red"], 26), pal["red"]))
            status.addWidget(badge)

        status.addStretch()
        main.addLayout(status)

        # 标签行
        tags = [t for t in (self.data.get("tags") or []) if t.get("key") and t.get("value")]
        if tags:
            tag_row = QHBoxLayout()
            tag_row.setContentsMargins(34, 0, 0, 0)
            tag_row.setSpacing(6)
            for t in tags:
                color_key = TAG_COLOR_KEYS.get(t["key"], "primary")
                chip = QLabel(f"{t['key']}: {t['value']}")
                chip.setStyleSheet(_chip_style(pal[color_key], pal))
                tag_row.addWidget(chip)
            tag_row.addStretch()
            main.addLayout(tag_row)

        # 备注
        note = self.data.get("note", "")
        if note:
            note_label = QLabel(note)
            note_label.setWordWrap(True)
            note_label.setStyleSheet(f"""
                QLabel {{
                    color: {pal['secondary']};
                    font-size: 12px;
                    padding-left: 34px;
                    background: transparent;
                }}
            """)
            main.addWidget(note_label)

        # 卡片样式：左侧彩条按今日状态着色
        if not enabled:
            accent = pal["separator"]
        elif done:
            accent = pal["green"]
        elif due:
            accent = pal["red"]
        else:
            accent = pal["separator"]

        self.setObjectName("RoutineCard")
        self.setStyleSheet(f"""
            #RoutineCard {{
                background: {pal['card']};
                border-radius: {pal['card_radius']}px;
                border: 1px solid {pal['border']};
                border-left: 4px solid {accent};
            }}
            #RoutineCard:hover {{
                border-color: {pal['primary']};
            }}
        """)

    def _on_toggle(self, state):
        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        log = self.data.setdefault("check_log", {})
        if state:
            log[today_str] = {"done": True, "time": datetime.now().isoformat()}
        else:
            log[today_str] = {"done": False, "time": datetime.now().isoformat()}
        self.toggled.emit(self.data)

    def _on_delete(self):
        self.deleted.emit(self.data)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            child = self.childAt(pos)
            if child is not self.checkbox and not isinstance(child, QPushButton):
                self.clicked.emit(self.data)
        super().mousePressEvent(event)


# ============================================================
# 周期事项页面
# ============================================================
class RoutinePage(QWidget):
    def __init__(self, theme_name: str = DEFAULT_THEME, parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.pal = _p(theme_name)
        self.routines: List[dict] = load_routines()
        self.view_mode = "card"
        self._reminded_ids = set()
        self._remind_date = ""

        self._build()
        self._refresh()

        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self._check_reminders)
        self.reminder_timer.start(60000)
        QTimer.singleShot(1200, self._check_reminders)

    # ---------- UI ----------
    def _build(self):
        pal = self.pal

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 左侧面板
        left = QFrame()
        left.setObjectName("RoutineLeftPanel")
        left.setFixedWidth(340)
        left.setStyleSheet(f"""
            #RoutineLeftPanel {{
                background: {pal['card']};
                border-right: 1px solid {pal['border']};
            }}
        """)

        lv = QVBoxLayout(left)
        lv.setContentsMargins(24, 24, 24, 24)
        lv.setSpacing(16)

        title = QLabel("周期事项")
        title.setFont(QFont("Segoe UI", 25, QFont.Normal))
        title.setStyleSheet(f"color: {pal['text']}; background: transparent;")
        lv.addWidget(title)

        today = QDate.currentDate()
        date_label = QLabel(
            f"今天 {today.month()}月{today.day()}日 {WEEKDAY_NAMES[today.dayOfWeek() - 1]}"
        )
        date_label.setStyleSheet(f"color: {pal['secondary']}; font-size: 13px; background: transparent;")
        lv.addWidget(date_label)

        desc = QLabel("每日 / 每周 / 每月的例行事项，到期自动展示，做完勾选，隔天自动重置。")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"""
            QLabel {{
                color: {pal['secondary']};
                font-size: 13px;
                line-height: 150%;
                background: transparent;
            }}
        """)
        lv.addWidget(desc)

        # 统计
        stats = QHBoxLayout()
        stats.setSpacing(8)
        self.stat_due = QLabel("0")
        self.stat_done = QLabel("0")
        self.stat_week = QLabel("0")
        self.stat_month = QLabel("0")
        stats.addWidget(self._stat_tile("今日应做", self.stat_due, pal["red"]))
        stats.addWidget(self._stat_tile("已完成", self.stat_done, pal["green"]))
        lv.addLayout(stats)
        stats2 = QHBoxLayout()
        stats2.setSpacing(8)
        stats2.addWidget(self._stat_tile("每周事项", self.stat_week, pal["blue"]))
        stats2.addWidget(self._stat_tile("每月事项", self.stat_month, pal["orange"]))
        lv.addLayout(stats2)

        lv.addStretch()

        # 视图切换
        view_label = QLabel("展示形式")
        view_label.setStyleSheet(f"color: {pal['secondary']}; font-size: 13px; background: transparent;")
        lv.addWidget(view_label)

        self.view_buttons = {}
        for text, mode in [("卡片视图", "card"), ("列表视图", "list")]:
            btn = QPushButton("  " + text)
            btn.setObjectName("NavBtn")
            btn.setFixedHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("active", mode == "card")
            btn.clicked.connect(lambda checked=False, m=mode: self._set_view(m))
            lv.addWidget(btn)
            self.view_buttons[mode] = btn

        add_btn = QPushButton("+ 新增周期事项")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.setFixedHeight(40)
        add_btn.clicked.connect(self._add_routine)
        lv.addWidget(add_btn)

        layout.addWidget(left)

        # 右侧内容区
        right = QWidget()
        right.setStyleSheet(f"background: {pal['bg']};")

        rv = QVBoxLayout(right)
        rv.setContentsMargins(24, 24, 24, 24)
        rv.setSpacing(16)

        header = QHBoxLayout()
        header_title = QLabel("例行工作安排")
        header_title.setFont(QFont("Segoe UI", 18, QFont.Normal))
        header.addWidget(header_title)
        header.addStretch()
        hint = QLabel("点击卡片可编辑 · 勾选表示今日完成")
        hint.setStyleSheet(f"color: {pal['muted']}; font-size: 13px;")
        header.addWidget(hint)
        rv.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background: transparent;")

        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(18)
        self.content_layout.addStretch()

        self.scroll.setWidget(self.content)
        rv.addWidget(self.scroll, 1)

        layout.addWidget(right, 1)

    def _stat_tile(self, text: str, num_label: QLabel, color: str) -> QWidget:
        pal = self.pal
        tile = QWidget()
        tile.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(tile)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(2)

        num_label.setFont(QFont("Segoe UI", 22, QFont.Normal))
        num_label.setAlignment(Qt.AlignCenter)
        num_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 22px;
                font-weight: 400;
                background: transparent;
            }}
        """)
        t = QLabel(text)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"""
            QLabel {{
                color: {pal['secondary']};
                font-size: 12px;
                background: transparent;
            }}
        """)
        lay.addWidget(num_label)
        lay.addWidget(t)
        return tile

    # ---------- 数据刷新 ----------
    def _clear_content(self):
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh(self):
        pal = self.pal
        self._clear_content()

        today = QDate.currentDate()
        today_str = today.toString("yyyy-MM-dd")

        groups = [
            ("daily", "每日事项", "每天打开后需要处理", pal["red"]),
            ("weekly", "每周事项", "按指定星期几展示", pal["blue"]),
            ("monthly", "每月事项", "按每月指定日期展示", pal["orange"]),
        ]

        for rep, name, sub, color in groups:
            items = [r for r in self.routines if r.get("repeat") == rep]
            self._build_section(name, sub, color, items)

        # 统计
        due_count = sum(1 for r in self.routines if is_due_today(r, today))
        done_count = sum(
            1 for r in self.routines
            if is_due_today(r, today) and is_done_today(r, today_str)
        )
        week_count = sum(1 for r in self.routines if r.get("repeat") == "weekly")
        month_count = sum(1 for r in self.routines if r.get("repeat") == "monthly")

        self.stat_due.setText(str(due_count))
        self.stat_done.setText(str(done_count))
        self.stat_week.setText(str(week_count))
        self.stat_month.setText(str(month_count))

        # 空提示
        if not self.routines:
            empty = QLabel("🎉 还没有周期事项，点击左下角「+ 新增周期事项」开始")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"""
                QLabel {{
                    color: {pal['secondary']};
                    font-size: 17px;
                    padding: 70px;
                }}
            """)
            self.content_layout.insertWidget(self.content_layout.count() - 1, empty)

        try:
            from config_app_v2 import make_text_selectable
            make_text_selectable(self, exclude_cls_names={"RoutineCard", "TodoCard"})
        except Exception:
            pass

    def _build_section(self, name: str, sub: str, color: str, items: List[dict]):
        pal = self.pal

        section = QFrame()
        section.setObjectName("RoutineSection")
        section.setStyleSheet(f"""
            #RoutineSection {{
                background: {pal['group']};
                border-radius: {pal['card_radius']}px;
                border: 1px solid {pal['border']};
            }}
        """)
        sv = QVBoxLayout(section)
        sv.setContentsMargins(18, 14, 18, 16)
        sv.setSpacing(12)

        # 分组头
        head = QHBoxLayout()
        head.setSpacing(10)

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent;")
        head.addWidget(dot)

        name_label = QLabel(name)
        name_label.setFont(QFont("Segoe UI", 16, QFont.Normal))
        name_label.setStyleSheet(f"color: {pal['text']}; background: transparent;")
        head.addWidget(name_label)

        count_badge = QLabel(f"{len(items)}")
        count_badge.setStyleSheet(_badge_style(color, "#FFFFFF"))
        head.addWidget(count_badge)

        sub_label = QLabel(sub)
        sub_label.setStyleSheet(f"color: {pal['muted']}; font-size: 12px; background: transparent;")
        head.addWidget(sub_label)
        head.addStretch()
        sv.addLayout(head)

        # 卡片容器
        if not items:
            empty = QLabel("暂无事项")
            empty.setStyleSheet(f"""
                QLabel {{
                    color: {pal['muted']};
                    font-size: 13px;
                    padding: 14px;
                    background: transparent;
                }}
            """)
            sv.addWidget(empty)
        else:
            if self.view_mode == "card":
                grid_widget = QWidget()
                grid_widget.setStyleSheet("background: transparent;")
                grid = QGridLayout(grid_widget)
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setHorizontalSpacing(12)
                grid.setVerticalSpacing(12)
                for i, r in enumerate(items):
                    card = RoutineCard(r, self.theme_name)
                    self._connect_card(card)
                    grid.addWidget(card, i // 2, i % 2)
                sv.addWidget(grid_widget)
            else:
                list_widget = QWidget()
                list_widget.setStyleSheet("background: transparent;")
                lv = QVBoxLayout(list_widget)
                lv.setContentsMargins(0, 0, 0, 0)
                lv.setSpacing(10)
                for r in items:
                    card = RoutineCard(r, self.theme_name)
                    self._connect_card(card)
                    lv.addWidget(card)
                sv.addWidget(list_widget)

        self.content_layout.insertWidget(self.content_layout.count() - 1, section)

    def _connect_card(self, card: RoutineCard):
        card.toggled.connect(self._on_toggle)
        card.deleted.connect(self._on_delete)
        card.clicked.connect(self._on_card_click)

    # ---------- 交互 ----------
    def _set_view(self, mode: str):
        self.view_mode = mode
        for m, btn in self.view_buttons.items():
            btn.setProperty("active", m == mode)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._refresh()

    def _add_routine(self):
        data = {
            "id": f"r_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "title": "",
            "repeat": "daily",
            "weekdays": [],
            "month_days": [],
            "tags": [],
            "note": "",
            "enabled": True,
            "notify": ["app"],
            "check_log": {},
            "created_at": datetime.now().isoformat(),
        }
        dlg = RoutineEditDialog(data, self.theme_name, self)
        if dlg.exec():
            self.routines.append(data)
            save_routines(self.routines)
            self._refresh()

    def _on_card_click(self, data: dict):
        dlg = RoutineEditDialog(data, self.theme_name, self)
        if dlg.exec():
            save_routines(self.routines)
            self._refresh()

    def _on_toggle(self, data: dict):
        save_routines(self.routines)
        self._refresh()

    def _on_delete(self, data: dict):
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除周期事项「{data.get('title', '')}」吗？\n（将同时删除其完成记录）",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.routines = [r for r in self.routines if r is not data]
            save_routines(self.routines)
            self._refresh()

    # ---------- 提醒 ----------
    def _check_reminders(self):
        today = QDate.currentDate()
        today_str = today.toString("yyyy-MM-dd")

        if self._remind_date != today_str:
            self._remind_date = today_str
            self._reminded_ids.clear()

        pending = []
        for r in self.routines:
            if not r.get("enabled", True):
                continue
            if "app" not in (r.get("notify") or ["app"]):
                continue
            if not is_due_today(r, today):
                continue
            if is_done_today(r, today_str):
                continue
            rid = r.get("id")
            if rid in self._reminded_ids:
                continue
            self._reminded_ids.add(rid)
            pending.append(r)

        if not pending:
            return

        lines = "\n".join(f"· {r.get('title', '')}" for r in pending)
        QMessageBox.information(
            self,
            "周期事项提醒",
            f"📅 今天有 {len(pending)} 件周期事项待处理：\n\n{lines}\n\n可切换到「周期事项」页完成勾选。",
        )
