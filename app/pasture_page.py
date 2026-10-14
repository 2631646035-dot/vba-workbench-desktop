"""Two views of one task list: quiet office and animated little horse workstations."""
import math
import shutil
import uuid
import copy
from pathlib import Path
from datetime import date, datetime
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QUrl
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QDesktopServices, QPainterPath
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QComboBox, QScrollArea, QDialog, QFormLayout, QSpinBox, QTextEdit, QCheckBox,
    QDateEdit, QDateTimeEdit, QFileDialog, QListWidget, QMessageBox, QLayout)
from task_store import TaskStore, new_task, timer_state

PRIORITIES = {'高': '#E87B70', '中': '#D5AC55', '低': '#54AFA1'}

class TaskEditor(QDialog):
    def __init__(self, store, task=None, parent=None):
        super().__init__(parent)
        self.store = store; self.task = copy.deepcopy(task or new_task()); self.files = list(self.task.get('attachments', []))
        self.setWindowTitle('任务工位 · 编辑' if task else '新增任务工位'); self.resize(620, 700)
        layout = QVBoxLayout(self); scroll=QScrollArea(); scroll.setWidgetResizable(True); content=QWidget(); form = QFormLayout(content); scroll.setWidget(content); layout.addWidget(scroll,1)
        self.title = QLineEdit(self.task.get('title', '')); form.addRow('任务名称', self.title)
        self.priority = QComboBox(); self.priority.addItems(['高', '中', '低']); self.priority.setCurrentText(self.task.get('priority','中'))
        form.addRow('重要性',self.priority)
        self.duration = QSpinBox(); self.duration.setRange(0, 10080); self.duration.setSuffix(' 分钟'); self.duration.setSpecialValueText('未估时')
        self.duration.setValue(self.task.get('minutes',0)); form.addRow('预估用时',self.duration)
        self.start = QDateEdit(); self.start.setCalendarPopup(True)
        from PySide6.QtCore import QDate
        self.start.setDate(QDate.fromString(self.task.get('start',date.today().isoformat()),'yyyy-MM-dd')); form.addRow('开始日期',self.start)
        self.enabled = QCheckBox('启用任务'); self.enabled.setChecked(self.task.get('enabled',True)); form.addRow(self.enabled)
        self.follow = QCheckBox('需要后续跟进'); self.follow.setChecked(self.task.get('is_follow_up',False)); form.addRow(self.follow)
        self.follow_date = QDateEdit(); self.follow_date.setCalendarPopup(True)
        self.follow_date.setDate(QDate.fromString(self.task.get('follow_up_date') or date.today().isoformat(),'yyyy-MM-dd'))
        form.addRow('跟进日期',self.follow_date); self.follow_date.setEnabled(self.follow.isChecked()); self.follow.toggled.connect(self.follow_date.setEnabled)
        self.recurring = QCheckBox('设为周期任务'); self.recurring.setChecked(bool(self.task.get('repeat'))); form.addRow(self.recurring)
        self.schedule = QWidget(); schedule = QFormLayout(self.schedule); schedule.setContentsMargins(0,0,0,0)
        self.repeat = QComboBox(); self.repeat.addItems(['每天','每周','每月'])
        self.repeat.setCurrentIndex({'daily':0,'weekly':1,'monthly':2}.get(self.task.get('repeat'),0)); schedule.addRow('重复方式',self.repeat)
        self.days = QLineEdit(); self.days.setPlaceholderText('逗号分隔，例如 1,3,5')
        self.days.setText(','.join(map(str,self.task.get('weekdays' if self.repeat.currentIndex()==1 else 'month_days',[]))))
        self.days_label = QLabel(); schedule.addRow(self.days_label,self.days); form.addRow(self.schedule)
        self.deadline_check=QCheckBox('设定完成期限（超期显示提醒）'); self.deadline_check.setChecked(bool(self.task.get('deadline') or self.task.get('deadline_time'))); form.addRow(self.deadline_check)
        self.deadline=QDateTimeEdit(); self.deadline.setCalendarPopup(True)
        from PySide6.QtCore import QDateTime
        self.deadline.setDateTime(QDateTime.fromString(self.task.get('deadline') or date.today().isoformat()+'T'+self.task.get('deadline_time','18:00:00'),Qt.ISODate))
        form.addRow('完成期限（周期任务只用时刻）',self.deadline)
        self.deadline.setEnabled(self.deadline_check.isChecked()); self.deadline_check.toggled.connect(self.deadline.setEnabled)
        self.recurring.toggled.connect(self.schedule.setVisible); self.schedule.setVisible(self.recurring.isChecked())
        self.repeat.currentIndexChanged.connect(self.schedule_hint); self.schedule_hint()
        self.note = QTextEdit(); self.note.setPlaceholderText('备注、交接信息和链接都放这里。'); self.note.setPlainText(self.task.get('note',''))
        form.addRow('备注 / 链接',self.note)
        self.attachments = QListWidget(); self.attachments.setMaximumHeight(110); form.addRow('附件',self.attachments); self.render_files()
        self.template_list=QListWidget(); self.template_list.setMaximumHeight(95); form.addRow('关联模板标签（可多选）',self.template_list)
        self.load_templates(self.task.get('template_ids',[]))
        manage=QPushButton('管理 SOP / 邮件 / 微信话术模板'); manage.clicked.connect(self.manage_templates); form.addRow(manage)
        row = QHBoxLayout(); layout.addLayout(row)
        add = QPushButton('＋ 添加文件'); add.clicked.connect(self.add_files); row.addWidget(add)
        remove = QPushButton('移除选中附件'); remove.clicked.connect(self.remove_file); row.addWidget(remove); row.addStretch()
        controls = QHBoxLayout(); layout.addLayout(controls); controls.addStretch()
        cancel = QPushButton('取消'); cancel.clicked.connect(self.reject); controls.addWidget(cancel)
        save = QPushButton('保存任务'); save.clicked.connect(self.commit); controls.addWidget(save)

    def schedule_hint(self):
        index = self.repeat.currentIndex(); self.days.setVisible(index != 0); self.days_label.setVisible(index != 0)
        self.days_label.setText('星期（1=周一，7=周日）' if index==1 else '每月日期（1–31）')

    def template_ids(self):
        return [self.template_list.item(i).data(Qt.UserRole) for i in range(self.template_list.count()) if self.template_list.item(i).checkState()==Qt.Checked]

    def load_templates(self,selected):
        from PySide6.QtWidgets import QListWidgetItem
        self.template_list.clear(); entries=self.store.templates(); known={t['id'] for t in entries}
        entries+= [{'id':key,'title':'未找到的模板（可取消关联）','kind':'缺失'} for key in selected if key not in known]
        for template in entries:
            item=QListWidgetItem(template.get('kind','SOP')+' · '+template['title']); item.setData(Qt.UserRole,template['id'])
            item.setFlags(item.flags()|Qt.ItemIsUserCheckable); item.setCheckState(Qt.Checked if template['id'] in selected else Qt.Unchecked); self.template_list.addItem(item)

    def manage_templates(self):
        from template_library import TemplateLibrary
        selected=self.template_ids(); TemplateLibrary(self.store,parent=self).exec(); self.load_templates(selected)

    def render_files(self):
        self.attachments.clear(); self.attachments.addItems([f.get('name',Path(f.get('path','')).name) for f in self.files])

    def add_files(self):
        names,_ = QFileDialog.getOpenFileNames(self,'添加任务附件')
        self.files.extend({'name':Path(p).name,'path':p,'pending':True} for p in names); self.render_files()

    def remove_file(self):
        i = self.attachments.currentRow()
        if i>=0: self.files.pop(i); self.render_files()

    def commit(self):
        if not self.title.text().strip():
            QMessageBox.warning(self,'还差任务名称','给这个工位起个名字再保存。'); return
        repeat = ['daily','weekly','monthly'][self.repeat.currentIndex()] if self.recurring.isChecked() else ''
        days = []
        if repeat in ('weekly','monthly'):
            try:
                days = sorted(set(int(s.strip()) for s in self.days.text().replace('，',',').split(',') if s.strip()))
                if not days or not all(1<=n<=(7 if repeat=='weekly' else 31) for n in days): raise ValueError()
            except ValueError:
                QMessageBox.warning(self,'日期格式','请填写有效日期，用逗号分隔。'); return
        copied = []; saved_files=[]
        try:
            for f in self.files:
                if f.get('pending'):
                    directory = self.store.root / 'config' / 'task_attachments'; directory.mkdir(exist_ok=True)
                    target = directory / (uuid.uuid4().hex + Path(f['path']).suffix)
                    shutil.copy2(f['path'],target); copied.append(target)
                    f = {'name':f['name'], 'path':str(target.relative_to(self.store.root)), 'managed':True}
                saved_files.append(f)
            self.task.update(title=self.title.text().strip(),priority=self.priority.currentText(),minutes=self.duration.value(),
                start=self.start.date().toString('yyyy-MM-dd'),repeat=repeat,weekdays=days if repeat=='weekly' else [],
                month_days=days if repeat=='monthly' else [],note=self.note.toPlainText(), enabled=self.enabled.isChecked(),
                is_follow_up=self.follow.isChecked(),follow_up_date=self.follow_date.date().toString('yyyy-MM-dd'),
                deadline=self.deadline.dateTime().toString(Qt.ISODate) if self.deadline_check.isChecked() and not repeat else '',
                deadline_time=self.deadline.time().toString('HH:mm:ss') if self.deadline_check.isChecked() and repeat else '',
                attachments=saved_files,template_ids=self.template_ids())
            self.store.save(self.task)
        except Exception as exc:
            for path in copied: path.unlink(missing_ok=True)
            QMessageBox.warning(self,'保存失败',str(exc)); return
        self.accept()

