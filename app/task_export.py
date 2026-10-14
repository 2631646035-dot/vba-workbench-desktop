"""Inspectable current/history exports. Missing legacy timestamps stay blank."""
import csv
import json
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from task_store import timer_state
from PySide6.QtCore import Qt,QDate
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QComboBox,QDateEdit,QPushButton,
    QLabel,QTableWidget,QTableWidgetItem,QFileDialog,QMessageBox,QAbstractItemView,QHeaderView)

COLUMNS=['任务ID','任务名称','记录日期','状态','优先级','预估分钟','创建时间','开始时间','完成时间','开始到完成分钟','计时状态','有效计时秒','有效计时分钟','周期','模板标签','备注']

def elapsed_minutes(start,end):
    if not start or not end: return ''
    try:
        values=[datetime.fromisoformat(v) for v in (start,end)]
        values=[v if v.tzinfo else v.replace(tzinfo=timezone(timedelta(hours=8))) for v in values]
        seconds=(values[1]-values[0]).total_seconds()
        return round(seconds/60,2) if seconds>=0 else ''
    except (ValueError,TypeError): return ''

def export_rows(store,scope,first,last):
    templates={t['id']:t['title'] for t in store.templates()}; receipts=store.completed(); rows=[]
    if scope=='history': records=[(t,day,'已完成') for _,day,t in receipts if first<=day<=last]
    elif scope=='all':
        records=[]
        for task in store.tasks():
            history=[(d,t) for tid,d,t in receipts if tid==task['id']]
            if history and not task.get('repeat'):
                day,snapshot=history[0]; records.append(({**task,'started_at':snapshot.get('started_at'),'completed_at':snapshot.get('completed_at')},day,'已完成'))
            else: records.append((task,'','周期计划' if task.get('repeat') else '待做'))
    else:
        snapshots={(tid,day):t for tid,day,t in receipts}
        records=[(snapshots.get((t['id'],first),t),first,'已完成' if done else '待做') for t,done in store.today(first)]
    for task,day,status in records:
        start=task.get('start_log',{}).get(day) or (task.get('started_at') if not task.get('repeat') or status=='已完成' else None)
        end=task.get('completed_at') if status=='已完成' else None
        timing=timer_state(task,day or date.today().isoformat())
        values=[task['id'],task['title'],day,status,task.get('priority','中'),task.get('minutes',0),task.get('created_at') or '',start or '',end or '',elapsed_minutes(start,end),'已结束' if timing['finished'] else '已暂停' if timing['paused'] else '计时中' if timing['started'] else '未开始',round(timing['seconds'],2) if timing['tracked'] else '',round(timing['seconds']/60,2) if timing['tracked'] else '',task.get('repeat',''),'; '.join(templates.get(key,'未找到模板:'+key) for key in task.get('template_ids',[])),task.get('note','')]
        rows.append(dict(zip(COLUMNS,values)))
    return rows

def write_export(path,rows,format_name):
    path=Path(path)
    if format_name=='json': path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        with path.open('w',encoding='utf-8-sig',newline='') as output:
            writer=csv.DictWriter(output,fieldnames=COLUMNS); writer.writeheader()
            # Prevent user text becoming a formula when CSV is opened in Excel.
            for row in rows:
                writer.writerow({k:("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})

class TaskExportDialog(QDialog):
    def __init__(self,store,scope='current',selected_day=None,parent=None):
        super().__init__(parent); self.store=store; self.setWindowTitle('任务数据导出'); self.resize(1000,570)
        layout=QVBoxLayout(self); controls=QHBoxLayout(); layout.addLayout(controls)
        self.scope=QComboBox(); self.scope.addItems(['当前任务（所选日期）','历史完成记录','全部任务 / 周期计划']); self.scope.setCurrentIndex({'current':0,'history':1,'all':2}.get(scope,0)); controls.addWidget(self.scope)
        self.first=QDateEdit(); self.last=QDateEdit()
        for field in (self.first,self.last): field.setCalendarPopup(True); field.setDisplayFormat('yyyy-MM-dd')
        today=QDate.fromString(selected_day or date.today().isoformat(),'yyyy-MM-dd')
        self.first.setDate(today.addDays(-30) if scope=='history' and not selected_day else today); self.last.setDate(today)
        controls.addWidget(QLabel('日期 / 历史起始')); controls.addWidget(self.first); controls.addWidget(QLabel('历史结束')); controls.addWidget(self.last)
        self.format=QComboBox(); self.format.addItems(['CSV（Excel可打开）','JSON']); controls.addWidget(self.format)
        self.info=QLabel(); layout.addWidget(self.info)
        self.table=QTableWidget(); self.table.setColumnCount(len(COLUMNS)); self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); layout.addWidget(self.table,1)
        note=QLabel('旧记录缺失的时间留空。开始到完成为自然经过时间（包含休息），不是净工作时长。当前任务只导出所选日期。'); note.setWordWrap(True); layout.addWidget(note)
        row=QHBoxLayout(); layout.addLayout(row); row.addStretch(); close=QPushButton('关闭'); close.clicked.connect(self.reject); row.addWidget(close)
        self.save=QPushButton('选择位置并导出'); self.save.clicked.connect(self.export); row.addWidget(self.save)
        self.scope.currentIndexChanged.connect(self.refresh); self.first.dateChanged.connect(self.refresh); self.last.dateChanged.connect(self.refresh); self.refresh()

    def refresh(self,*args):
        scope=['current','history','all'][self.scope.currentIndex()]; self.first.setEnabled(scope!='all'); self.last.setEnabled(scope=='history')
        first=self.first.date().toString('yyyy-MM-dd'); last=self.last.date().toString('yyyy-MM-dd')
        valid=scope!='history' or first<=last
        self.rows=export_rows(self.store,scope,first,last) if valid else []; self.save.setEnabled(valid)
        self.info.setText(f'共 {len(self.rows)} 条，预览前200条；导出包含全部记录。' if valid else '历史结束日期不能早于起始日期。')
        self.table.setRowCount(min(200,len(self.rows)))
        for i,row in enumerate(self.rows[:200]):
            for j,column in enumerate(COLUMNS): self.table.setItem(i,j,QTableWidgetItem(str(row[column])))

    def export(self):
        self.refresh(); kind='csv' if self.format.currentIndex()==0 else 'json'
        path,_=QFileDialog.getSaveFileName(self,'导出任务数据','工作台任务_'+date.today().isoformat()+'.'+kind,'CSV (*.csv)' if kind=='csv' else 'JSON (*.json)')
        if not path: return
        if not Path(path).suffix: path+='.'+kind
        try: write_export(path,self.rows,kind)
        except Exception as exc: QMessageBox.warning(self,'导出失败',str(exc)); return
        QMessageBox.information(self,'导出完成',f'已导出 {len(self.rows)} 条记录。\n{path}')
