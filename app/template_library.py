"""Local SOP/message templates with explicit, validated web-link navigation."""
import re
import uuid
import shutil
from pathlib import Path
from PySide6.QtCore import Qt,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,
    QTextEdit,QPushButton,QLabel,QListWidget,QSplitter,QWidget,QMessageBox,QApplication)

def web_links(text):
    candidates=re.findall(r'https?://[^\s<>]+',text)
    result=[]
    for value in candidates:
        value=value.rstrip('。，；）]')
        url=QUrl(value)
        if url.isValid() and url.scheme() in ('http','https') and url.host() and value not in result: result.append(value)
    return result

def open_template_file(store,attachment,parent=None):
    path=Path(attachment.get('path','')); path=path if path.is_absolute() else store.root/path
    if attachment.get('managed'):
        try: path.resolve().relative_to((store.root/'config'/'template_attachments').resolve())
        except ValueError: QMessageBox.warning(parent,'附件路径异常','附件路径不在模板文件目录中。'); return False
    if not path.is_file(): QMessageBox.warning(parent,'文件不存在','附件可能被移动或删除，请重新添加。'); return False
    if path.suffix.lower() in ('.exe','.bat','.cmd','.ps1','.vbs','.js','.msi','.py','.scr','.lnk','.url','.hta','.com','.pif','.wsf','.reg'):
        QMessageBox.warning(parent,'安全提示','不直接运行脚本、快捷方式或安装程序附件。'); return False
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

class TemplateEditor(QDialog):
    def __init__(self,store,template=None,parent=None):
        super().__init__(parent); self.store=store; self.template=dict(template or {'id':uuid.uuid4().hex})
        self.setWindowTitle('编辑做事模板' if template else '新增做事模板'); self.resize(640,580)
        layout=QVBoxLayout(self); form=QFormLayout(); layout.addLayout(form)
        self.title=QLineEdit(self.template.get('title','')); form.addRow('模板名称 / 标签',self.title)
        self.kind=QComboBox(); self.kind.addItems(['SOP','邮件模板','微信话术','在线文档','其他'])
        self.kind.setCurrentText(self.template.get('kind','SOP')); form.addRow('模板类型',self.kind)
        self.body=QTextEdit(); self.body.setPlainText(self.template.get('body','')); self.body.setPlaceholderText('操作步骤、邮件正文、回复话术，可在正文中放 https:// 链接。')
        layout.addWidget(self.body,1)
        self.links=QTextEdit(); self.links.setMaximumHeight(85); self.links.setPlaceholderText('在线文档网址，每行一个，仅支持 http / https')
        self.links.setPlainText('\n'.join(self.template.get('links',[]))); layout.addWidget(self.links)
        self.files=[dict(record) for record in self.template.get('attachments',[])]
        self.file_list=QListWidget(); self.file_list.setMaximumHeight(90); layout.addWidget(QLabel('模板文件（保存时复制到本地模板库）')); layout.addWidget(self.file_list); self.render_files()
        file_row=QHBoxLayout(); layout.addLayout(file_row)
        add_file=QPushButton('＋ 添加文件'); add_file.clicked.connect(self.add_files); file_row.addWidget(add_file)
        remove_file=QPushButton('移除选中附件'); remove_file.clicked.connect(self.remove_file); file_row.addWidget(remove_file); file_row.addStretch()
        row=QHBoxLayout(); layout.addLayout(row); row.addStretch()
        cancel=QPushButton('取消'); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        save=QPushButton('保存模板'); save.clicked.connect(self.commit); row.addWidget(save)

    def render_files(self): self.file_list.clear(); self.file_list.addItems([f.get('name',Path(f.get('path','')).name) for f in self.files])
    def add_files(self):
        from PySide6.QtWidgets import QFileDialog
        paths,_=QFileDialog.getOpenFileNames(self,'添加模板文件')
        self.files.extend({'name':Path(path).name,'path':path,'pending':True} for path in paths); self.render_files()
    def remove_file(self):
        index=self.file_list.currentRow()
        if index>=0: self.files.pop(index); self.render_files()

    def commit(self):
        links=[line.strip() for line in self.links.toPlainText().splitlines() if line.strip()]
        if any(web_links(link)!=[link] for link in links):
            QMessageBox.warning(self,'链接格式','请每行填写一个完整的 http:// 或 https:// 网页地址。'); return
        if not self.title.text().strip(): QMessageBox.warning(self,'需要名称','请填写模板名称。'); return
        copied=[]; files=[]
        try:
            for record in self.files:
                if record.get('pending'):
                    directory=self.store.root/'config'/'template_attachments'; directory.mkdir(exist_ok=True,parents=True)
                    target=directory/(uuid.uuid4().hex+Path(record['path']).suffix)
                    copied.append(target); shutil.copy2(record['path'],target)
                    record={'name':record['name'],'path':str(target.relative_to(self.store.root)),'managed':True}
                files.append(record)
            self.template.update(title=self.title.text().strip(),kind=self.kind.currentText(),body=self.body.toPlainText(),links=links,attachments=files)
            self.store.save_template(self.template)
        except Exception as exc:
            for path in copied: path.unlink(missing_ok=True)
            QMessageBox.warning(self,'保存失败',str(exc)); return
        self.accept()

