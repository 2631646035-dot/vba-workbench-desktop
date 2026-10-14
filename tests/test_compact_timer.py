import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile,unittest
from pathlib import Path
from datetime import date
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QPoint
from PySide6.QtGui import QContextMenuEvent,QFontDatabase
from PySide6.QtWidgets import QApplication,QWidget,QMessageBox,QPushButton
from PySide6.QtTest import QTest
from task_store import TaskStore,new_task,timer_state
from compact_tasks import CompactTasks,CompactTaskRow
from pasture_page import PasturePage
from template_library import TemplateEditor,TemplateLibrary,open_template_file
from task_export import export_rows

app=QApplication.instance() or QApplication([])
for font in ('C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/segoeui.ttf'): QFontDatabase.addApplicationFont(font)

class TimerTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.store=TaskStore(self.temp.name); self.day=date.today().isoformat()
    def tearDown(self): self.temp.cleanup()
    def task(self,**values):
        task=new_task(); task.update(title='核对价卡',start='2026-10-01'); task.update(values); self.store.save(task); return task
    def now(self,clock): return self.day+'T'+clock+'+08:00'
    def test_pause_resume_restart_and_completed_snapshot(self):
        task=self.task()
        with patch('task_store.timestamp',return_value=self.now('10:00:00')): self.store.start_task(task['id'],self.day)
        with patch('task_store.timestamp',return_value=self.now('10:02:00')): self.store.pause_task(task['id'],self.day)
        reopened=TaskStore(self.temp.name); current=reopened.tasks()[0]
        state=timer_state(current,self.day,self.now('10:05:00')); self.assertTrue(state['paused']); self.assertEqual(state['seconds'],120)
        stale=dict(task); stale['title']='修改备注时仍保留计时'; self.store.save(stale)
        self.assertTrue(timer_state(self.store.tasks()[0],self.day)['paused'])
        with patch('task_store.timestamp',return_value=self.now('10:05:00')): self.store.pause_task(task['id'],self.day,False)
        with patch('task_store.timestamp',return_value=self.now('10:06:00')): self.store.toggle(task,self.day)
        snapshot=self.store.completed()[0][2]; state=timer_state(snapshot,self.day,self.now('15:00:00')); self.assertEqual(state['seconds'],180); self.assertTrue(state['finished'])
        row=export_rows(self.store,'history',self.day,self.day)[0]; self.assertEqual(row['有效计时分钟'],3); self.assertEqual(row['开始到完成分钟'],6)
        self.store.toggle(task,self.day)
        with patch('task_store.timestamp',return_value=self.now('10:07:00')): self.store.pause_task(task['id'],self.day,False)
        self.assertEqual(timer_state(self.store.tasks()[0],self.day,self.now('10:08:00'))['seconds'],240)

    def test_pause_is_idempotent_and_day_isolated(self):
        task=self.task(repeat='daily')
        with patch('task_store.timestamp',return_value='2026-10-12T10:00:00+08:00'): self.store.start_task(task['id'],'2026-10-12')
        with patch('task_store.timestamp',return_value='2026-10-12T10:01:00+08:00'): self.store.pause_task(task['id'],'2026-10-12')
        with patch('task_store.timestamp',return_value='2026-10-12T10:05:00+08:00'): self.store.pause_task(task['id'],'2026-10-12')
        current=self.store.tasks()[0]; self.assertEqual(timer_state(current,'2026-10-12')['seconds'],60); self.assertFalse(timer_state(current,'2026-10-13')['started'])
        with self.assertRaises(ValueError): self.store.pause_task(task['id'],'2026-10-13')
        with patch('task_store.timestamp',return_value='2026-10-13T10:00:00+08:00'): self.store.start_task(task['id'],'2026-10-13')
        current=self.store.tasks()[0]; self.assertEqual(timer_state(current,'2026-10-13','2026-10-13T10:02:00+08:00')['seconds'],120)
        self.assertEqual(timer_state(current,'2026-10-12')['seconds'],60)

    def test_normal_timer_survives_date_change(self):
        task=self.task()
        with patch('task_store.timestamp',return_value='2026-10-12T23:59:00+08:00'): self.store.start_task(task['id'],'2026-10-12')
        current=self.store.tasks()[0]; self.assertEqual(timer_state(current,'2026-10-13','2026-10-13T00:01:00+08:00')['seconds'],120)
        with patch('task_store.timestamp',return_value='2026-10-13T00:01:00+08:00'): self.store.pause_task(task['id'],'2026-10-13')
        current=self.store.tasks()[0]; self.assertEqual(timer_state(current,'2026-10-13','2026-10-13T10:00:00+08:00')['seconds'],120)

    def test_double_click_timer_toggle_then_finish(self):
        task=self.task(); page=PasturePage(store=self.store); owner=QWidget(); compact=CompactTasks(self.store,owner,page); compact.show(); app.processEvents()
        row=compact.content.findChildren(CompactTaskRow)[0]
        self.assertEqual(row.badge.text(),'●'); self.assertIn('双击',row.name.toolTip())
        self.assertFalse(any(b.text() in ('开始','完成','已开始') for b in compact.content.findChildren(QPushButton)))
        with patch('task_store.timestamp',return_value=self.now('10:00:00')): QTest.mouseDClick(row.name,Qt.LeftButton)
        app.processEvents(); row=next(r for r in compact.content.findChildren(CompactTaskRow) if r.isVisible())
        row.update_timer(self.now('10:01:05')); self.assertEqual(row.badge.text(),'01:05')
        QTest.mouseDClick(row.badge,Qt.LeftButton); self.assertTrue(row.minutes_only); self.assertEqual(len(self.store.completed()),0)
        row.update_timer(self.now('10:01:05')); self.assertEqual(row.badge.text(),'1.1分')
        with patch('task_store.timestamp',return_value=self.now('10:01:06')): QTest.mouseDClick(row.name,Qt.LeftButton)
        self.assertEqual(len(self.store.completed()),1)
        compact.close(); page.close(); owner.close(); compact.deleteLater(); page.deleteLater(); owner.deleteLater(); app.processEvents()

    def test_right_click_cancel_pause_blink_resume(self):
        task=self.task(); page=PasturePage(store=self.store); owner=QWidget()
        with patch('task_store.timestamp',return_value=self.now('10:00:00')): self.store.start_task(task['id'],self.day)
        compact=CompactTasks(self.store,owner,page); compact.show(); app.processEvents(); row=compact.content.findChildren(CompactTaskRow)[0]
        event=QContextMenuEvent(QContextMenuEvent.Mouse,QPoint(1,1),QPoint(1,1))
        with patch('compact_tasks.QMessageBox.question',return_value=QMessageBox.No): row.contextMenuEvent(event)
        self.assertFalse(timer_state(self.store.tasks()[0],self.day)['paused'])
        with patch('compact_tasks.QMessageBox.question',return_value=QMessageBox.Yes),patch('task_store.timestamp',return_value=self.now('10:01:05')): row.contextMenuEvent(event)
        app.processEvents(); row=next(r for r in compact.content.findChildren(CompactTaskRow) if r.isVisible())
        with patch('compact_tasks.time.monotonic',return_value=0): row.update_timer(self.now('10:15:00')); first=row.badge.styleSheet()
        with patch('compact_tasks.time.monotonic',return_value=.5): row.update_timer(self.now('10:20:00')); second=row.badge.styleSheet()
        self.assertEqual(row.badge.text(),'01:05'); self.assertNotEqual(first,second)
        compact.grab().save(str(Path(__file__).parent/'ui_previews'/'compact_paused_timer.png'))
        with patch('compact_tasks.QMessageBox.question',return_value=QMessageBox.Yes),patch('task_store.timestamp',return_value=self.now('10:20:00')): row.contextMenuEvent(event)
        self.assertFalse(timer_state(self.store.tasks()[0],self.day)['paused'])
        compact.close(); self.assertFalse(compact.clock_timer.isActive()); page.close(); owner.close(); compact.deleteLater(); page.deleteLater(); owner.deleteLater(); app.processEvents()

    def test_template_files_copy_and_safe_open(self):
        source=Path(self.temp.name)/'操作SOP.txt'; source.write_text('示例流程',encoding='utf-8')
        editor=TemplateEditor(self.store); editor.title.setText('文件式SOP'); editor.files=[{'name':source.name,'path':str(source),'pending':True}]; editor.commit()
        attachment=self.store.templates()[0]['attachments'][0]; destination=self.store.root/attachment['path']
        self.assertTrue(destination.is_file()); source.unlink(); self.assertTrue(destination.is_file())
        with patch('template_library.QDesktopServices.openUrl',return_value=True) as opened:
            self.assertTrue(open_template_file(self.store,attachment)); self.assertEqual(Path(opened.call_args[0][0].toLocalFile()),destination.resolve())
        blocked=self.store.root/'config'/'template_attachments'/'unsafe.cmd'; blocked.write_text('not executable in test',encoding='utf-8')
        with patch('template_library.QMessageBox.warning'),patch('template_library.QDesktopServices.openUrl') as opened:
            self.assertFalse(open_template_file(self.store,{'path':str(blocked.relative_to(self.store.root)),'managed':True})); opened.assert_not_called()
        library=TemplateLibrary(self.store); library.show(); app.processEvents(); self.assertEqual(library.file_list.count(),1)
        library.grab().save(str(Path(__file__).parent/'ui_previews'/'template_files.png'))
        library.close(); editor.close(); library.deleteLater(); editor.deleteLater(); app.processEvents()

    def test_template_file_failed_save_rolls_back_copy(self):
        source=Path(self.temp.name)/'SOP.txt'; source.write_text('example',encoding='utf-8')
        editor=TemplateEditor(self.store); editor.title.setText('模板'); editor.files=[{'name':source.name,'path':str(source),'pending':True}]
        with patch.object(self.store,'save_template',side_effect=RuntimeError('failed')),patch('template_library.QMessageBox.warning'): editor.commit()
        self.assertTrue(source.exists()); self.assertEqual(self.store.templates(),[]); self.assertEqual(list((self.store.root/'config'/'template_attachments').iterdir()),[])
        editor.close(); editor.deleteLater(); app.processEvents()

if __name__=='__main__': unittest.main()
