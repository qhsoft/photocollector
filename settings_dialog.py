"""设置对话框"""
import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QFileDialog
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings_path='settings.json'):
        super().__init__(parent)
        self.setWindowTitle("设置照片存放路径")
        self.resize(400, 120)
        self.settings_path = settings_path
        layout = QVBoxLayout(self)
        self.path_edit = QLineEdit()
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self.browse_path)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.path_edit)
        hlayout.addWidget(btn_browse)
        layout.addLayout(hlayout)
        btn_ok = QPushButton("保存")
        btn_ok.clicked.connect(self.save)
        layout.addWidget(btn_ok)
        self.load()
    
    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择照片存放路径", self.path_edit.text())
        if path:
            self.path_edit.setText(path)
    
    def load(self):
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.path_edit.setText(data.get('photo_dir', ''))
        except Exception:
            pass
    
    def save(self):
        path = self.path_edit.text().strip()
        if path:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump({'photo_dir': path}, f)
            self.accept()
