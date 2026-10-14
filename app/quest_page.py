"""A quiet, game-like daily routine UI; reuses the existing routine storage/dialogs."""
from datetime import datetime
from PySide6.QtCore import Qt, QDate, QTimer, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QComboBox, QScrollArea, QCheckBox, QMenu)
from routines_page import RoutinePage, RoutineEditDialog, is_due_today, is_done_today, repeat_text, save_routines


def completion_summary(routines, today=None):
    today = today or QDate.currentDate()
    due = [r for r in routines if is_due_today(r, today)]
    done = sum(is_done_today(r, today.toString('yyyy-MM-dd')) for r in due)
    return len(due), done, done * 20


class ProgressRing(QWidget):
    def __init__(self, pal, parent=None):
        super().__init__(parent)
        self.pal, self._value = pal, 0.0
        self.setFixedSize(112, 112)
        self.animation = QPropertyAnimation(self, b'progress', self)
        self.animation.setDuration(550)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def get_progress(self):
        return self._value

    def set_progress(self, value):
        self._value = value
        self.update()

    progress = Property(float, get_progress, set_progress)

    def advance(self, value, animated=True):
        self.animation.stop()
        if animated:
            self.animation.setStartValue(self._value)
            self.animation.setEndValue(float(value))
            self.animation.start()
        else:
            self.set_progress(float(value))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(10, 10, -10, -10)
        p.setPen(QPen(QColor(self.pal['border']), 7))
        p.drawEllipse(rect)
        pen = QPen(QColor(self.pal['primary']), 7)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 90 * 16, -int(self._value * 360 * 16))
        p.setPen(QColor(self.pal['text']))
        p.setFont(QFont('Microsoft YaHei UI', 20))
        p.drawText(self.rect(), Qt.AlignCenter, f'{round(self._value * 100)}%')


