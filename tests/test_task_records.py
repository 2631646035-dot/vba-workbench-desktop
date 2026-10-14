import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import csv,json,tempfile,unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QDate
from PySide6.QtWidgets import QApplication,QPushButton,QLabel,QWidget
from PySide6.QtGui import QFontDatabase
from task_store import TaskStore,new_task
from task_export import export_rows,write_export,elapsed_minutes,TaskExportDialog
from template_library import TemplateLibrary,web_links
from pasture_page import PasturePage,TaskEditor

app=QApplication.instance() or QApplication([])
for font in ('C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/segoeui.ttf'): QFontDatabase.addApplicationFont(font)

class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.store=TaskStore(self.temp.name); self.day=date.today().isoformat()
    def tearDown(self): self.temp.cleanup()
    def task(self,**values):
        task=new_task(); task.update(title='核对物流账单',start='2026-10-01'); task.update(values); self.store.save(task); return task
    def template(self):
        template={'id':'sop1','title':'账单核对SOP','kind':'SOP','body':'1. 确认账期\n2. 对照价格规则\n3. 提交差异清单','links':['https://example.com/sop']}; self.store.save_template(template); return template

    def test_creation_start_finish_and_stale_edit(self):
        with patch('task_store.timestamp',return_value=self.day+'T09:00:00+08:00'): task=self.task()
        stale=dict(task)
        with patch('task_store.timestamp',return_value=self.day+'T10:00:00+08:00'): started=self.store.start_task(task['id'],self.day)
        with patch('task_store.timestamp',return_value=self.day+'T10:30:00+08:00'): again=self.store.start_task(task['id'],self.day)
        self.assertEqual(started['start_log'],again['start_log'])
        stale['created_at']='invented'; stale['title']='修改标题'; self.store.save(stale)
        current=self.store.tasks()[0]; self.assertEqual(current['created_at'],self.day+'T09:00:00+08:00'); self.assertEqual(current['started_at'],started['started_at'])
        with patch('task_store.timestamp',return_value=self.day+'T11:00:00+08:00'): self.store.toggle(task,self.day)
        receipt=self.store.completed()[0][2]; self.assertEqual(receipt['title'],'修改标题'); self.assertEqual(receipt['started_at'],started['started_at'])
        row=export_rows(self.store,'history',self.day,self.day)[0]; self.assertEqual(row['开始到完成分钟'],60)
        with self.assertRaises(ValueError): self.store.start_task(task['id'],self.day)
        self.store.toggle(task,self.day); self.assertEqual(len(self.store.completed()),0)

    def test_missing_legacy_time_is_not_fabricated(self):
        task=new_task(); task.update(title='旧记录',start='2026-10-01')
        with self.store.connect() as db: self.store._save(db,task); self.store._receipt(db,task,'2026-10-12')
        self.store.save(task); self.assertFalse(self.store.tasks()[0].get('created_at'))
        row=export_rows(self.store,'history','2026-10-12','2026-10-12')[0]
        self.assertEqual([row[k] for k in ('创建时间','开始时间','完成时间','开始到完成分钟')],['','','',''])

    def test_recurring_start_and_completion_are_separate(self):
        task=self.task(repeat='daily')
        for day in ('2026-10-12','2026-10-13'):
            with patch('task_store.timestamp',return_value=day+'T10:00:00+08:00'): self.store.start_task(task['id'],day)
            with patch('task_store.timestamp',return_value=day+'T11:00:00+08:00'): self.store.toggle(task,day)
        receipts=self.store.completed(); self.assertEqual(len(receipts),2)
        for _,day,snapshot in receipts: self.assertEqual(snapshot['started_at'],day+'T10:00:00+08:00'); self.assertEqual(snapshot['completed_at'],day+'T11:00:00+08:00')

    def test_csv_json_and_all_tasks_export(self):
        self.template(); task=self.task(title='=HYPERLINK("malicious")',template_ids=['sop1'])
        self.store.start_task(task['id'],self.day); self.store.toggle(task,self.day)
        rows=export_rows(self.store,'all',self.day,self.day); self.assertTrue(rows[0]['完成时间']); self.assertEqual(rows[0]['模板标签'],'账单核对SOP')
        csv_path=Path(self.temp.name)/'tasks.csv'; write_export(csv_path,rows,'csv')
        with csv_path.open(encoding='utf-8-sig',newline='') as f: exported=list(csv.DictReader(f))
        self.assertTrue(exported[0]['任务名称'].startswith("'="))
        json_path=Path(self.temp.name)/'tasks.json'; write_export(json_path,rows,'json'); self.assertEqual(json.loads(json_path.read_text(encoding='utf-8')),rows)
        self.assertEqual(elapsed_minutes('invalid','also invalid'),'')
        self.assertEqual(elapsed_minutes('2026-10-12T10:00:00','2026-10-12T11:00:00+08:00'),60)

    def test_template_tags_save_and_link_navigation(self):
        template=self.template(); task=self.task(); editor=TaskEditor(self.store,task)
        editor.template_list.item(0).setCheckState(Qt.Checked); editor.commit(); self.assertEqual(self.store.tasks()[0]['template_ids'],['sop1'])
        library=TemplateLibrary(self.store,'sop1'); library.show(); app.processEvents(); self.assertEqual(library.current['id'],'sop1')
        with patch('template_library.QDesktopServices.openUrl',return_value=True) as opened:
            self.assertFalse(opened.called)
            next(button for button in library.findChildren(QPushButton) if button.text().startswith('打开在线文档')).click()
            self.assertEqual(opened.call_args[0][0].toString(),'https://example.com/sop')
        self.assertEqual(web_links('javascript:alert(1) file:///C:/test.exe'),[])
        library.grab().save(str(Path(__file__).parent/'ui_previews'/'template_library.png'))
        library.close(); editor.close(); library.deleteLater(); editor.deleteLater(); app.processEvents()

    def test_export_dialog_range_and_snapshot(self):
        task=self.task(); self.store.toggle(task,self.day)
        dialog=TaskExportDialog(self.store,'history',self.day); dialog.show(); app.processEvents()
        self.assertEqual(len(dialog.rows),1); self.assertEqual(dialog.rows[0]['状态'],'已完成')
        dialog.grab().save(str(Path(__file__).parent/'ui_previews'/'task_export.png'))
        dialog.first.setDate(QDate.fromString(self.day,'yyyy-MM-dd').addDays(1)); self.assertFalse(dialog.save.isEnabled())
        dialog.close(); dialog.deleteLater(); app.processEvents()

    def test_floating_priority_dots_and_start(self):
        from compact_tasks import CompactTasks
        self.template(); tasks=[self.task(title='示例任务 · '+priority,priority=priority,template_ids=['sop1']) for priority in ('高','中','低')]
        page=PasturePage(store=self.store); owner=QWidget(); compact=CompactTasks(self.store,owner,page); compact.show(); app.processEvents()
        labels=compact.content.findChildren(QLabel); dots=[label for label in labels if label.text()=='●']
        self.assertEqual(len(dots),3); self.assertEqual({dot.accessibleName() for dot in dots},{'高优先级','中优先级','低优先级'})
        self.assertFalse(any(label.text() in ('高优先','中优先','低优先') for label in labels))
        compact.start_task(tasks[0]); current=next(t for t in self.store.tasks() if t['id']==tasks[0]['id']); self.assertTrue(current['start_log'][self.day]); self.assertEqual(len(self.store.completed()),0)
        app.processEvents(); compact.grab().save(str(Path(__file__).parent/'ui_previews'/'floating_priority_templates.png'))
        compact.close(); page.close(); owner.close(); compact.deleteLater(); page.deleteLater(); owner.deleteLater(); app.processEvents()

if __name__=='__main__': unittest.main()