class WorkWorld(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setMinimumHeight(330); self.setMouseTracking(True)
        self.items=[]; self.station_rects=[]; self.phase=0.; self.hover=-1; self.actor='小马'; self.open_task=None
        self.reward_until=0.
        self.timer=QTimer(self); self.timer.setInterval(40); self.timer.timeout.connect(self.tick); self.timer.start()
        self.setToolTip('点击工位打开任务；颜色和“高 / 中 / 低”共同表示重要性。')

    def tick(self):
        if self.isVisible(): self.phase+=.035; self.update()

    def set_items(self, items):
        self.items=items; columns=max(1,int(max(400,self.width())/210))
        self.setMinimumHeight(max(330, math.ceil(len(items)/columns)*132+150)); self.update()

    def resizeEvent(self,event):
        super().resizeEvent(event); self.set_items(self.items)

    def mouseMoveEvent(self,event):
        self.hover=next((i for i,r in enumerate(self.station_rects) if r.contains(event.position())),-1)
        self.setCursor(Qt.PointingHandCursor if self.hover>=0 else Qt.ArrowCursor)
        if self.hover>=0: self.setToolTip(self.items[self.hover][0]['title'])
        self.update()

    def leaveEvent(self,event): self.hover=-1; self.update()

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and self.hover>=0 and self.open_task: self.open_task(self.items[self.hover][0])

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor('#F3EDE1'))
        p.setPen(QPen(QColor('#E4DCCB'),1))
        for y in range(45,self.height(),42): p.drawLine(0,y,self.width(),y)
        p.setPen(QColor('#4B6456')); p.setFont(QFont('Microsoft YaHei UI',11)); p.drawText(24,32,'打工牧场  /  每个工位都是一件事')
        cols=max(1,int(self.width()/210)); width=self.width()/cols; self.station_rects=[]
        for i,(task,done) in enumerate(self.items):
            x=i%cols*width+20; y=i//cols*132+65; r=QRectF(x,y,width-36,100); self.station_rects.append(r)
            raised= -5 if i==self.hover else 0
            p.setPen(Qt.NoPen); p.setBrush(QColor('#D9D1C2')); p.drawRoundedRect(r.translated(0,7),12,12)
            p.setBrush(QColor('#FFFFFF' if not done else '#E0EBDD')); p.drawRoundedRect(r.translated(0,raised),12,12)
            p.setBrush(QColor(PRIORITIES.get(task.get('priority','中')))); p.drawRoundedRect(QRectF(x,y+raised,width-36,8),4,4)
            p.setBrush(QColor('#36584D')); p.drawRoundedRect(QRectF(x+14,y+18+raised,36,25),4,4)
            p.setPen(QPen(QColor('#36584D'),3)); p.drawLine(QPointF(x+32,y+43+raised),QPointF(x+32,y+52+raised))
            p.drawLine(QPointF(x+17,y+53+raised),QPointF(x+46,y+53+raised))
            p.setPen(QColor('#36584D')); p.setFont(QFont('Microsoft YaHei UI',9,QFont.Bold))
            text=p.fontMetrics().elidedText(task['title'],Qt.ElideRight,int(width-60)); p.drawText(QPointF(x+12,y+74+raised),text)
            p.setFont(QFont('Microsoft YaHei UI',8)); p.drawText(QPointF(x+60,y+35+raised),f"{task.get('priority','中')}优先 · {'已收工' if done else '待处理'}")
            if done:
                p.setPen(QPen(QColor('#92A34F'),3))
                for k in range(5): p.drawLine(QPointF(x+width-65+k*4,y+44),QPointF(x+width-70+k*4,y+58))
        if not self.items:
            p.setPen(QColor('#617263')); p.drawText(25,105,'牧场暂时没有工位。新增一个任务，小马就有地方跑了。')
        points=[QPointF(r.center().x(),r.bottom()+25) for r in self.station_rects] or [QPointF(self.width()/2,175)]
        pending=[i for i,(_,done) in enumerate(self.items) if not done]; active=[points[i] for i in pending] or points
        step=self.phase*.32; a=active[int(step)%len(active)]; b=active[(int(step)+1)%len(active)]; fraction=step%1
        pos=a+(b-a)*fraction; happy=bool(self.items) and not pending; bob=math.sin(self.phase*5)*(6 if happy else 3)
        self.draw_animal(p,pos.x(),pos.y()+bob,happy)
        if self.phase<self.reward_until:
            p.setPen(QColor('#688B35')); p.setFont(QFont('Microsoft YaHei UI',12,QFont.Bold)); p.drawText(QPointF(pos.x()-32,pos.y()-70),'＋1 捆草')
        p.end()

    def draw_animal(self,p,x,y,happy):
        p.save(); p.translate(x,y); p.setPen(QPen(QColor('#795440'),2)); p.setBrush(QColor('#BA8C66'))
        for k in (-20,-12,7,17):
            swing=math.sin(self.phase*7+k)*7
            p.drawLine(QPointF(k,9),QPointF(k+swing,30))
        p.drawEllipse(QRectF(-31,-15,54,31)); p.drawEllipse(QRectF(5,-34,16,35)); p.drawEllipse(QRectF(8,-39,25,24))
        p.drawEllipse(QRectF(15,-25,31,16))
        p.setBrush(QColor('#745440')); p.drawEllipse(QRectF(8,-35,9,25))
        p.setBrush(QColor('#BA8C66')); p.drawEllipse(QRectF(14,-51,7,17))
        if self.actor=='小牛':
            p.setPen(QPen(QColor('#EEDCB3'),5)); p.drawLine(QPointF(13,-38),QPointF(7,-49)); p.drawLine(QPointF(27,-38),QPointF(32,-49))
            p.setPen(Qt.NoPen); p.setBrush(QColor('#725548')); p.drawEllipse(QRectF(-18,-11,15,13))
        else:
            p.setPen(QPen(QColor('#745440'),4))
            for k in range(4): p.drawLine(QPointF(9,-31+k*5),QPointF(3,-30+k*5))
        p.setPen(QPen(QColor('#3D3C31'),3)); p.drawPoint(QPointF(28,-30))
        p.setPen(QPen(QColor('#73513D'),3)); p.drawLine(QPointF(-29,-4),QPointF(-42,-17))
        p.setPen(QPen(QColor('#835841'),2)); p.drawArc(QRectF(29,-19,10,8),180*16,180*16)
        if happy:
            p.setPen(QColor('#CC9362')); p.setFont(QFont('Segoe UI',15)); p.drawText(-38,-50,'★')
        p.restore()

