"""标签浏览面板"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget
from database import DatabaseManager


class TagPanel(QWidget):
    """标签浏览面板"""
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        
        layout = QVBoxLayout()
        
        label = QLabel("标签:")
        layout.addWidget(label)
        
        self.tag_list = QListWidget()
        layout.addWidget(self.tag_list)
        
        layout.addStretch()
        
        self.setLayout(layout)
        self.add_tag("全部")

    def add_tag(self, tag_name: str):
        """添加标签项"""
        self.tag_list.addItem(tag_name)
