"""照片/人脸详情面板"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox, QInputDialog
)
from database import DatabaseManager


class FaceDetailPanel(QWidget):
    """照片/人脸详情界面"""
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager

        layout = QVBoxLayout()

        # 照片显示区域
        self.photo_label = QLabel("照片区域")
        layout.addWidget(self.photo_label)

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.mark_person_btn = QLabel("标记为某人")
        btn_layout.addWidget(self.mark_person_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
