"""照片列表显示面板"""
from datetime import datetime
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem
from PySide6.QtGui import QPixmap, QIcon
from database import DatabaseManager


class PhotoListWidget(QWidget):
    """照片列表显示面板"""
    def __init__(self, db_manager=None, show_detail_callback=None):
        super().__init__()
        self.db_manager = db_manager
        self.show_detail_callback = show_detail_callback
        layout = QVBoxLayout()
        self.photo_list = QListWidget()
        self.photo_list.setIconSize(QSize(80, 80))
        self.photo_list.itemClicked.connect(self.on_photo_clicked)
        layout.addWidget(self.photo_list)
        self.setLayout(layout)

    def refresh(self):
        self.load_photos_from_database()

    def load_photos_from_database(self, created_after=None, created_before=None, tags=None, person_ids=None):
        """
        从数据库加载照片缩略图，支持按创建时间、标签、人员筛选。
        """
        self.photo_list.clear()
        if not self.db_manager:
            return

        # 直接使用数据库层面的筛选
        photos = self.db_manager.get_all_files(
            created_after=created_after,
            created_before=created_before,
            tags=tags,
            person_ids=person_ids
        )

        print(f"加载照片数量: {len(photos)}")
        for photo in photos:
            thumbnail_data = self.db_manager.get_thumbnail(photo['id'])
            if thumbnail_data:
                pixmap = QPixmap()
                pixmap.loadFromData(thumbnail_data)
                icon = QIcon(pixmap.scaled(320, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                icon = QIcon()
            # 显示相对路径/名称作为标签，但把 file_id 放在 UserRole，方便直接查询详情
            display_text = photo.get("file_path")
            list_item = QListWidgetItem(icon, display_text)
            list_item.setData(Qt.UserRole, photo.get('id'))
            self.photo_list.addItem(list_item)

        # 设置每行显示 5 个缩略图
        self.photo_list.setGridSize(QSize(320, 240))
        self.photo_list.setViewMode(QListWidget.IconMode)
        self.photo_list.setResizeMode(QListWidget.Adjust)

    def on_photo_clicked(self, item):
        # 触发外部回调，传递 file_id（UserRole 中存储）
        if self.show_detail_callback:
            file_id = item.data(Qt.UserRole)
            try:
                file_id = int(file_id)
            except Exception:
                pass
            self.show_detail_callback(file_id)
