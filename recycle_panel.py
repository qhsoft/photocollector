"""回收站面板"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QListWidgetItem, QPushButton
)
from database import DatabaseManager


class RecyclePanel(QWidget):
    """回收站面板：显示软删除的记录"""
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        layout = QVBoxLayout()
        label = QLabel("回收站（软删除记录）：")
        layout.addWidget(label)

        self.list = QListWidget()
        layout.addWidget(self.list)

        btn_layout = QHBoxLayout()
        btn_restore = QPushButton("恢复所选")
        btn_purge = QPushButton("永久删除所选")
        btn_refresh = QPushButton("刷新")
        btn_restore.clicked.connect(self.restore_selected)
        btn_purge.clicked.connect(self.purge_selected)
        btn_refresh.clicked.connect(self.refresh)
        btn_layout.addWidget(btn_restore)
        btn_layout.addWidget(btn_purge)
        btn_layout.addWidget(btn_refresh)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.refresh()

    def refresh(self):
        self.list.clear()
        files = self.db_manager.get_all_files(include_deleted=True)
        for rec in files:
            if rec.get('is_deleted') == 1:
                # 直接显示文件相对路径（数据库中存储的路径），将 id 存入 UserRole
                display = rec.get('file_path')
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, rec.get('id'))
                self.list.addItem(item)

    def restore_selected(self):
        items = self.list.selectedItems()
        if not items:
            return
        for it in items:
            fid = it.data(Qt.UserRole)
            self.db_manager.restore_file(fid)
        self.refresh()

    def purge_selected(self):
        items = self.list.selectedItems()
        if not items:
            return
        for it in items:
            fid = it.data(Qt.UserRole)
            self.db_manager.delete_file_permanently(fid)
        self.refresh()
