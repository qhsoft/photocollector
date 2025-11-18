"""时间线浏览面板"""
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget
from database import DatabaseManager


class TimelinePanel(QWidget):
    """时间线浏览面板"""
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        
        layout = QVBoxLayout()
        
        label = QLabel("按年份浏览:")
        layout.addWidget(label)
        
        self.year_list = QListWidget()
        layout.addWidget(self.year_list)
        
        layout.addStretch()
        
        self.setLayout(layout)

        self.refresh_years()
    
    def refresh_years(self):
        """根据数据库文件创建时间统计年份"""
        self.year_list.clear()
        years = set()
        files = self.db_manager.get_all_files()
        for rec in files:
            created_at = rec.get('created_at')
            if created_at:
                try:
                    year = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').year
                    years.add(year)
                except Exception:
                    pass
        years = sorted(list(years), reverse=True)
        for year in years:
            self.year_list.addItem(str(year))