class QuestPage(RoutinePage):
    def _label(self, text, size=14, color='text'):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.PlainText)
        label.setStyleSheet(f"color:{self.pal[color]};font-size:{size}px;background:transparent;border:0;")
        return label

    def _button(self, text, slot, primary=False):
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumHeight(36)
        button.setObjectName('PrimaryBtn' if primary else 'QuestButton')
        button.clicked.connect(slot)
        return button

    def _build(self):
        self._day = QDate.currentDate().toString('yyyy-MM-dd')
        self.filter_mode = '今日任务'
        p = self.pal
        self.setObjectName('QuestPage')
        self.setStyleSheet(f'''
            #QuestPage {{ background:{p['bg']}; }}
            QFrame#QuestPanel {{ background:{p['card']};border:1px solid {p['border']};border-radius:18px; }}
            QPushButton#QuestButton {{ background:{p['card']};color:{p['secondary']};border:1px solid {p['border']};border-radius:10px;padding:8px 14px; }}
            QPushButton#QuestButton:hover {{ background:{p['hover']};color:{p['primary']};border-color:{p['primary']}; }}
            QPushButton#QuestButton:pressed {{ background:{p['selection_bg']}; }}
            QPushButton:focus {{ border:2px solid {p['primary']}; }}
        ''')
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(18)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(self._label('DAILY QUEST / 日常工作', 11, 'muted'))
        titles.addWidget(self._label('今日任务', 30))
        self.date_label = self._label('', 13, 'secondary')
        titles.addWidget(self.date_label)
        header.addLayout(titles, 1)
        header.addWidget(self._button('+ 新建任务', self._add_routine, True))
        root.addLayout(header)

        hero = QFrame()
        hero.setObjectName('QuestPanel')
        hero.setMinimumHeight(146)
        row = QHBoxLayout(hero)
        row.setContentsMargins(20, 16, 20, 16)
        self.ring = ProgressRing(p)
        row.addWidget(self.ring)
        words = QVBoxLayout()
        self.progress_title = self._label('', 23)
        self.progress_note = self._label('', 13, 'secondary')
        words.addWidget(self.progress_title)
        words.addWidget(self.progress_note)
        words.addWidget(self._label('每完成一项 +20 XP · 积分只用于记录今日进展', 12, 'muted'))
        row.addLayout(words, 1)
        score = QVBoxLayout()
        score.addWidget(self._label('今日获得', 12, 'muted'))
        self.xp = self._label('0 XP', 27, 'primary')
        score.addWidget(self.xp)
        self.badge = self._label('今日通关', 12, 'primary')
        self.badge.setStyleSheet(f"color:{p['primary']};background:{p['hover']};border-radius:8px;padding:6px 10px;font-size:12px;")
        score.addWidget(self.badge)
        row.addLayout(score)
        root.addWidget(hero)

        self.feedback = self._label('一次完成一件事，今天的进度由你掌握。', 13, 'secondary')
        self.feedback.setMinimumHeight(32)
        self.feedback_timer = QTimer(self)
        self.feedback_timer.setSingleShot(True)
        self.feedback_timer.timeout.connect(self._clear_feedback)
        root.addWidget(self.feedback)

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('搜索任务、备注或标签…')
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(120)
        self.search.textChanged.connect(self._refresh)
        controls.addWidget(self.search, 1)
        self.filter = QComboBox()
        self.filter.addItems(['今日任务', '待完成', '已完成', '全部周期'])
        self.filter.setCursor(Qt.PointingHandCursor)
        self.filter.currentTextChanged.connect(self._refresh)
        controls.addWidget(self.filter)
        self.motion = QCheckBox('轻量动画')
        self.motion.setChecked(True)
        self.motion.setCursor(Qt.PointingHandCursor)
        controls.addWidget(self.motion)
        root.addLayout(controls)

        self.section_label = self._label('', 13, 'muted')
        root.addWidget(self.section_label)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet('border:0;background:transparent;')
        self.content = QWidget()
        self.content.setStyleSheet('background:transparent;')
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 6, 0)
        self.content_layout.setSpacing(10)
        self.content_layout.addStretch()
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)
        self.week_label = self._label('', 12, 'muted')
        root.addWidget(self.week_label)

    def _refresh(self, *_):
        today = QDate.currentDate()
        day = today.toString('yyyy-MM-dd')
        self._clear_content()
        total, done, xp = completion_summary(self.routines, today)
        self.ring.advance(done / total if total else 0, self.motion.isChecked())
        self.xp.setText(f'{xp} XP')
        self.badge.setVisible(bool(total and done == total))
        self.date_label.setText(today.toString('yyyy年M月d日') + ' · 完成记录按天保存')
        self.progress_title.setText('今日任务全部完成' if total and done == total else f'已完成 {done} / {total} 项')
        self.progress_note.setText('今天没有到期任务，可以休息或安排下一项。' if not total else
                                  '收工徽章已解锁，给今天的自己一个赞。' if done == total else f'还有 {total - done} 项，按自己的节奏推进。')
        query, mode = self.search.text().strip().casefold(), self.filter.currentText()
        items = []
        for r in self.routines:
            due, complete = is_due_today(r, today), is_done_today(r, day)
            if mode != '全部周期' and not due:
                continue
            if mode == '待完成' and complete or mode == '已完成' and not complete:
                continue
            haystack = ' '.join([r.get('title', ''), r.get('note', '')] +
                                [str(t.get('key','')) + str(t.get('value','')) for t in r.get('tags', [])])
            if query and query not in haystack.casefold():
                continue
            items.append(r)
        items.sort(key=lambda r: (not is_due_today(r, today), is_done_today(r, day)))
        self.section_label.setText(f'{mode} · {len(items)} 项    /    标记完成不会自动执行工作流')
        for r in items:
            self.content_layout.insertWidget(self.content_layout.count() - 1, self._card(r))
        if not items:
            empty = self._label('没有匹配的任务。试试清除搜索、更换筛选，或新建一项任务。', 15, 'secondary')
            empty.setAlignment(Qt.AlignCenter)
            empty.setMinimumHeight(130)
            self.content_layout.insertWidget(0, empty)
        week_done = 0
        for offset in range(7):
            date = today.addDays(-offset)
            week_done += sum(is_done_today(r, date.toString('yyyy-MM-dd')) for r in self.routines)
        self.week_label.setText(f'近7天已完成 {week_done} 次任务    ·    今日积分由完成记录计算，撤销后同步扣回，不会重复领取。')

    def _card(self, data):
        p = self.pal
        due, done = is_due_today(data), is_done_today(data)
        frame = QFrame()
        frame.setObjectName('QuestPanel')
        frame.setStyleSheet(f'''QFrame#QuestPanel {{background:{p['card']};border:1px solid {p['border']};border-radius:14px;}}
                              QFrame#QuestPanel:hover {{border-color:{p['primary']};}}''')
        row = QHBoxLayout(frame)
        row.setContentsMargins(18, 16, 18, 16)
        row.setSpacing(16)
        icon = self._label('●' if done else '○', 23, 'primary' if done else 'muted')
        icon.setFixedWidth(28)
        row.addWidget(icon)
        info = QVBoxLayout()
        title = self._label(data.get('title') or '未命名任务', 16, 'secondary' if done else 'text')
        info.addWidget(title)
        tags = ' · '.join(f"{t.get('key','')}：{t.get('value','')}" for t in data.get('tags', []))
        info.addWidget(self._label(repeat_text(data) + (' · ' + tags if tags else '') +
                                   (' · 已停用' if not data.get('enabled', True) else ''), 12, 'muted'))
        if data.get('note'):
            note = str(data['note'])
            info.addWidget(self._label(note[:110] + ('…' if len(note) > 110 else ''), 12, 'secondary'))
        row.addLayout(info, 1)
        edit = QPushButton('详情 ···')
        edit.setObjectName('QuestButton')
        edit.setCursor(Qt.PointingHandCursor)
        menu = QMenu(edit)
        menu.addAction('查看 / 编辑任务', lambda r=data: self._on_card_click(r))
        menu.addSeparator()
        menu.addAction('删除任务…', lambda r=data: self._on_delete(r))
        edit.setMenu(menu)
        edit.setToolTip('编辑任务，或确认后删除')
        row.addWidget(edit)
        action = self._button('撤销完成' if done else '完成 +20 XP' if due else '未到期',
                              lambda _=False, r=data: self._complete(r), due and not done)
        action.setEnabled(due)
        action.setMinimumWidth(112)
        row.addWidget(action)
        return frame

    def _complete(self, data):
        if not is_due_today(data):
            return
        day = QDate.currentDate().toString('yyyy-MM-dd')
        old = is_done_today(data, day)
        before = dict(data.get('check_log') or {})
        data.setdefault('check_log', {})[day] = {'done': not old, 'time': datetime.now().isoformat()}
        try:
            save_routines(self.routines)
        except OSError:
            data['check_log'] = before
            self.feedback.setText('保存失败，完成状态未改变。请检查目录权限后重试。')
            return
        self._refresh()
        self.feedback.setText('已撤销完成 · 今日积分 -20 XP' if old else '任务完成！+20 XP · 又推进了一步。')
        self.feedback.setStyleSheet(f"color:{self.pal['primary']};background:{self.pal['hover']};border-radius:8px;padding:8px 12px;font-size:13px;")
        self.feedback_timer.start(4500)

    def _clear_feedback(self):
        self.feedback.setText('进度已保存。完成标记可随时撤销。')
        self.feedback.setStyleSheet(f"color:{self.pal['secondary']};background:transparent;font-size:13px;border:0;")

    def _check_reminders(self):
        # Quiet in-page reminders, including midnight rollover; no modal interruption.
        day = QDate.currentDate().toString('yyyy-MM-dd')
        if day != self._day:
            self._day = day
            self._refresh()
            self.feedback.setText('新的一天，今日任务已更新；历史完成记录仍保留。')