class HistoryDesk(QPushButton):
    def __init__(self, day, records, callback):
        super().__init__(); self.day=day; self.records=records; self.spread=0.; self.hovered=False
        self.setMinimumSize(180,122); self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(lambda: callback(day,records))
        self.timer=QTimer(self); self.timer.setInterval(25); self.timer.timeout.connect(self.animate)

    def enterEvent(self,event): self.hovered=True; self.timer.start(); super().enterEvent(event)
    def leaveEvent(self,event): self.hovered=False; self.timer.start(); super().leaveEvent(event)
    def animate(self):
        target=1. if self.hovered else 0.; self.spread+=(target-self.spread)*.22; self.update()
        if abs(target-self.spread)<.01: self.timer.stop()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setPen(Qt.NoPen)
        for i,color in enumerate(['#C9D9D1','#AFCCC0','#FFFFFF']):
            p.setBrush(QColor(color)); p.drawRoundedRect(QRectF(14+i*4,18+i*6-self.spread*i*9,self.width()-36,78),10,10)
        p.setPen(QColor('#2E5E4C')); p.setFont(QFont('Microsoft YaHei UI',10,QFont.Bold)); p.drawText(30,53,self.day)
        p.setFont(QFont('Microsoft YaHei UI',9)); p.drawText(30,80,f'{len(self.records)} 件已完成 · {len(self.records)} 捆草')
        p.end()

