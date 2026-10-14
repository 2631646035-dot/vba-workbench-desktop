"""Small left-side always-on-top pending task window; shares the primary task store."""
from datetime import date
import time
from PySide6.QtCore import Qt,QTimer,QRect
from PySide6.QtWidgets import QWidget,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QScrollArea,QFrame,QMessageBox,QLayout,QSizeGrip
from companion_interaction import FloatingCompanion
from PySide6.QtGui import QPainter,QPen,QColor
from task_store import timer_state,timestamp

class DoubleClickLabel(QLabel):
    def __init__(self,text,callback,parent=None):
        super().__init__(text,parent); self.callback=callback
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.LeftButton: self.callback(); event.accept()
        else: super().mouseDoubleClickEvent(event)

class CompactTaskRow(QFrame):
    def __init__(self,task,window):
        super().__init__(); self.task=task; self.window_ref=window
        self.minutes_only=window.store.setting('timer_display:'+task['id'],'clock')=='minutes'
        self.setMouseTracking(True); self.setStyleSheet('CompactTaskRow{border:1px solid #DCE7E0;border-radius:9px;}')
        box=QVBoxLayout(self); box.setContentsMargins(8,8,8,8); row=QHBoxLayout(); box.addLayout(row)
        self.badge=DoubleClickLabel('●',self.toggle_display); self.badge.setAlignment(Qt.AlignCenter); row.addWidget(self.badge)
        self.name=DoubleClickLabel(task['title'],self.activate); self.name.setTextFormat(Qt.PlainText); self.name.setWordWrap(True); row.addWidget(self.name,1)
        self.name.setCursor(Qt.PointingHandCursor); self.badge.setCursor(Qt.PointingHandCursor)
        window.page.template_tags(box,task); self.update_timer()

    def state(self): return timer_state(self.task,date.today().isoformat())
    def activate(self):
        if self.state()['started']: self.window_ref.finish(self.task)
        else: self.window_ref.start_task(self.task)
    def toggle_display(self):
        if not self.state()['started']: self.activate(); return
        selected=not self.minutes_only
        try: self.window_ref.store.set_setting('timer_display:'+self.task['id'],'minutes' if selected else 'clock')
        except Exception as exc: QMessageBox.warning(self,'无法保存显示设置',str(exc)); return
        self.minutes_only=selected; self.update_timer()
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.LeftButton: self.activate(); event.accept()
        else: super().mouseDoubleClickEvent(event)
    def contextMenuEvent(self,event):
        state=self.state()
        if not state['started']: return
        resume=state['paused'] or state['finished']
        question='继续这个任务的计时吗？' if resume else '暂停这个任务的计时吗？暂停期间不累计时间。'
        if QMessageBox.question(self,'继续计时' if resume else '暂停计时',question,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            try: self.window_ref.store.pause_task(self.task['id'],date.today().isoformat(),not resume)
            except Exception as exc: QMessageBox.warning(self,'无法保存',str(exc)); return
            self.window_ref.refresh(); self.window_ref.page.refresh()
        event.accept()
    def update_timer(self,at=None):
        state=timer_state(self.task,date.today().isoformat(),at); priority=self.task.get('priority','中')
        color={'高':'#E65E5E','中':'#D8AC34','低':'#4EAF73'}.get(priority,'#D8AC34')
        if state['started']:
            seconds=int(state['seconds']); self.badge.setFixedWidth(65)
            self.badge.setText(f'{seconds/60:.1f}分' if self.minutes_only else f'{seconds//60:02d}:{seconds%60:02d}')
            self.badge.setToolTip(priority+'优先级 · 双击时间切换 分:秒 / 分钟 · 右键暂停或继续')
            self.badge.setAccessibleName(('已暂停 ' if state['paused'] else '计时 ')+self.badge.text())
            # Blink softly without hiding the value or changing its geometry.
            if state['paused'] and int(time.monotonic()*2)%2: color='#B7C8BE'
            self.badge.setStyleSheet('color:'+color+';font-size:12px;font-weight:600;')
        else:
            self.badge.setFixedWidth(18); self.badge.setText('●'); self.badge.setToolTip(priority+'优先级 · 双击任务开始')
            self.badge.setAccessibleName(priority+'优先级'); self.badge.setStyleSheet('color:'+color+';font-size:18px;')
        hint='双击任务名称完成 · 右键继续计时' if state['paused'] or state['finished'] else '再次双击任务名称完成 · 右键暂停' if state['started'] else '双击任务名称开始'
        self.name.setToolTip(hint); self.setToolTip(hint)

class VisibleSizeGrip(QSizeGrip):
    def paintEvent(self,event):
        painter=QPainter(self); painter.setPen(QPen(QColor('#7B998A'),2))
        for offset in (4,9,14): painter.drawLine(self.width()-offset,self.height()-2,self.width()-2,self.height()-offset)
        painter.end()

class DragHeader(QLabel):
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self._drag=None
            if not self.window().windowHandle() or not self.window().windowHandle().startSystemMove():
                self._drag=event.globalPosition().toPoint()-self.window().pos()
    def mouseMoveEvent(self,event):
        if event.buttons() & Qt.LeftButton and getattr(self,'_drag',None) is not None:
            self.window().move(event.globalPosition().toPoint()-self._drag)
    def mouseReleaseEvent(self,event): self._drag=None

class CompactTasks(QWidget):
    def __init__(self,store,owner,page):
        super().__init__(None,Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.store=store; self.owner=owner; self.page=page; self.last_completed=None
        self._signature=None
        self._resizing=None; self.setMouseTracking(True)
        self.setWindowTitle('待做任务 · 悬浮清单'); self.resize(300,460); self.setMinimumSize(260,240)
        self.setStyleSheet('QWidget{background:#F3F6F3;color:#263F34;font-size:13px;} QPushButton{background:#FFFFFF;border:1px solid #CAD8CF;border-radius:8px;padding:7px;} QPushButton:hover{background:#E3EEE8;}')
        layout=QVBoxLayout(self); layout.setContentsMargins(12,12,12,12)
        header=QHBoxLayout(); layout.addLayout(header)
        self.title=DragHeader('待做任务'); self.title.setStyleSheet('font-size:15px;font-weight:600;'); header.addWidget(self.title,1)
        restore=QPushButton('↗'); restore.setToolTip('返回主窗口'); restore.clicked.connect(self.close); header.addWidget(restore)
        close=QPushButton('×'); close.setToolTip('收起悬浮窗并返回主窗口'); close.clicked.connect(self.close); header.addWidget(close)
        self.companion=FloatingCompanion(store,page,self); layout.addWidget(self.companion)
        hint=QLabel('左键挠痒 · 右键抛任务'); hint.setAlignment(Qt.AlignCenter); layout.addWidget(hint)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); layout.addWidget(self.scroll,1)
        self.content=QWidget(); self.rows=QVBoxLayout(self.content); self.scroll.setWidget(self.content)
        self.rows.setSizeConstraint(QLayout.SetMinAndMaxSize)
        footer=QHBoxLayout(); layout.addLayout(footer)
        self.undo=QPushButton('撤销上一次完成'); self.undo.setEnabled(False); self.undo.clicked.connect(self.undo_last); footer.addWidget(self.undo,1)
        grip=VisibleSizeGrip(self); grip.setFixedSize(18,18); grip.setToolTip('拖动调整窗口大小'); footer.addWidget(grip,0,Qt.AlignBottom)
        self.title.setToolTip('按住标题拖动窗口 · 拖边缘或右下角调整大小')
        self.timer=QTimer(self); self.timer.setInterval(2000); self.timer.timeout.connect(self.refresh); self.timer.start()
        self.clock_timer=QTimer(self); self.clock_timer.setInterval(500); self.clock_timer.timeout.connect(self.update_timers); self.clock_timer.start()
        screen=self.screen().availableGeometry(); self.move(screen.left()+12,screen.top()+max(12,(screen.height()-self.height())//3))
        self.refresh()

    def update_timers(self):
        if not self.isVisible() or self.isMinimized(): return
        now=timestamp()
        for row in self.content.findChildren(CompactTaskRow):
            if row.isVisible(): row.update_timer(now)

    def resize_edges(self,position):
        edges=Qt.Edge(0)
        if position.x()<8: edges|=Qt.LeftEdge
        if position.x()>self.width()-8: edges|=Qt.RightEdge
        if position.y()<8: edges|=Qt.TopEdge
        if position.y()>self.height()-8: edges|=Qt.BottomEdge
        return edges

    def mousePressEvent(self,event):
        edges=self.resize_edges(event.position())
        if event.button()==Qt.LeftButton and edges:
            if not self.windowHandle() or not self.windowHandle().startSystemResize(edges):
                self._resizing=(edges,event.globalPosition().toPoint(),QRect(self.geometry()))
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self._resizing:
            edges,start,original=self._resizing; delta=event.globalPosition().toPoint()-start; rect=QRect(original)
            if edges & Qt.LeftEdge: rect.setLeft(min(original.left()+delta.x(),original.right()-self.minimumWidth()+1))
            if edges & Qt.RightEdge: rect.setRight(max(original.right()+delta.x(),original.left()+self.minimumWidth()-1))
            if edges & Qt.TopEdge: rect.setTop(min(original.top()+delta.y(),original.bottom()-self.minimumHeight()+1))
            if edges & Qt.BottomEdge: rect.setBottom(max(original.bottom()+delta.y(),original.top()+self.minimumHeight()-1))
            self.setGeometry(rect); return
        edges=self.resize_edges(event.position())
        diagonal=(edges & Qt.LeftEdge and edges & Qt.TopEdge) or (edges & Qt.RightEdge and edges & Qt.BottomEdge)
        other=(edges & Qt.RightEdge and edges & Qt.TopEdge) or (edges & Qt.LeftEdge and edges & Qt.BottomEdge)
        self.setCursor(Qt.SizeFDiagCursor if diagonal else Qt.SizeBDiagCursor if other else Qt.SizeHorCursor if edges & (Qt.LeftEdge|Qt.RightEdge) else Qt.SizeVerCursor if edges else Qt.ArrowCursor)

    def mouseReleaseEvent(self,event): self._resizing=None; super().mouseReleaseEvent(event)

    def refresh(self):
        day=date.today().isoformat(); pending=[t for t,done in self.store.today(day) if not done]
        signature=repr((day,pending))
        if signature==self._signature: return
        self._signature=signature
        while self.rows.count():
            item=self.rows.takeAt(0)
            if item.widget(): item.widget().hide(); item.widget().deleteLater()
        self.title.setText('待做任务 · '+str(len(pending)))
        pending.sort(key=lambda t:{'高':0,'中':1,'低':2}.get(t.get('priority'),1))
        for task in pending: self.rows.addWidget(CompactTaskRow(task,self))
        if not pending: self.rows.addWidget(QLabel('今天的任务已清空。'))
        self.rows.addStretch()
        if self.last_completed and self.last_completed[1]!=day: self.last_completed=None; self.undo.setEnabled(False)

    def start_task(self,task):
        if self.page.begin_task(task): self.refresh()

    def finish(self,task):
        day=date.today().isoformat()
        try:
            # A stale visible button must never undo a completion made elsewhere.
            if not any(t['id']==task['id'] and not done for t,done in self.store.today(day)): self.refresh(); return
            self.store.toggle(task,day)
        except Exception as exc: QMessageBox.warning(self,'无法保存',str(exc)); return
        self.last_completed=(task,day); self.undo.setEnabled(True); self.refresh(); self.page.refresh()

    def undo_last(self):
        if self.last_completed:
            task,day=self.last_completed
            try:
                if any(tid==task['id'] and d==day for tid,d,_ in self.store.completed()): self.store.toggle(task,day)
            except Exception as exc: QMessageBox.warning(self,'无法保存',str(exc)); return
            self.last_completed=None; self.undo.setEnabled(False); self.refresh(); self.page.refresh()

    def closeEvent(self,event):
        self.timer.stop(); self.clock_timer.stop(); self.companion.timer.stop(); self.owner.showNormal(); self.owner.raise_(); self.owner.activateWindow(); self.page.refresh(); event.accept()
