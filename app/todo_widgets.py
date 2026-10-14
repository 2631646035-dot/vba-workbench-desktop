"""
待办事项 v4.1 — Apple iOS / macOS 清晰简洁风

重点修改：
1. 提高文字对比度
2. 修复统计区域文字被遮挡/看不清
3. 重新设计跟进时间轴为“跟进总览图”
4. 卡片、弹窗、附件区统一高对比 iOS 风格
"""

import json
import os
import re
import html
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QLineEdit, QComboBox, QCheckBox, QDateEdit,
    QFileDialog, QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem,
    QGraphicsRectItem, QSizePolicy, QDialog, QTextEdit, QTextBrowser,
    QListWidget, QListWidgetItem, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QDate, QSize, QRectF, QPointF
)
from PySide6.QtGui import (
    QFont, QColor, QBrush, QPen, QPainter, QPainterPath,
    QPixmap, QIcon, QLinearGradient, QPolygonF
)

try:
    from config_app_v2 import THEMES, DEFAULT_THEME
    from config_app_v2 import make_text_selectable
except Exception:
    import __main__ as main_mod
    THEMES = main_mod.THEMES
    DEFAULT_THEME = main_mod.DEFAULT_THEME

try:
    import todo_db
    HAS_DB = True
except Exception:
    HAS_DB = False


PROJECT_DIR = Path(__file__).parent
TODO_FILE = PROJECT_DIR / "config" / "todos.json"
ATTACHMENTS_DIR = PROJECT_DIR / "config" / "attachments"

ESTIMATED_TIMES = ["15min", "30min", "1h", "2h", "4h", "1天", "2天", "3天", "1周"]

QUOTES = [
    "千里之行，始于足下。",
    "今日事，今日毕。",
    "工欲善其事，必先利其器。",
    "不积跬步，无以至千里。",
    "效率是做好对的事情。",
    "好的开始是成功的一半。",
    "行动是治愈焦虑的良药。",
    "把简单的事做到极致就是绝招。",
]


def _p(theme_name: str) -> dict:
    return THEMES.get(theme_name, THEMES[DEFAULT_THEME])


def _priority_color(priority: str, pal: dict) -> str:
    return {
        "高": pal["red"],
        "中": pal["orange"],
        "低": pal["green"],
    }.get(priority, pal["primary"])


def _ios_shadow(widget: QWidget, theme_name: str = DEFAULT_THEME):
    pal = _p(theme_name)
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(pal["shadow_blur"])
    effect.setOffset(0, 4)
    effect.setColor(QColor(0, 0, 0, pal["shadow_alpha"]))
    widget.setGraphicsEffect(effect)


def _parse_date(date_str: str) -> QDate:
    if not date_str:
        return QDate()
    d = QDate.fromString(date_str[:10], "yyyy-MM-dd")
    return d


def _date_from_created(created_at: str) -> QDate:
    if not created_at:
        return QDate()
    try:
        return QDate.fromString(created_at[:10], "yyyy-MM-dd")
    except Exception:
        return QDate()


