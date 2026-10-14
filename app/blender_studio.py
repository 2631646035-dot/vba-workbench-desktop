"""Open the editable Blender project and re-export it without blocking Qt."""
import json,subprocess
from pathlib import Path
from PySide6.QtCore import QProcess
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPushButton,QFileDialog,QMessageBox,QPlainTextEdit

ROOT=Path(__file__).resolve().parent/'animation_studio'

class StudioDialog(QDialog):
    process=None
    def reject(self):
        if self.process is not None and self.process.state()!=QProcess.NotRunning: return
        super().reject()
    def closeEvent(self,event):
        if self.process is not None and self.process.state()!=QProcess.NotRunning: event.ignore(); return
        super().closeEvent(event)

def executable():
    config=ROOT/'local_tools.json'
    if config.exists():
        try:
            path=Path(json.loads(config.read_text(encoding='utf-8'))['blender_executable'])
            if path.is_file(): return path
        except (OSError,ValueError,KeyError): pass
    candidate=ROOT.parents[2]/'tools'/'blender'/'blender-4.5.9-windows-x64'/'blender.exe'
    return candidate if candidate.is_file() else None

def open_studio(parent):
    dialog=StudioDialog(parent); dialog.setWindowTitle('角色动画 · Blender 工作室'); dialog.resize(560,520)
    layout=QVBoxLayout(dialog); layout.setContentsMargins(24,24,24,24); layout.setSpacing(14)
    title=QLabel('角色动画工作室'); title_font=QFont(title.font()); title_font.setPointSize(18); title_font.setBold(True); title.setFont(title_font); layout.addWidget(title)
    description=QLabel('在 Blender 中调整角色骨骼、脚步和动作曲线。\n保存工程后点击“同步动作”，工作台会自动载入新动画。\n时间轴：站立 1–60 · 行走 81–140 · 开心 161–220。')
    description.setWordWrap(True); layout.addWidget(description)
    status=QLabel(); layout.addWidget(status)
    def refresh_status():
        path=executable(); status.setText('已连接 Blender · 本地制作，无需账号' if path else '请选择本机 Blender 程序')
    refresh_status()
    open_button=QPushButton('打开 Blender 角色工程'); export_button=QPushButton('同步保存后的动作到工作台'); choose=QPushButton('更换 Blender 程序路径')
    open_button.setObjectName('PrimaryBtn'); export_button.setObjectName('SecondaryBtn')
    for button in (open_button,export_button,choose): button.setMinimumHeight(40)
    for button in (open_button,export_button,choose): layout.addWidget(button)
    log=QPlainTextEdit(); log.setReadOnly(True); log.setPlaceholderText('导出日志会显示在这里'); layout.addWidget(log)
    process=QProcess(dialog); dialog.process=process
    def select():
        filename,_=QFileDialog.getOpenFileName(dialog,'选择 Blender 程序','','Blender (blender.exe)')
        if filename:
            (ROOT/'local_tools.json').write_text(json.dumps({'blender_executable':filename},ensure_ascii=False,indent=2),encoding='utf-8'); refresh_status()
    def check():
        path=executable()
        if not path: select(); path=executable()
        if not path: return None
        if not (ROOT/'companions.blend').exists(): QMessageBox.warning(dialog,'工程缺失','未找到 companions.blend，请恢复 animation_studio 文件夹。'); return None
        return path
    def launch():
        path=check()
        if path:
            try: subprocess.Popen([str(path),str(ROOT/'companions.blend')],cwd=str(ROOT))
            except OSError as exc: QMessageBox.warning(dialog,'打开失败',str(exc))
    def export():
        path=check()
        if not path: return
        export_button.setEnabled(False); open_button.setEnabled(False); choose.setEnabled(False); log.clear()
        process.setWorkingDirectory(str(ROOT)); process.setProgram(str(path))
        process.setArguments(['--background',str(ROOT/'companions.blend'),'--python-exit-code','1','--python',str(ROOT/'build_blender.py'),'--','--export-only'])
        process.setProcessChannelMode(QProcess.MergedChannels); process.start()
    def output(): log.appendPlainText(bytes(process.readAllStandardOutput()).decode('utf-8',errors='replace').strip())
    def finished(code,status_code):
        for button in (export_button,open_button,choose): button.setEnabled(True)
        log.appendPlainText('同步完成，角色将在下一帧使用新动作。' if code==0 else '同步失败，继续使用上一次成功导出的动作。')
    def failed(error):
        for button in (export_button,open_button,choose): button.setEnabled(True)
        log.appendPlainText('无法启动 Blender：'+process.errorString())
    process.readyReadStandardOutput.connect(output); process.finished.connect(finished); process.errorOccurred.connect(failed)
    open_button.clicked.connect(launch); export_button.clicked.connect(export); choose.clicked.connect(select)
    dialog.exec()