class TemplateLibrary(QDialog):
    def __init__(self,store,selected_id=None,parent=None):
        super().__init__(parent); self.store=store; self.current=None
        self.setWindowTitle('做事模板 · SOP / 邮件 / 微信话术'); self.resize(900,640)
        layout=QVBoxLayout(self); toolbar=QHBoxLayout(); layout.addLayout(toolbar)
        self.search=QLineEdit(); self.search.setPlaceholderText('搜索模板名称或内容'); self.search.textChanged.connect(self.reload); toolbar.addWidget(self.search,1)
        add=QPushButton('＋ 新建模板'); add.clicked.connect(self.create); toolbar.addWidget(add)
        splitter=QSplitter(); layout.addWidget(splitter,1)
        self.list=QListWidget(); self.list.setMinimumWidth(200); self.list.currentRowChanged.connect(self.select); splitter.addWidget(self.list)
        panel=QWidget(); self.panel_layout=QVBoxLayout(panel); splitter.addWidget(panel); splitter.setStretchFactor(1,3)
        self.heading=QLabel('选择模板，或创建第一份做事模板'); self.heading.setWordWrap(True); self.heading.setStyleSheet('font-size:20px;font-weight:600;'); self.panel_layout.addWidget(self.heading)
        self.body=QTextEdit(); self.body.setReadOnly(True); self.panel_layout.addWidget(self.body,1)
        self.file_list=QListWidget(); self.file_list.setMaximumHeight(95); self.file_list.setToolTip('双击打开附件，或选中后点击打开文件')
        self.file_list.itemDoubleClicked.connect(lambda item:self.open_file()); self.panel_layout.addWidget(self.file_list)
        self.open_file_button=QPushButton('打开选中的模板文件'); self.open_file_button.clicked.connect(self.open_file); self.panel_layout.addWidget(self.open_file_button)
        self.link_box=QWidget(); self.link_rows=QVBoxLayout(self.link_box); self.panel_layout.addWidget(self.link_box)
        actions=QHBoxLayout(); self.panel_layout.addLayout(actions)
        self.copy=QPushButton('复制正文'); self.copy.clicked.connect(lambda:QApplication.clipboard().setText(self.body.toPlainText())); actions.addWidget(self.copy)
        self.edit=QPushButton('编辑模板'); self.edit.clicked.connect(self.edit_current); actions.addWidget(self.edit)
        close=QPushButton('关闭'); close.clicked.connect(self.accept); actions.addWidget(close)
        self.reload(selected_id=selected_id)

    def reload(self,*args,selected_id=None):
        target=selected_id or (self.current or {}).get('id')
        query=self.search.text().strip().lower()
        self.entries=sorted([t for t in self.store.templates() if query in (t['title']+' '+t.get('body','')+' '+' '.join(f.get('name','') for f in t.get('attachments',[]))).lower()],key=lambda t:t['title'])
        self.list.blockSignals(True); self.list.clear(); self.list.addItems([t.get('kind','SOP')+' · '+t['title'] for t in self.entries]); self.list.blockSignals(False)
        index=next((i for i,t in enumerate(self.entries) if t['id']==target),0 if self.entries else -1)
        self.list.setCurrentRow(index); self.select(index)

    def select(self,index):
        self.current=self.entries[index] if 0<=index<len(self.entries) else None
        self.heading.setText(self.current['title'] if self.current else '没有匹配的模板'); self.body.setPlainText((self.current or {}).get('body',''))
        self.copy.setEnabled(bool(self.current)); self.edit.setEnabled(bool(self.current))
        while self.link_rows.count():
            item=self.link_rows.takeAt(0)
            if item.widget(): item.widget().hide(); item.widget().deleteLater()
        template=self.current or {}
        self.file_list.clear(); self.file_list.addItems([f.get('name','模板文件') for f in template.get('attachments',[])])
        has_files=bool(template.get('attachments')); self.file_list.setVisible(has_files); self.open_file_button.setVisible(has_files)
        if has_files: self.file_list.setCurrentRow(0)
        for url in web_links('\n'.join(template.get('links',[]))+'\n'+template.get('body','')):
            button=QPushButton('打开在线文档：'+url[:80]); button.setToolTip(url)
            button.clicked.connect(lambda checked=False,u=url:QDesktopServices.openUrl(QUrl(u))); self.link_rows.addWidget(button)

    def open_file(self):
        files=(self.current or {}).get('attachments',[]); index=self.file_list.currentRow()
        if 0<=index<len(files): open_template_file(self.store,files[index],self)

    def create(self):
        dialog=TemplateEditor(self.store,parent=self)
        if dialog.exec(): self.reload(selected_id=dialog.template['id'])
    def edit_current(self):
        if self.current:
            dialog=TemplateEditor(self.store,self.current,self)
            if dialog.exec(): self.reload(selected_id=dialog.template['id'])