# ============================================================
# 1. 跟进总览图
# ============================================================
class FollowOverviewView(QGraphicsView):
    """
    替代原来的小时间轴。

    展现方式：
    - 每一行是一个跟进事项
    - 左侧显示事项标题
    - 中间是从创建时间/最早记录到计划跟进日期的时间线
    - 蓝色圆点：历史跟进记录
    - 橙/红菱形：计划跟进时间
    - 绿色圆点：已完成
    """

    def __init__(self, theme_name: str = DEFAULT_THEME, parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.pal = _p(theme_name)
        self.todos: List[dict] = []

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)

        self.setMinimumHeight(230)
        self.setMaximumHeight(300)

        self.left_width = 132
        self.top_margin = 36
        self.row_h = 38
        self.day_w = 34

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.setStyleSheet(f"""
            QGraphicsView {{
                background: {self.pal['surface']};
                border: 1.5px solid {self.pal['border']};
                border-radius: {self.pal['radius']}px;
            }}
        """)

    def set_todos(self, todos: List[dict]):
        self.todos = [t for t in todos if t.get("is_follow_up")]
        self._draw()

    def _collect_dates(self):
        dates = []
        for todo in self.todos:
            c = _date_from_created(todo.get("created_at", ""))
            if c.isValid():
                dates.append(c)

            fd = _parse_date(todo.get("follow_up_date", ""))
            if fd.isValid():
                dates.append(fd)

            for h in todo.get("follow_up_history", []):
                hd = _parse_date(h.get("date", ""))
                if hd.isValid():
                    dates.append(hd)

        return dates

    def _draw(self):
        self.scene.clear()
        pal = self.pal

        if not self.todos:
            text = self.scene.addText("暂无跟进事项")
            text.setDefaultTextColor(QColor(pal["secondary"]))
            text.setFont(QFont("Segoe UI", 11, QFont.Normal))
            text.setPos(22, 34)
            self.scene.setSceneRect(0, 0, 420, 170)
            return

        dates = self._collect_dates()
        if not dates:
            today = QDate.currentDate()
            min_date = today.addDays(-3)
            max_date = today.addDays(7)
        else:
            min_date = min(dates).addDays(-1)
            max_date = max(dates).addDays(2)

        total_days = max(1, max_date.toJulianDay() - min_date.toJulianDay() + 1)

        chart_x = self.left_width
        chart_w = total_days * self.day_w
        width = chart_x + chart_w + 30
        height = self.top_margin + max(5, len(self.todos)) * self.row_h + 22

        # 背景
        bg = QGraphicsRectItem(0, 0, width, height)
        bg.setBrush(QBrush(QColor(pal["surface"])))
        bg.setPen(QPen(Qt.NoPen))
        self.scene.addItem(bg)

        # 标题提示
        title = self.scene.addText("跟进总览")
        title.setDefaultTextColor(QColor(pal["text"]))
        title.setFont(QFont("Segoe UI", 10, QFont.Normal))
        title.setPos(12, 8)

        legend = self.scene.addText("●历史跟进   ◆计划跟进   ✓已完成")
        legend.setDefaultTextColor(QColor(pal["secondary"]))
        legend.setFont(QFont("Segoe UI", 8))
        legend.setPos(chart_x + 8, 10)

        # 日期轴
        for i in range(total_days + 1):
            d = min_date.addDays(i)
            x = chart_x + i * self.day_w

            is_major = i == 0 or d.dayOfWeek() == 1 or d.day() == 1
            pen = QPen(QColor(pal["border"]), 1)
            if is_major:
                pen = QPen(QColor(pal["separator"]), 1)

            line = QGraphicsLineItem(x, self.top_margin - 6, x, height - 16)
            line.setPen(pen)
            self.scene.addItem(line)

            if is_major:
                label = self.scene.addText(d.toString("MM/dd"))
                label.setDefaultTextColor(QColor(pal["secondary"]))
                label.setFont(QFont("Segoe UI", 7))
                label.setPos(x - 14, self.top_margin - 24)

        # 今天竖线
        today = QDate.currentDate()
        if min_date <= today <= max_date:
            idx = today.toJulianDay() - min_date.toJulianDay()
            x = chart_x + idx * self.day_w
            today_line = QGraphicsLineItem(x, self.top_margin - 8, x, height - 14)
            today_line.setPen(QPen(QColor(pal["primary"]), 2))
            self.scene.addItem(today_line)

            t = self.scene.addText("今天")
            t.setDefaultTextColor(QColor(pal["primary"]))
            t.setFont(QFont("Segoe UI", 8, QFont.Normal))
            t.setPos(x - 14, height - 18)

        # 每个任务一行
        for row, todo in enumerate(self.todos):
            y = self.top_margin + row * self.row_h + 18

            # 交替背景
            if row % 2 == 0:
                rect = QGraphicsRectItem(6, y - 16, width - 14, self.row_h - 4)
                rect.setBrush(QBrush(QColor(pal["group"])))
                rect.setPen(QPen(Qt.NoPen))
                self.scene.addItem(rect)

            title_text = todo.get("title", "未命名")
            if len(title_text) > 9:
                title_text = title_text[:9] + "…"

            title_item = self.scene.addText(title_text)
            title_item.setDefaultTextColor(QColor(pal["text"]))
            title_item.setFont(QFont("Segoe UI", 8, QFont.Normal))
            title_item.setPos(12, y - 12)
            title_item.setToolTip(todo.get("title", ""))

            completed = todo.get("completed", False)
            priority = todo.get("priority", "中")
            pri_color = QColor(_priority_color(priority, pal))

            fd = _parse_date(todo.get("follow_up_date", ""))
            created = _date_from_created(todo.get("created_at", ""))

            valid_points = []

            if created.isValid():
                valid_points.append(created)

            for h in todo.get("follow_up_history", []):
                hd = _parse_date(h.get("date", ""))
                if hd.isValid():
                    valid_points.append(hd)

            if fd.isValid():
                valid_points.append(fd)

            if not valid_points:
                continue

            start_d = min(valid_points)
            end_d = max(valid_points)

            x1 = chart_x + (start_d.toJulianDay() - min_date.toJulianDay()) * self.day_w
            x2 = chart_x + (end_d.toJulianDay() - min_date.toJulianDay()) * self.day_w
            if x2 < x1:
                x1, x2 = x2, x1

            # 时间跨度线
            span = QGraphicsLineItem(x1, y, x2, y)
            span.setPen(QPen(QColor(pal["primary"] if not completed else pal["green"]), 3))
            self.scene.addItem(span)

            # 历史跟进点
            for h in todo.get("follow_up_history", []):
                hd = _parse_date(h.get("date", ""))
                if not hd.isValid():
                    continue
                x = chart_x + (hd.toJulianDay() - min_date.toJulianDay()) * self.day_w
                dot = QGraphicsEllipseItem(x - 5, y - 5, 10, 10)
                dot.setBrush(QBrush(QColor(pal["blue"])))
                dot.setPen(QPen(QColor(pal["surface"]), 2))
                dot.setToolTip(f"{todo.get('title', '')}\n历史跟进：{h.get('date', '')}\n备注：{h.get('note', '')}")
                self.scene.addItem(dot)

            # 计划跟进点：菱形
            if fd.isValid():
                x = chart_x + (fd.toJulianDay() - min_date.toJulianDay()) * self.day_w
                points = QPolygonF([
                    QPointF(x, y - 7),
                    QPointF(x + 7, y),
                    QPointF(x, y + 7),
                    QPointF(x - 7, y),
                ])
                diamond = self.scene.addPolygon(points)
                diamond.setBrush(QBrush(pri_color))
                diamond.setPen(QPen(QColor(pal["surface"]), 2))
                diamond.setToolTip(
                    f"{todo.get('title', '')}\n计划跟进：{todo.get('follow_up_date', '')}\n优先级：{priority}"
                )

            # 完成状态
            status_x = chart_x + chart_w + 8
            status = self.scene.addText("✓" if completed else "未完")
            status.setFont(QFont("Segoe UI", 8, QFont.Normal))
            status.setDefaultTextColor(QColor(pal["green"] if completed else pal["secondary"]))
            status.setPos(status_x, y - 11)

        self.scene.setSceneRect(0, 0, width, height)


# ============================================================
# 2. S 型活动密度曲线
# ============================================================
class SCurveView(QWidget):
    def __init__(self, theme_name: str = DEFAULT_THEME, parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.pal = _p(theme_name)
        self.setMinimumHeight(90)
        self.setMaximumHeight(110)
        self.weekly_data: List[Dict] = []

    def set_data(self, todos: List[dict], weeks: int = 8):
        today = QDate.currentDate()
        week_start = today.addDays(-(today.dayOfWeek() - 1))
        self.weekly_data = []

        for i in range(weeks - 1, -1, -1):
            ws = week_start.addDays(-i * 7)
            we = ws.addDays(6)
            count = 0

            for todo in todos:
                if not todo.get("is_follow_up"):
                    continue

                for h in todo.get("follow_up_history", []):
                    hd = _parse_date(h.get("date", ""))
                    if hd.isValid() and ws <= hd <= we:
                        count += 1

                fd = _parse_date(todo.get("follow_up_date", ""))
                if fd.isValid() and ws <= fd <= we:
                    count += 1

            self.weekly_data.append({"week_start": ws, "week_end": we, "count": count})

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pal = self.pal
        w = self.width()
        h = self.height()
        padding = 16

        painter.fillRect(self.rect(), QColor(pal["surface"]))

        if not self.weekly_data:
            painter.setPen(QColor(pal["secondary"]))
            painter.setFont(QFont("Segoe UI", 9, QFont.Normal))
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无跟进数据")
            return

        n = len(self.weekly_data)
        max_count = max(d["count"] for d in self.weekly_data) or 1
        bar_width = (w - padding * 2) / n
        chart_h = h - padding * 2 - 16
        baseline_y = h - padding - 4

        painter.setPen(QPen(QColor(pal["border"]), 1))
        painter.drawLine(padding, baseline_y, w - padding, baseline_y)

        points = []
        for i, d in enumerate(self.weekly_data):
            x = padding + i * bar_width + bar_width / 2
            y = baseline_y - (d["count"] / max_count) * chart_h
            points.append((x, y))

        if len(points) >= 2:
            fill_path = QPainterPath()
            fill_path.moveTo(points[0][0], baseline_y)

            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                ctrl_x1 = x1 + (x2 - x1) * 0.5
                ctrl_x2 = x2 - (x2 - x1) * 0.5
                fill_path.cubicTo(ctrl_x1, y1, ctrl_x2, y2, x2, y2)

            fill_path.lineTo(points[-1][0], baseline_y)
            fill_path.closeSubpath()

            gradient = QLinearGradient(0, padding, 0, baseline_y)
            c = QColor(pal["primary"])
            gradient.setColorAt(0, QColor(c.red(), c.green(), c.blue(), 70))
            gradient.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 12))
            painter.fillPath(fill_path, QBrush(gradient))

            curve = QPainterPath()
            curve.moveTo(points[0][0], points[0][1])
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                ctrl_x1 = x1 + (x2 - x1) * 0.5
                ctrl_x2 = x2 - (x2 - x1) * 0.5
                curve.cubicTo(ctrl_x1, y1, ctrl_x2, y2, x2, y2)

            painter.setPen(QPen(QColor(pal["primary"]), 2.3))
            painter.drawPath(curve)

        painter.setFont(QFont("Segoe UI", 8, QFont.Normal))

        for i, d in enumerate(self.weekly_data):
            x = padding + i * bar_width + bar_width / 2
            y = baseline_y - (d["count"] / max_count) * chart_h

            if d["count"] > 0:
                painter.setBrush(QBrush(QColor(pal["primary"])))
                painter.setPen(QPen(QColor(pal["surface"]), 2))
                painter.drawEllipse(QPointF(x, y), 4.5, 4.5)

                painter.setPen(QColor(pal["text"]))
                painter.drawText(QRectF(x - 12, y - 22, 24, 14), Qt.AlignCenter, str(d["count"]))

            painter.setPen(QColor(pal["secondary"]))
            painter.drawText(
                QRectF(x - bar_width / 2, baseline_y + 2, bar_width, 14),
                Qt.AlignCenter,
                d["week_start"].toString("MM/dd")
            )