class PasturePage(QWidget):
    def __init__(self, theme='light', store=None):
        super().__init__(); self.theme=theme; self.store=store or TaskStore(); self.day=date.today().isoformat()
        self._initial_scene_applied=False
        self.mode=self.store.setting('mode','office'); self.actor=self.store.setting('actor','小马')
        if self.actor not in ('小马','腊肠犬','猴子','小猫'): self.actor='小马'
        self.outfit=self.store.setting('outfit','通勤')
        outer=QVBoxLayout(self); outer.setContentsMargins(24,20,24,20); outer.setSpacing(14)
        header=QHBoxLayout(); outer.addLayout(header)
        title=QLabel('今日任务'); title.setStyleSheet('font-size:26px;font-weight:700;'); header.addWidget(title); header.addStretch()
        self.mode_box=QComboBox(); self.mode_box.addItems(['简洁','角色工位']); self.mode_box.setCurrentIndex(1 if self.mode=='game' else 0)
        self.mode_box.currentIndexChanged.connect(self.change_mode); self.mode_box.hide()
        add=QPushButton('＋ 新建任务'); add.clicked.connect(lambda:self.edit()); header.addWidget(add)
        templates=QPushButton('做事模板'); templates.clicked.connect(lambda:self.open_templates()); header.addWidget(templates)
        export=QPushButton('导出数据'); export.clicked.connect(lambda:self.export_tasks()); header.addWidget(export)
        self.summary=QLabel(); self.summary.setWordWrap(True); outer.addWidget(self.summary)
        self.warning=QLabel(); self.warning.setWordWrap(True); self.warning.setStyleSheet('background:#FFF0DA;color:#795428;padding:12px;border-radius:12px;'); outer.addWidget(self.warning)
        toolbar=QHBoxLayout(); outer.addLayout(toolbar)
        self.search=QLineEdit(); self.search.setPlaceholderText('搜索任务、备注'); self.search.textChanged.connect(self.refresh); toolbar.addWidget(self.search,1)
        self.filter=QComboBox(); self.filter.addItems(['今日全部','今日未完成','今日已完成','所有任务 / 周期计划','历史桌面']); self.filter.currentIndexChanged.connect(self.refresh); toolbar.addWidget(self.filter)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); outer.addWidget(self.scroll,1)
        self.content=QWidget(); self.list=QVBoxLayout(self.content); self.list.setSpacing(12)
        self.list.setSizeConstraint(QLayout.SetMinAndMaxSize); self.scroll.setWidget(self.content)
        from monitor_scene import MonitorWorld
        self.world=MonitorWorld(); self.world.theme=theme; self.world.actor=self.actor; self.world.open_task=self.open_plot; self.world.timer_task=self.timer_action
        self.day_timer=QTimer(self); self.day_timer.setInterval(30000); self.day_timer.timeout.connect(self.rollover); self.day_timer.start()
        self.refresh()

    def rollover(self):
        if self.day!=date.today().isoformat(): self.day=date.today().isoformat(); self.refresh()
        elif self.mode=='game': self.world.update()

    def change_mode(self,index):
        self.mode='game' if index else 'office'; self.store.set_setting('mode',self.mode); self.refresh()
        self.apply_scene_mode()

    def showEvent(self,event):
        super().showEvent(event)
        if not self._initial_scene_applied:
            self._initial_scene_applied=True
            if self.mode=='game': QTimer.singleShot(0,self.apply_scene_mode)

    def apply_scene_mode(self):
        window=self.window()
        if window is self or window.isMinimized(): return
        if hasattr(window,'_nav'): window._nav.setVisible(self.store.setting('sidebar_hidden','no')!='yes')
        if hasattr(window,'title_bar'): window.title_bar.setVisible(True)

    def toggle_fullscreen(self):
        window=self.window()
        if window.isFullScreen(): window.showNormal()
        else: window.showFullScreen()

    def open_plot(self,task):
        dialog=QDialog(self); dialog.setWindowTitle('任务详情'); dialog.resize(620,400)
        layout=QVBoxLayout(dialog)
        layout.addWidget(self.card(task,any(t['id']==task['id'] and done for t,done in self.store.today(self.day))))
        close=QPushButton('返回工位'); close.clicked.connect(dialog.accept); layout.addWidget(close); dialog.exec()

    def begin_task(self,task):
        self.rollover()
        try: self.store.start_task(task['id'],self.day)
        except Exception as exc: QMessageBox.warning(self,'无法开始',str(exc)); return False
        self.world.selected_id=task['id']; self.refresh(); return True

    def timer_action(self,task):
        """Read the latest record so a stale detail dialog cannot resume by mistake."""
        self.rollover()
        current=next((t for t in self.store.tasks() if t['id']==task['id']),None)
        if current is None: return False
        state=timer_state(current,self.day)
        if not state['started']: return self.begin_task(current)
        try: self.store.pause_task(current['id'],self.day,not (state['paused'] or state['finished']))
        except Exception as exc: QMessageBox.warning(self,'无法修改计时状态',str(exc)); return False
        if state['paused'] or state['finished']: self.world.selected_id=current['id']
        self.refresh(); return True

    def open_templates(self,template_id=None):
        from template_library import TemplateLibrary
        TemplateLibrary(self.store,template_id,self).exec(); self.refresh()

    def export_tasks(self,scope=None,day=None):
        from task_export import TaskExportDialog
        selected=scope or ('history' if self.filter.currentIndex()==4 else 'all' if self.filter.currentIndex()==3 else 'current')
        TaskExportDialog(self.store,selected,day or (self.day if selected=='current' else None),self).exec()

    def template_tags(self,layout,task):
        templates={t['id']:t for t in self.store.templates()}
        if not task.get('template_ids'): return
        row=QVBoxLayout(); layout.addLayout(row)
        for key in task['template_ids']:
            template=templates.get(key)
            name=template['title'] if template else '未找到'
            tag=QPushButton('模板 · '+name[:24]+('…' if len(name)>24 else ''))
            tag.setToolTip(name+' · 打开对应的 SOP / 邮件 / 话术或在线文档'); tag.setEnabled(template is not None)
            tag.clicked.connect(lambda checked=False,k=key:self.open_templates(k)); row.addWidget(tag)

    def time_summary(self,task,day=None):
        day=day or self.day
        started=task.get('start_log',{}).get(day) or (task.get('started_at') if not task.get('repeat') else None)
        completed=task.get('completed_at')
        if not completed:
            completed=next((t.get('completed_at') for tid,d,t in self.store.completed() if tid==task['id'] and d==day),None)
        return '创建：'+(task.get('created_at') or '旧记录未记录')+'\n开始：'+(started or '未开始 / 未记录')+'\n完成：'+(completed or '未完成 / 未记录')

    def settings(self):
        dialog=QDialog(self); dialog.setWindowTitle('设置 · 外观与显示'); dialog.resize(490,650); layout=QVBoxLayout(dialog)
        form=QFormLayout(); layout.addLayout(form)
        mode=QComboBox(); mode.addItems(['简洁','角色工位']); mode.setCurrentIndex(1 if self.mode=='game' else 0); form.addRow('显示模式',mode)
        theme=QComboBox(); theme.addItems(['浅色','深色']); theme.setCurrentIndex(1 if self.theme=='dark' else 0); form.addRow('颜色主题',theme)
        background=QComboBox(); background.addItems(['雾白','青绿','暖砂','浅蓝']); background.setCurrentText(self.store.setting('background','雾白')); form.addRow('页面背景',background)
        layout.addWidget(QLabel('陪伴角色'))
        actor=QComboBox(); actor.addItems(['小马','腊肠犬','猴子','小猫']); actor.setCurrentText(self.actor); layout.addWidget(actor)
        from mascot_animation import OUTFITS
        layout.addWidget(QLabel('角色服装'))
        outfit=QComboBox(); outfit.addItems(OUTFITS); outfit.setCurrentText(self.outfit); layout.addWidget(outfit)
        motion=QCheckBox('开启动画'); motion.setChecked(self.store.setting('motion','yes')=='yes'); layout.addWidget(motion)
        layout.addWidget(QLabel('预警：待做 > 5 件，或已估时合计 > 180 分钟。\n体力是趣味指标，不代表真实健康状况。'))
        compact=QPushButton('打开左侧悬浮清单'); layout.addWidget(compact)
        def open_compact():
            dialog.accept(); self.open_compact()
        compact.clicked.connect(open_compact)
        studio=QPushButton('角色动画工作室 · Blender'); layout.addWidget(studio)
        def show_studio():
            from blender_studio import open_studio
            open_studio(dialog)
        studio.clicked.connect(show_studio)
        button=QPushButton('保存设置'); layout.addWidget(button)
        def save():
            self.actor=actor.currentText(); self.store.set_setting('actor',self.actor)
            self.outfit=outfit.currentText(); self.store.set_setting('outfit',self.outfit)
            self.store.set_setting('motion','yes' if motion.isChecked() else 'no')
            self.store.set_setting('background',background.currentText())
            self.world.actor=self.actor; dialog.accept(); self.mode_box.setCurrentIndex(mode.currentIndex()); self.refresh()
            chosen='dark' if theme.currentIndex() else 'light'
            if chosen!=self.theme and hasattr(self.window(),'set_theme'): self.window().set_theme(chosen)
        button.clicked.connect(save); dialog.exec()

    def open_compact(self):
        from compact_tasks import CompactTasks
        if not hasattr(self,'compact_window') or not self.compact_window.isVisible():
            self.compact_window=CompactTasks(self.store,self.window(),self)
        self.compact_window.show(); self.compact_window.raise_(); self.window().hide()

    def clear(self):
        while self.list.count():
            item=self.list.takeAt(0); widget=item.widget()
            if widget:
                widget.hide()
                if widget is self.world: widget.hide(); widget.setParent(self)
                else:
                    for timer in widget.findChildren(QTimer): timer.stop()
                    widget.deleteLater()

    def refresh(self,*args):
        self.world.outfit=self.outfit; self.world.day=self.day
        self.world.background_choice=self.store.setting('background','雾白')
        from monitor_scene import BACKGROUNDS
        color=BACKGROUNDS[self.theme].get(self.world.background_choice,BACKGROUNDS[self.theme]['雾白'])
        self.setObjectName('TaskSurface'); self.setStyleSheet('#TaskSurface{background:'+color+';}')
        self.clear(); entries=self.store.today(self.day); pending=[t for t,done in entries if not done]
        done_count=sum(done for _,done in entries); total_minutes=sum(t.get('minutes',0) for t in pending)
        unknown=sum(not t.get('minutes') for t in pending); receipts=self.store.completed()
        health=max(10,100-done_count*12); grass=len(receipts)
        self.world.done_today=done_count; self.world.all_done=bool(entries) and not pending
        game=self.mode=='game'
        if game:
            mood='全世界没有比你更厉害的牛马啦！今天收工。' if entries and not pending else '菜收到了，电量见底了。歇一会儿也算战术。' if health<=40 else '收割不少，马都干出自信了。' if done_count>=3 else '先收一块田，别一上来就承包整个农场。'
            self.summary.setText(f'{self.day}  ·  {done_count}/{len(entries)} 已完成  ·  奖励 {grass} 份')
        else:
            self.summary.setText(f'{self.day}  ·  {done_count}/{len(entries)} 已完成  ·  待做预估 {total_minutes} 分钟')
        overloaded=len(pending)>5 or total_minutes>180
        self.world.overloaded=overloaded and self.day==date.today().isoformat()
        self.warning.setVisible(overloaded or unknown>0)
        self.warning.setText((('活太多了，你还是先排个优先级吧。' if game else '工作量预警：建议重新安排优先级。') if overloaded else '有任务没估时，先别急着说今天不忙。' if game else '预估时长尚不完整。')+f' 待做 {len(pending)} 件 / 已估时 {total_minutes} 分钟。'+(f' {unknown} 件未估时，实际时长可能更高。' if unknown else ''))
        selected=self.filter.currentIndex(); query=self.search.text().strip().lower()
        if selected==4:
            groups={}
            for _,day,t in receipts:
                if query and query not in (t['title']+t.get('note','')).lower(): continue
                groups.setdefault(day,[]).append(t)
            if not groups: self.list.addWidget(QLabel('还没有完成记录。完成任务后，这里会留下当天的桌面。'))
            for day,tasks in sorted(groups.items(),reverse=True): self.list.addWidget(HistoryDesk(day,tasks,self.show_history))
        else:
            if selected==3: entries=[(t,False) for t in self.store.tasks()]
            elif selected==1: entries=[(t,d) for t,d in entries if not d]
            elif selected==2: entries=[(t,d) for t,d in entries if d]
            entries=[(t,d) for t,d in entries if not query or query in (t['title']+t.get('note','')).lower()]
            entries.sort(key=lambda pair: ({'高':0,'中':1,'低':2}.get(pair[0].get('priority'),1),pair[0]['title']))
            if game and selected!=3:
                self.world.set_items(entries); self.list.addWidget(self.world); self.world.show()
                if self.store.setting('motion','yes')=='yes': self.world.timer.start()
                else: self.world.timer.stop()
            else: self.world.timer.stop()
            if not entries: self.list.addWidget(QLabel('这里没有匹配的任务。'))
            if not game or selected==3:
                for task,done in entries: self.list.addWidget(self.card(task,done,selected==3))
        self.list.addStretch()
        self.list.invalidate(); self.list.activate()

    def card(self,task,done,planning=False):
        frame=QFrame(); layout=QVBoxLayout(frame); row=QHBoxLayout(); layout.addLayout(row)
        dark=self.theme=='dark'; frame.setStyleSheet(f"QFrame{{background:{'#172C3A' if dark else '#FFFFFF'};border:1px solid {'#385364' if dark else '#DCE7E1'};border-left:4px solid {PRIORITIES.get(task.get('priority','中'))};border-radius:12px;}} QLabel{{border:none;background:transparent;}}")
        title=QLabel(task['title']); title.setWordWrap(True); title.setStyleSheet('font-size:15px;font-weight:600;border:none;'); row.addWidget(title,1)
        edit=QPushButton('详情 / 编辑'); edit.clicked.connect(lambda:self.edit(task)); row.addWidget(edit)
        if not planning:
            if not done:
                state=timer_state(task,self.day)
                start_button=QPushButton('开始处理' if not state['started'] else '继续处理' if state['paused'] or state['finished'] else '暂停处理')
                def act():
                    if self.timer_action(task) and isinstance(frame.window(),QDialog): frame.window().accept()
                start_button.clicked.connect(act); row.addWidget(start_button)
            complete=QPushButton('撤销完成' if done else '完成任务 ＋1 奖励' if self.mode=='game' else '完成任务')
            def complete_task():
                if self.finish(task) and isinstance(frame.window(),QDialog): frame.window().accept()
            complete.clicked.connect(complete_task); row.addWidget(complete)
        cadence={'daily':'每天','weekly':'每周 '+','.join(map(str,task.get('weekdays',[]))),'monthly':'每月 '+','.join(map(str,task.get('month_days',[])))}.get(task.get('repeat'),'普通任务')
        meta=QLabel(f"{task.get('priority','中')}优先 · {cadence} · {str(task.get('minutes'))+' 分钟' if task.get('minutes') else '未估时'}"+(' · 已停用' if not task.get('enabled',True) else ''))
        layout.addWidget(meta)
        times=QLabel(self.time_summary(task)); times.setWordWrap(True); times.setTextFormat(Qt.PlainText); times.setStyleSheet('font-size:11px;color:#7B9188;border:none;'); layout.addWidget(times)
        self.template_tags(layout,task)
        if task.get('note'):
            note=QLabel(task['note']); note.setTextFormat(Qt.PlainText); note.setWordWrap(True); note.setTextInteractionFlags(Qt.TextSelectableByMouse); layout.addWidget(note)
            import re
            for url in re.findall(r'https?://[^\s<>]+',task['note']):
                link=QPushButton('打开链接：'+url[:75]); link.clicked.connect(lambda checked=False,u=url:QDesktopServices.openUrl(QUrl(u))); layout.addWidget(link)
        if task.get('is_follow_up'):
            follow=QLabel('跟进日期：'+task.get('follow_up_date','未设置')); layout.addWidget(follow)
        for record in task.get('follow_up_history',[]):
            label=QLabel(record.get('date','')+' · '+record.get('note','')); label.setTextFormat(Qt.PlainText); label.setWordWrap(True); layout.addWidget(label)
        for attachment in task.get('attachments',[]):
            button=QPushButton('附件 · '+attachment.get('name','查看文件'))
            button.clicked.connect(lambda checked=False,a=attachment:self.open_attachment(a)); layout.addWidget(button)
        return frame

    def open_attachment(self,attachment):
        path=Path(attachment.get('path','')); path=path if path.is_absolute() else self.store.root/path
        if not path.is_file(): QMessageBox.warning(self,'附件不存在','文件可能已移动，请重新添加。'); return
        if path.suffix.lower() in ('.exe','.bat','.cmd','.ps1','.vbs','.js','.msi','.py','.scr'):
            QMessageBox.warning(self,'安全提示','不直接运行脚本或安装程序附件，请在文件管理器中查看。'); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def edit(self,task=None):
        dialog=TaskEditor(self.store,task,self)
        if dialog.exec(): self.refresh()

    def finish(self,task):
        was_done=any(t['id']==task['id'] and done for t,done in self.store.today(self.day))
        try: self.store.toggle(task,self.day)
        except Exception as exc: QMessageBox.warning(self,'未保存完成记录',str(exc)); return False
        if not was_done: self.world.reward_until=self.world.phase+2.7
        else: self.world.reward_until=0.
        self.refresh()
        return True

    def show_history(self,day,tasks):
        dialog=QDialog(self); dialog.setWindowTitle(day+' · 历史桌面'); dialog.resize(700,560)
        layout=QVBoxLayout(dialog); layout.addWidget(QLabel(f'{day} · 完成 {len(tasks)} 件 · 获得 {len(tasks)} 捆草'))
        export=QPushButton('导出这一天的历史数据'); export.clicked.connect(lambda:self.export_tasks('history',day)); layout.addWidget(export)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); content=QWidget(); rows=QVBoxLayout(content)
        for task in tasks:
            title=QLabel(task['title']); title.setWordWrap(True); title.setStyleSheet('font-size:16px;font-weight:600;'); rows.addWidget(title)
            note=QLabel(task.get('note','') or '无备注'); note.setWordWrap(True); note.setTextFormat(Qt.PlainText); rows.addWidget(note)
            times=QLabel(self.time_summary(task,day)); times.setWordWrap(True); times.setTextFormat(Qt.PlainText); rows.addWidget(times)
            self.template_tags(rows,task)
            for attachment in task.get('attachments',[]):
                button=QPushButton('附件 · '+attachment.get('name','查看文件')); button.clicked.connect(lambda checked=False,a=attachment:self.open_attachment(a)); rows.addWidget(button)
        rows.addStretch(); scroll.setWidget(content); layout.addWidget(scroll); close=QPushButton('收好桌面'); close.clicked.connect(dialog.accept); layout.addWidget(close); dialog.exec()