# ============================================================
# 3. 附件区域
# ============================================================
class AttachmentWidget(QWidget):
    attachmentsChanged = Signal()

    def __init__(self, todo_id: int, theme_name: str = DEFAULT_THEME, parent=None):
        super().__init__(parent)
        self.todo_id = todo_id
        self.theme_name = theme_name
        self.pal = _p(theme_name)
        self.attachments: List[dict] = []
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self):
        pal = self.pal

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        label = QLabel("附件")
        label.setFont(QFont("Segoe UI", 11, QFont.Normal))
        label.setStyleSheet(f"color: {pal['text']};")
        header.addWidget(label)
        header.addStretch()

        add_btn = QPushButton("添加文件")
        add_btn.setFixedHeight(34)
        add_btn.clicked.connect(self._add_files_dialog)
        header.addWidget(add_btn)

        layout.addLayout(header)

        self.file_list = QListWidget()
        self.file_list.setAcceptDrops(True)
        self.file_list.setIconSize(QSize(28, 28))
        self.file_list.setMinimumHeight(82)
        self.file_list.setMaximumHeight(130)
        self.file_list.setStyleSheet(f"""
            QListWidget {{
                background: {pal['surface']};
                border: 1.8px dashed {pal['separator']};
                border-radius: {pal['radius']}px;
                padding: 8px;
                color: {pal['text']};
            }}
            QListWidget::item {{
                padding: 8px 10px;
                border-radius: 8px;
            }}
            QListWidget::item:hover {{
                background: {pal['hover']};
            }}
            QListWidget::item:selected {{
                background: {pal['selection_bg']};
                color: {pal['text']};
            }}
        """)
        self.file_list.itemDoubleClicked.connect(self._open_attachment)
        layout.addWidget(self.file_list)

        hint = QLabel("拖放文件到此处，或点击「添加文件」")
        hint.setStyleSheet(f"color: {pal['secondary']}; font-size: 12px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

    def set_attachments(self, attachments: List[dict]):
        self.attachments = attachments or []
        self._refresh_list()

    def _refresh_list(self):
        self.file_list.clear()

        for att in self.attachments:
            name = att.get("name", "未知文件")
            path = att.get("path", "")

            item = QListWidgetItem(name)
            item.setToolTip(path)
            item.setIcon(self._create_text_icon(self._get_icon_for_ext(Path(name).suffix.lower())))
            item.setData(Qt.UserRole, path)

            self.file_list.addItem(item)

    def _get_icon_for_ext(self, ext: str) -> str:
        icons = {
            ".xlsx": "📊", ".xls": "📊", ".csv": "📊",
            ".pdf": "📄", ".doc": "📝", ".docx": "📝",
            ".txt": "📄", ".msg": "📧", ".eml": "📧",
            ".png": "🖼", ".jpg": "🖼", ".jpeg": "🖼",
            ".gif": "🖼", ".bmp": "🖼",
            ".zip": "📦", ".rar": "📦",
            ".py": "🐍", ".json": "⚙️",
        }
        return icons.get(ext, "📎")

    def _create_text_icon(self, text: str) -> QIcon:
        pm = QPixmap(28, 28)
        pm.fill(Qt.transparent)

        painter = QPainter(pm)
        painter.setFont(QFont("Segoe UI", 16))
        painter.drawText(pm.rect(), Qt.AlignCenter, text)
        painter.end()

        return QIcon(pm)

    def _add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        for path in paths:
            self._add_file(path)

    def _add_file(self, src_path: str):
        src = Path(src_path)
        if not src.exists():
            return

        dest_dir = ATTACHMENTS_DIR / str(self.todo_id)
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / src.name
        if src.resolve() != dest_path.resolve():
            shutil.copy2(src, dest_path)

        self.attachments.append({"name": src.name, "path": str(dest_path)})
        self._refresh_list()
        self.attachmentsChanged.emit()

    def _open_attachment(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path and Path(path).exists():
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and Path(path).exists():
                self._add_file(path)
        event.acceptProposedAction()


# ============================================================
# 4. 待办卡片
# ============================================================
class TodoCard(QFrame):
    toggled = Signal(dict)
    deleted = Signal(dict)
    clicked = Signal(dict)

    def __init__(self, data: dict, theme_name: str = DEFAULT_THEME, parent=None):
        super().__init__(parent)
        self.data = data
        self.theme_name = theme_name
        self.pal = _p(theme_name)
        self.setCursor(Qt.PointingHandCursor)
        self._build_ui()

    def _build_ui(self):
        pal = self.pal
        is_follow_up = self.data.get("is_follow_up", False)
        priority = self.data.get("priority", "中")
        completed = self.data.get("completed", False)
        priority_color = _priority_color(priority, pal)

        main = QVBoxLayout(self)
        main.setContentsMargins(20, 16, 20, 16)
        main.setSpacing(10)

        # 顶部：复选框 + 标题 + 删除
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(completed)
        self.checkbox.stateChanged.connect(self._on_toggle)
        top_row.addWidget(self.checkbox, 0, Qt.AlignTop)

        title_box = QVBoxLayout()
        title_box.setSpacing(6)

        self.title_label = QLabel(self.data.get("title", ""))
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            f"""
            QLabel {{
                color: {pal['text']};
                font-size: 16px;
                font-weight: 400;
                line-height: 140%;
            }}
            """
            if not completed else
            f"""
            QLabel {{
                color: {pal['muted']};
                font-size: 15px;
                font-weight: 400;
                text-decoration: line-through;
                line-height: 140%;
            }}
            """
        )
        title_box.addWidget(self.title_label)

        top_row.addLayout(title_box, 1)

        del_btn = QPushButton("×")
        del_btn.setFixedSize(30, 30)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                color: {pal['secondary']};
                background: transparent;
                border: none;
                border-radius: 15px;
                font-size: 18px;
                font-weight: 400;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {pal['danger_bg']};
                color: {pal['danger_text']};
            }}
        """)
        del_btn.clicked.connect(self._on_delete)
        top_row.addWidget(del_btn, 0, Qt.AlignTop)

        main.addLayout(top_row)

        # 标签区域
        tags_row = QHBoxLayout()
        tags_row.setSpacing(8)
        tags_row.setContentsMargins(34, 0, 0, 0)

        priority_badge = QLabel(f"● {priority}")
        priority_badge.setStyleSheet(f"""
            QLabel {{
                color: {priority_color};
                font-size: 13px;
                font-weight: 400;
            }}
        """)
        tags_row.addWidget(priority_badge)

        est = self.data.get("estimated_time", "")
        if est:
            tags_row.addWidget(self._make_separator())
            est_label = QLabel(f"⏱ {est}")
            est_label.setStyleSheet(f"""
                QLabel {{
                    color: {pal['secondary']};
                    font-size: 13px;
                    font-weight: 400;
                }}
            """)
            tags_row.addWidget(est_label)

        if is_follow_up:
            tags_row.addWidget(self._make_separator())

            fu_date = self.data.get("follow_up_date", "")
            fu_text = f"🔁 {fu_date}" if fu_date else "🔁 跟进"
            fu_label = QLabel(fu_text)
            fu_label.setStyleSheet(f"""
                QLabel {{
                    color: {pal['blue']};
                    font-size: 13px;
                    font-weight: 400;
                }}
            """)
            tags_row.addWidget(fu_label)

            history = self.data.get("follow_up_history", [])
            if history:
                tags_row.addWidget(self._make_separator())
                hist_label = QLabel(f"已跟进 {len(history)} 次")
                hist_label.setStyleSheet(f"""
                    QLabel {{
                        color: {pal['secondary']};
                        font-size: 13px;
                        font-weight: 400;
                    }}
                """)
                tags_row.addWidget(hist_label)

            if self.data.get("follow_up_reminder"):
                fd = _parse_date(fu_date)
                if fd.isValid():
                    days_left = fd.toJulianDay() - QDate.currentDate().toJulianDay()
                    if 0 <= days_left <= 3:
                        tags_row.addWidget(self._make_separator())
                        bell = QLabel("🔔 即将到期")
                        bell.setStyleSheet(f"""
                            QLabel {{
                                color: {pal['red']};
                                font-size: 13px;
                                font-weight: 400;
                            }}
                        """)
                        tags_row.addWidget(bell)

        attachments = self.data.get("attachments", [])
        if attachments:
            tags_row.addWidget(self._make_separator())
            att_label = QLabel(f"📎 {len(attachments)} 个附件")
            att_label.setStyleSheet(f"""
                QLabel {{
                    color: {pal['orange']};
                    font-size: 13px;
                    font-weight: 400;
                }}
            """)
            tags_row.addWidget(att_label)

        if completed:
            tags_row.addWidget(self._make_separator())
            done_label = QLabel("✓ 已完成")
            done_label.setStyleSheet(f"""
                QLabel {{
                    color: {pal['green']};
                    font-size: 13px;
                    font-weight: 400;
                }}
            """)
            tags_row.addWidget(done_label)

        tags_row.addStretch()
        main.addLayout(tags_row)

        note = self.data.get("note", "")
        if note:
            import re as _re
            url_pat = _re.compile(r'(https?://[^\s<>"\']+)')
            urls = url_pat.findall(note)
            if urls:
                escaped = note
                for url in urls:
                    escaped = escaped.replace(
                        url,
                        f'<a href="{url}" style="color: {pal["primary"]};">{url}</a>'
                    )
                note_label = QLabel(escaped)
                note_label.setTextFormat(Qt.RichText)
                note_label.setOpenExternalLinks(True)
            else:
                note_label = QLabel(note)

            note_label.setWordWrap(True)
            note_label.setStyleSheet(f"""
                QLabel {{
                    color: {pal['secondary']};
                    font-size: 13px;
                    background: transparent;
                    padding-left: 34px;
                }}
            """)
            main.addWidget(note_label)

        # 卡片样式
        accent = pal["blue"] if is_follow_up else "transparent"
        opacity_bg = pal["card"]

        self.setObjectName("TodoCard")
        self.setStyleSheet(f"""
            #TodoCard {{
                background: {opacity_bg};
                border-radius: {pal['card_radius']}px;
                border: 1px solid {pal['border']};
                border-left: 4px solid {accent};
            }}
            #TodoCard:hover {{
                border-color: {pal['primary']};
                background: {pal['surface']};
            }}
        """)

    def _make_separator(self) -> QLabel:
        sep = QLabel("|")
        sep.setStyleSheet(f"""
            QLabel {{
                color: {self.pal['separator']};
                font-size: 13px;
                font-weight: 400;
            }}
        """)
        return sep

    def _on_toggle(self, state):
        self.data["completed"] = bool(state)
        if state:
            self.data["completed_at"] = datetime.now().isoformat()
        else:
            self.data["completed_at"] = ""
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
# 5. 待办详情弹窗
# ============================================================
class TodoDetailDialog(QDialog):
    def __init__(self, data: dict, theme_name: str = DEFAULT_THEME, parent=None):
        super().__init__(parent)
        self.data = data
        self.theme_name = theme_name
        self.pal = _p(theme_name)

        self.setWindowTitle("待办详情")
        self.setMinimumSize(640, 700)
        self.setModal(True)

        self._build_ui()
        self._load_data()

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 13, QFont.Normal))
        label.setStyleSheet(f"""
            QLabel {{
                color: {self.pal['secondary']};
                font-size: 13px;
                font-weight: 400;
            }}
        """)
        return label

    def _build_group_card(self) -> QFrame:
        pal = self.pal
        card = QFrame()
        card.setObjectName("GroupCard")
        card.setStyleSheet(f"""
            #GroupCard {{
                background: {pal['group']};
                border-radius: {pal['card_radius']}px;
                border: 1px solid {pal['border']};
            }}
        """)
        return card

    def _build_ui(self):
        pal = self.pal

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)

        title = QLabel("待办详情")
        title.setFont(QFont("Segoe UI", 24, QFont.Normal))
        title.setStyleSheet(f"color: {pal['text']};")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # 基本信息
        info_card = self._build_group_card()
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(20, 18, 20, 18)
        info_layout.setSpacing(14)

        info_layout.addWidget(self._section_title("基本信息"))

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("待办事项标题")
        self.title_edit.setMinimumHeight(44)
        info_layout.addWidget(self.title_edit)

        row1 = QHBoxLayout()
        row1.setSpacing(12)

        pri_label = QLabel("优先级")
        pri_label.setStyleSheet(f"color: {pal['text']}; font-weight: 400;")
        row1.addWidget(pri_label)

        self.priority_combo = QComboBox()
        self.priority_combo.addItem("低", "低")
        self.priority_combo.addItem("中", "中")
        self.priority_combo.addItem("高", "高")
        row1.addWidget(self.priority_combo, 1)

        info_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(12)

        est_label = QLabel("预估时间")
        est_label.setStyleSheet(f"color: {pal['text']}; font-weight: 400;")
        row2.addWidget(est_label)

        self.est_combo = QComboBox()
        self.est_combo.setEditable(True)
        for item in ESTIMATED_TIMES:
            self.est_combo.addItem(item)
        row2.addWidget(self.est_combo, 1)

        info_layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.completed_check = QCheckBox("已完成")
        row3.addWidget(self.completed_check)
        row3.addStretch()
        info_layout.addLayout(row3)

        info_layout.addWidget(self._section_title("备注"))

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("输入备注，可包含链接（如 https://example.com）...")
        self.note_edit.setMinimumHeight(60)
        self.note_edit.setMaximumHeight(120)
        info_layout.addWidget(self.note_edit)

        scroll_layout.addWidget(info_card)

        # 跟进设置
        fu_card = self._build_group_card()
        fu_layout = QVBoxLayout(fu_card)
        fu_layout.setContentsMargins(20, 18, 20, 18)
        fu_layout.setSpacing(14)

        fu_layout.addWidget(self._section_title("跟进设置"))

        self.follow_up_check = QCheckBox("设为跟进事项")
        fu_layout.addWidget(self.follow_up_check)

        fu_date_row = QHBoxLayout()
        fu_date_row.setSpacing(12)

        fu_date_label = QLabel("跟进日期")
        fu_date_label.setStyleSheet(f"color: {pal['text']}; font-weight: 400;")
        fu_date_row.addWidget(fu_date_label)

        self.fu_date_edit = QDateEdit()
        self.fu_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.fu_date_edit.setCalendarPopup(True)
        self.fu_date_edit.setMinimumHeight(42)
        fu_date_row.addWidget(self.fu_date_edit, 1)

        fu_layout.addLayout(fu_date_row)

        self.fu_reminder_check = QCheckBox("到日期时提醒")
        fu_layout.addWidget(self.fu_reminder_check)

        hist_label = QLabel("跟进历史")
        hist_label.setStyleSheet(f"""
            QLabel {{
                color: {pal['secondary']};
                font-size: 13px;
                font-weight: 400;
            }}
        """)
        fu_layout.addWidget(hist_label)

        self.history_view = QTextBrowser()
        self.history_view.setOpenExternalLinks(True)
        self.history_view.setMinimumHeight(92)
        self.history_view.setMaximumHeight(150)
        self.history_view.setStyleSheet(f"""
            QTextBrowser {{
                background: {pal['surface']};
                border: 1.8px solid {pal['input_border']};
                border-radius: {pal['radius']}px;
                color: {pal['text']};
                padding: 6px 8px;
            }}
        """)
        fu_layout.addWidget(self.history_view)

        add_hist_row = QHBoxLayout()
        add_hist_row.setSpacing(8)

        self.hist_note_edit = QLineEdit()
        self.hist_note_edit.setPlaceholderText("输入本次跟进备注，可包含链接...")
        self.hist_note_edit.setMinimumHeight(40)
        add_hist_row.addWidget(self.hist_note_edit, 1)

        add_hist_btn = QPushButton("记录")
        add_hist_btn.setObjectName("PrimaryBtn")
        add_hist_btn.setFixedHeight(40)
        add_hist_btn.clicked.connect(self._add_history)
        add_hist_row.addWidget(add_hist_btn)

        fu_layout.addLayout(add_hist_row)

        del_row = QHBoxLayout()
        del_row.setSpacing(8)
        self.hist_del_combo = QComboBox()
        del_row.addWidget(self.hist_del_combo, 1)
        del_hist_btn = QPushButton("删除该记录")
        del_hist_btn.setObjectName("DangerBtn")
        del_hist_btn.clicked.connect(self._del_history)
        del_row.addWidget(del_hist_btn)
        fu_layout.addLayout(del_row)

        scroll_layout.addWidget(fu_card)

        # 附件
        att_card = self._build_group_card()
        att_layout = QVBoxLayout(att_card)
        att_layout.setContentsMargins(20, 18, 20, 18)
        att_layout.setSpacing(10)

        att_layout.addWidget(self._section_title("附件"))

        todo_id = self.data.get("id", 0)
        self.attachment_widget = AttachmentWidget(todo_id, self.theme_name)
        att_layout.addWidget(self.attachment_widget)

        scroll_layout.addWidget(att_card)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.setFixedHeight(44)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.setFixedHeight(44)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _load_data(self):
        self.title_edit.setText(self.data.get("title", ""))

        priority = self.data.get("priority", "中")
        idx = self.priority_combo.findData(priority)
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)

        est = self.data.get("estimated_time", "")
        if est:
            idx = self.est_combo.findText(est)
            if idx >= 0:
                self.est_combo.setCurrentIndex(idx)
            else:
                self.est_combo.setEditText(est)

        self.completed_check.setChecked(self.data.get("completed", False))

        self.note_edit.setPlainText(self.data.get("note", ""))

        self.follow_up_check.setChecked(self.data.get("is_follow_up", False))
        self.follow_up_check.stateChanged.connect(self._on_fu_toggle)

        fu_date = self.data.get("follow_up_date", "")
        if fu_date:
            d = _parse_date(fu_date)
            if d.isValid():
                self.fu_date_edit.setDate(d)
            else:
                self.fu_date_edit.setDate(QDate.currentDate())
        else:
            self.fu_date_edit.setDate(QDate.currentDate())

        self.fu_reminder_check.setChecked(self.data.get("follow_up_reminder", False))

        self._refresh_history()
        self.attachment_widget.set_attachments(self.data.get("attachments", []))
        self._on_fu_toggle()

    def _on_fu_toggle(self, state=None):
        enabled = self.follow_up_check.isChecked()
        self.fu_date_edit.setEnabled(enabled)
        self.fu_reminder_check.setEnabled(enabled)
        self.history_view.setEnabled(enabled)
        self.hist_del_combo.setEnabled(enabled)
        self.hist_note_edit.setEnabled(enabled)
        self.hist_note_edit.setPlaceholderText(
            "输入本次跟进备注，可包含链接..." if enabled else "请先勾选「设为跟进事项」"
        )

    def _refresh_history(self):
        pal = self.pal
        history = self.data.get("follow_up_history", [])

        parts = []
        if not history:
            parts.append(
                f'<p style="color:{pal["secondary"]}; margin:2px 0;">暂无跟进记录</p>'
            )
        for i, h in enumerate(history):
            display = html.escape(h.get("note", ""))
            if h.get("linked"):
                display = re.sub(
                    r'(https?://[^\s<]+)',
                    lambda m: f'<a href="{m.group(1)}" style="color:{pal["primary"]};">{m.group(1)}</a>',
                    display,
                )
            parts.append(
                f'<p style="margin:2px 0; color:{pal["text"]};">'
                f'{i + 1}. '
                f'<span style="color:{pal["secondary"]};">{h.get("date", "")}</span>'
                f' — {display}</p>'
            )
        self.history_view.setHtml("".join(parts))

        self.hist_del_combo.blockSignals(True)
        self.hist_del_combo.clear()
        for i, h in enumerate(history):
            summary = h.get("note", "")[:24]
            self.hist_del_combo.addItem(f"{i + 1}. {h.get('date', '')} — {summary}")
        self.hist_del_combo.blockSignals(False)

    def _add_history(self):
        note = self.hist_note_edit.text().strip()
        if not note:
            return

        linked = False
        if re.search(r'https?://', note):
            reply = QMessageBox.question(
                self,
                "检测到链接",
                "备注中包含链接（URL）。\n\n是否将链接转换为可自动跳转的形式？",
                QMessageBox.Yes | QMessageBox.No,
            )
            linked = (reply == QMessageBox.Yes)

        history = self.data.setdefault("follow_up_history", [])
        history.append({
            "date": QDate.currentDate().toString("yyyy-MM-dd"),
            "note": note,
            "linked": linked,
        })

        self.hist_note_edit.clear()
        self._refresh_history()

    def _del_history(self):
        idx = self.hist_del_combo.currentIndex()
        if idx < 0:
            return

        history = self.data.get("follow_up_history", [])
        if 0 <= idx < len(history):
            history.pop(idx)
            self._refresh_history()

    def _save(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "待办标题不能为空。")
            return

        self.data["title"] = title
        self.data["priority"] = self.priority_combo.currentData()
        self.data["estimated_time"] = self.est_combo.currentText().strip()
        self.data["completed"] = self.completed_check.isChecked()
        self.data["note"] = self.note_edit.toPlainText().strip()

        is_fu = self.follow_up_check.isChecked()
        self.data["is_follow_up"] = is_fu

        if is_fu:
            self.data["follow_up_date"] = self.fu_date_edit.date().toString("yyyy-MM-dd")
            self.data["follow_up_reminder"] = self.fu_reminder_check.isChecked()
            self.data.setdefault("follow_up_history", [])
        else:
            self.data["follow_up_date"] = ""
            self.data["follow_up_reminder"] = False
            self.data.setdefault("follow_up_history", [])

        self.data["attachments"] = self.attachment_widget.attachments

        self._persist()
        self.accept()

    def _persist(self):
        """直接将当前 self.data 写入 todos.json，不依赖弹窗返回值"""
        try:
            with open(TODO_FILE, 'r', encoding='utf-8') as f:
                all_todos = json.load(f)
            for i, t in enumerate(all_todos):
                if t.get('id') == self.data.get('id'):
                    clean = {k: v for k, v in self.data.items() if not k.startswith('_')}
                    all_todos[i] = clean
                    break
            with open(TODO_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_todos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TodoDetail] Persist error: {e}")


# ============================================================
# 6. TodoPageV4
# ============================================================
class TodoPageV4(QWidget):
    def __init__(self, theme_name: str = DEFAULT_THEME, parent=None):
        super().__init__(parent)

        self.theme_name = theme_name
        self.pal = _p(theme_name)

        self.todos: List[dict] = []
        self.filter_mode = "all"

        self._load_todos()
        self._build_ui()
        self._refresh_list()

        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self._check_reminders)
        self.reminder_timer.start(60000)

    def _build_ui(self):
        pal = self.pal

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 左侧面板
        left = QFrame()
        left.setObjectName("TodoLeftPanel")
        left.setFixedWidth(360)
        left.setStyleSheet(f"""
            #TodoLeftPanel {{
                background: {pal['card']};
                border-right: 1px solid {pal['border']};
            }}
        """)

        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(24, 24, 24, 24)
        left_layout.setSpacing(18)

        title = QLabel("待办事项")
        title.setFont(QFont("Segoe UI", 25, QFont.Normal))
        title.setStyleSheet(f"color: {pal['text']}; background: transparent;")
        left_layout.addWidget(title)

        quote_idx = QDate.currentDate().dayOfYear() % len(QUOTES)
        quote = QLabel(QUOTES[quote_idx])
        quote.setWordWrap(True)
        quote.setStyleSheet(f"""
            QLabel {{
                color: {pal['secondary']};
                font-size: 13px;
                font-weight: 400;
                line-height: 150%;
                background: transparent;
            }}
        """)
        left_layout.addWidget(quote)

        # 统计卡片 — 重新设计，避免“完成 / 跟进”看不清
        stats_card = QFrame()
        stats_card.setObjectName("StatsCard")
        stats_card.setStyleSheet(f"""
            #StatsCard {{
                background: transparent;
                border: none;
            }}
        """)

        stats_layout = QHBoxLayout(stats_card)
        stats_layout.setContentsMargins(12, 14, 12, 14)
        stats_layout.setSpacing(10)

        self.stat_total_num = QLabel("0")
        self.stat_done_num = QLabel("0")
        self.stat_follow_num = QLabel("0")

        stats_layout.addWidget(self._build_stat_tile("总计", self.stat_total_num, pal["text"]))
        stats_layout.addWidget(self._build_stat_tile("完成", self.stat_done_num, pal["green"]))
        stats_layout.addWidget(self._build_stat_tile("跟进", self.stat_follow_num, pal["blue"]))

        left_layout.addWidget(stats_card)

        # 筛选
        filter_label = QLabel("筛选")
        filter_label.setFont(QFont("Segoe UI", 13, QFont.Normal))
        filter_label.setStyleSheet(f"""
            QLabel {{
                color: {pal['secondary']};
                font-size: 13px;
                font-weight: 400;
                background: transparent;
            }}
        """)
        left_layout.addWidget(filter_label)

        self.filter_buttons = {}

        filter_items = [
            ("全部", "all"),
            ("待完成", "pending"),
            ("已完成", "completed"),
            ("跟进中", "follow_up"),
        ]

        for text, mode in filter_items:
            btn = QPushButton(text)
            btn.setObjectName("NavBtn")
            btn.setFixedHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("active", mode == "all")
            btn.clicked.connect(lambda checked=False, m=mode: self._set_filter(m))
            left_layout.addWidget(btn)
            self.filter_buttons[mode] = btn

        # 跟进总览图 — 暂时隐藏
        # timeline_label = QLabel("跟进总览")
        # timeline_label.setFont(QFont("Segoe UI", 13, QFont.Normal))
        # timeline_label.setStyleSheet(f"""
        #     QLabel {{
        #         color: {pal['secondary']};
        #         font-size: 13px;
        #         font-weight: 400;
        #     }}
        # """)
        # left_layout.addWidget(timeline_label)
        #
        # self.timeline_view = FollowOverviewView(self.theme_name)
        # left_layout.addWidget(self.timeline_view)

        # 活动密度 — 暂时隐藏
        # scurve_label = QLabel("活动密度")
        # scurve_label.setFont(QFont("Segoe UI", 13, QFont.Normal))
        # scurve_label.setStyleSheet(f"""
        #     QLabel {{
        #         color: {pal['secondary']};
        #         font-size: 13px;
        #         font-weight: 400;
        #     }}
        # """)
        # left_layout.addWidget(scurve_label)
        #
        # self.scurve_view = SCurveView(self.theme_name)
        # left_layout.addWidget(self.scurve_view)

        left_layout.addStretch()

        export_btn = QPushButton("导出 Excel")
        export_btn.setObjectName("SecondaryBtn")
        export_btn.setFixedHeight(38)
        export_btn.clicked.connect(self._export_excel)
        left_layout.addWidget(export_btn)

        clear_btn = QPushButton("清除已完成")
        clear_btn.setObjectName("DangerBtn")
        clear_btn.setFixedHeight(38)
        clear_btn.clicked.connect(self._clear_completed)
        left_layout.addWidget(clear_btn)

        layout.addWidget(left)

        # 右侧主区域
        right = QWidget()
        right.setStyleSheet(f"background: {pal['bg']};")

        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(24, 24, 24, 24)
        right_layout.setSpacing(16)

        # 添加卡片
        add_card = QFrame()
        add_card.setObjectName("AddCard")
        add_card.setStyleSheet(f"""
            #AddCard {{
                background: {pal['card']};
                border-radius: {pal['card_radius']}px;
                border: 1px solid {pal['border']};
            }}
        """)
        _ios_shadow(add_card, self.theme_name)

        add_layout = QVBoxLayout(add_card)
        add_layout.setContentsMargins(20, 18, 20, 18)
        add_layout.setSpacing(12)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入待办事项，按 Enter 添加...")
        self.input_field.setMinimumHeight(44)
        self.input_field.returnPressed.connect(self._add_todo)
        add_layout.addWidget(self.input_field)

        opt_row = QHBoxLayout()
        opt_row.setSpacing(12)

        self.quick_priority = QComboBox()
        self.quick_priority.addItem("低", "低")
        self.quick_priority.addItem("中", "中")
        self.quick_priority.addItem("高", "高")
        self.quick_priority.setFixedWidth(96)
        self.quick_priority.setMinimumHeight(40)
        opt_row.addWidget(self.quick_priority)

        self.quick_est = QComboBox()
        for t in ESTIMATED_TIMES:
            self.quick_est.addItem(t)
        self.quick_est.setFixedWidth(112)
        self.quick_est.setMinimumHeight(40)
        opt_row.addWidget(self.quick_est)

        self.quick_followup = QCheckBox("跟进")
        self.quick_followup.setMinimumHeight(40)
        opt_row.addWidget(self.quick_followup)

        opt_row.addStretch()

        add_btn = QPushButton("添加")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.setFixedHeight(40)
        add_btn.clicked.connect(self._add_todo)
        opt_row.addWidget(add_btn)

        add_layout.addLayout(opt_row)
        right_layout.addWidget(add_card)

        # 列表区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background: transparent;")

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(12)
        self.list_layout.addStretch()

        self.scroll_area.setWidget(self.list_container)
        right_layout.addWidget(self.scroll_area, 1)

        layout.addWidget(right, 1)

    def _build_stat_tile(self, title: str, num_label: QLabel, color: str) -> QWidget:
        pal = self.pal

        tile = QWidget()
        tile.setStyleSheet("background: transparent;")

        lay = QVBoxLayout(tile)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(2)

        num_label.setFont(QFont("Segoe UI", 22, QFont.Normal))
        num_label.setAlignment(Qt.AlignCenter)
        num_label.setMinimumWidth(56)
        num_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 22px;
                font-weight: 400;
                background: transparent;
            }}
        """)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setMinimumWidth(56)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {pal['secondary']};
                font-size: 13px;
                font-weight: 400;
                background: transparent;
            }}
        """)

        lay.addWidget(num_label)
        lay.addWidget(title_label)

        return tile

    def _set_filter(self, mode: str):
        self.filter_mode = mode

        for m, btn in self.filter_buttons.items():
            btn.setProperty("active", m == mode)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._refresh_list()

    def _refresh_list(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 排序：未完成在前，已完成在后
        # 同组内按优先级：高→中→低
        # 同优先级内按创建时间倒序（新的在前）
        priority_order = {"高": 0, "中": 1, "低": 2}

        def sort_key(todo):
            completed = 1 if todo.get("completed", False) else 0
            pri = priority_order.get(todo.get("priority", "中"), 1)
            created = todo.get("created_at", "")
            return (completed, pri, created)

        sorted_todos = sorted(self.todos, key=sort_key)

        shown = 0

        for todo in sorted_todos:
            completed = todo.get("completed", False)
            is_follow_up = todo.get("is_follow_up", False)

            if self.filter_mode == "pending" and completed:
                continue
            if self.filter_mode == "completed" and not completed:
                continue
            if self.filter_mode == "follow_up" and not is_follow_up:
                continue

            card = TodoCard(todo, self.theme_name)
            card.toggled.connect(self._on_toggle)
            card.deleted.connect(self._on_delete)
            card.clicked.connect(self._on_card_click)

            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
            shown += 1

        total = len(self.todos)
        done = sum(1 for t in self.todos if t.get("completed"))
        follow = sum(1 for t in self.todos if t.get("is_follow_up"))

        self.stat_total_num.setText(str(total))
        self.stat_done_num.setText(str(done))
        self.stat_follow_num.setText(str(follow))

        # 跟进总览已隐藏，不再刷新
        # if hasattr(self, 'timeline_view'):
        #     self.timeline_view.set_todos(self.todos)
        # if hasattr(self, 'scurve_view'):
        #     self.scurve_view.set_data(self.todos)

        if shown == 0:
            empty = QLabel("🎉 暂无待办事项")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"""
                QLabel {{
                    color: {self.pal['secondary']};
                    font-size: 18px;
                    font-weight: 400;
                    padding: 70px;
                }}
            """)
            self.list_layout.insertWidget(self.list_layout.count() - 1, empty)

        try:
            make_text_selectable(self)
        except Exception:
            pass

    def _add_todo(self):
        text = self.input_field.text().strip()
        if not text:
            return

        todo = {
            "id": max([t.get("id", 0) for t in self.todos], default=0) + 1,
            "title": text,
            "completed": False,
            "priority": self.quick_priority.currentData(),
            "created_at": datetime.now().isoformat(),
            "estimated_time": self.quick_est.currentText(),
            "is_follow_up": False,
            "follow_up_date": "",
            "follow_up_reminder": False,
            "follow_up_history": [],
            "attachments": [],
        }

        if self.quick_followup.isChecked():
            todo["is_follow_up"] = True
            todo["follow_up_date"] = QDate.currentDate().toString("yyyy-MM-dd")
            todo["follow_up_reminder"] = False
            todo["follow_up_history"] = []

        self.todos.insert(0, todo)

        self.input_field.clear()
        self.quick_followup.setChecked(False)

        self._save_todos()
        self._refresh_list()

    def _on_card_click(self, data: dict):
        dialog = TodoDetailDialog(data, self.theme_name, self)
        dialog.exec()
        # 无论弹窗以何种方式关闭，都重新加载文件并刷新
        self._load_todos()
        self._refresh_list()

    def _on_toggle(self, data: dict):
        self._save_todos()
        self._refresh_list()

    def _on_delete(self, data: dict):
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除「{data.get('title', '')}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.todos = [t for t in self.todos if t is not data]

            todo_id = data.get("id")
            if todo_id:
                att_dir = ATTACHMENTS_DIR / str(todo_id)
                if att_dir.exists():
                    shutil.rmtree(att_dir, ignore_errors=True)

            self._save_todos()
            self._refresh_list()

    def _clear_completed(self):
        before = len(self.todos)
        self.todos = [t for t in self.todos if not t.get("completed")]

        if len(self.todos) < before:
            self._save_todos()
            self._refresh_list()

    def _export_excel(self):
        from PySide6.QtWidgets import QFileDialog as QFD

        default_name = f"todos_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        save_path, _ = QFD.getSaveFileName(
            self, "导出待办事项", default_name, "Excel (*.xlsx)"
        )
        if not save_path:
            return

        try:
            if HAS_DB:
                path = todo_db.export_to_excel(save_path)
            else:
                from openpyxl import Workbook
                wb = Workbook()
                ws = wb.active
                ws.title = "待办事项"
                headers = ["ID", "标题", "优先级", "已完成", "建立时间", "完成时间",
                           "预估时间", "是否跟进", "跟进日期", "跟进提醒",
                           "跟进历史", "附件", "备注"]
                ws.append(headers)
                for t in self.todos:
                    history = t.get("follow_up_history", [])
                    history_str = "; ".join(f"{h.get('date','')} {h.get('note','')}" for h in history) if history else ""
                    attachments = t.get("attachments", [])
                    att_str = "; ".join(a.get("name","") for a in attachments) if attachments else ""
                    ws.append([
                        t.get("id",""), t.get("title",""), t.get("priority",""),
                        "是" if t.get("completed") else "否",
                        t.get("created_at",""), t.get("completed_at",""),
                        t.get("estimated_time",""),
                        "是" if t.get("is_follow_up") else "否",
                        t.get("follow_up_date",""),
                        "是" if t.get("follow_up_reminder") else "否",
                        history_str, att_str, t.get("note",""),
                    ])
                wb.save(save_path)
                path = save_path

            QMessageBox.information(self, "导出成功", f"已导出到:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出出错:\n{e}")

    def _check_reminders(self):
        today = QDate.currentDate().toString("yyyy-MM-dd")

        for todo in self.todos:
            if not todo.get("is_follow_up"):
                continue
            if not todo.get("follow_up_reminder"):
                continue

            fu_date = todo.get("follow_up_date", "")

            if fu_date == today and todo.get("_last_reminder") != today:
                todo["_last_reminder"] = today
                QMessageBox.information(
                    self,
                    "跟进提醒",
                    f"📅 今天需要跟进：\n\n"
                    f"{todo.get('title', '')}\n\n"
                    f"上次跟进备注：{self._last_note(todo)}"
                )

    def _last_note(self, todo: dict) -> str:
        history = todo.get("follow_up_history", [])
        if history:
            return history[-1].get("note", "无")
        return "无"

    def _load_todos(self):
        if HAS_DB:
            try:
                self.todos = todo_db.load_all()
                return
            except Exception:
                pass

        if TODO_FILE.exists():
            try:
                raw = json.loads(TODO_FILE.read_text(encoding="utf-8"))
                self.todos = []

                for t in raw:
                    t.setdefault("estimated_time", "")
                    t.setdefault("is_follow_up", False)
                    t.setdefault("follow_up_date", "")
                    t.setdefault("follow_up_reminder", False)
                    t.setdefault("follow_up_history", [])
                    t.setdefault("attachments", [])
                    t.setdefault("created_at", datetime.now().isoformat())
                    t.setdefault("completed", False)
                    t.setdefault("priority", "中")
                    t.setdefault("completed_at", "")
                    t.setdefault("note", "")
                    self.todos.append(t)

            except Exception:
                self.todos = []
        else:
            self.todos = []

    def _save_todos(self):
        clean = []

        for t in self.todos:
            item = {k: v for k, v in t.items() if not k.startswith("_")}
            clean.append(item)

        # 写 JSON（兼容旧逻辑）
        TODO_FILE.parent.mkdir(exist_ok=True)
        TODO_FILE.write_text(
            json.dumps(clean, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # 写 SQLite
        if HAS_DB:
            try:
                for t in clean:
                    todo_db.save_todo(t)
            except Exception:
                pass