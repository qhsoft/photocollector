"""
照片和视频浏览管理应用
主界面为照片浏览器，左侧为 Tab 导航，右侧为照片列表显示
"""
import sys
import os
import json
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
)
from PySide6.QtGui import QPixmap, QIcon, QAction

from database import DatabaseManager
from collect import CollectDialog
from timeline_panel import TimelinePanel
from tag_panel import TagPanel
from recycle_panel import RecyclePanel
from photo_list_widget import PhotoListWidget
from person_panel import PersonPanel
from settings_dialog import SettingsDialog
from face_detail_panel import FaceDetailPanel


class MainWindow(QMainWindow):
    """主窗口 - 照片浏览器"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("照片浏览管理")
        self.resize(1200, 700)
        
        self.db_manager = DatabaseManager()
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        
        # 左侧 Tab 导航
        self.left_tabs = QTabWidget()
        self.left_tabs.setMaximumWidth(300)
        
        self.timeline_panel = TimelinePanel(self.db_manager)
        self.tag_panel = TagPanel(self.db_manager)
        self.recycle_panel = RecyclePanel(self.db_manager)
        self.person_panel = PersonPanel(self.db_manager)
        
        self.left_tabs.addTab(self.timeline_panel, "时间")
        self.left_tabs.addTab(self.tag_panel, "标签")
        self.left_tabs.addTab(self.recycle_panel, "回收站")
        self.left_tabs.addTab(self.person_panel, "人员")
        
        main_layout.addWidget(self.left_tabs, 0)
        
        # 主体左右分栏：左侧照片列表，右侧详情面板
        self.photo_list = PhotoListWidget(db_manager=self.db_manager, show_detail_callback=self.show_photo_detail)
        self.detail_panel = QWidget()
        detail_layout = QVBoxLayout(self.detail_panel)
        self.detail_img = QLabel()
        self.detail_img.setAlignment(Qt.AlignCenter)
        detail_layout.addWidget(self.detail_img)

        self.meta_text = QTextEdit()
        self.meta_text.setReadOnly(True)
        detail_layout.addWidget(self.meta_text)

        self.face_table = QTableWidget()
        self.face_table.setColumnCount(3)
        self.face_table.setHorizontalHeaderLabels(['人脸ID', '特征', 'bbox'])
        detail_layout.addWidget(self.face_table)

        # 左右分栏
        body_layout = QHBoxLayout()
        self.photo_list.setMinimumWidth(500)
        self.detail_panel.setMaximumWidth(320)
        body_layout.addWidget(self.photo_list, 4)
        body_layout.addWidget(self.detail_panel, 1)
        main_layout.addLayout(body_layout, 1)

        central_widget.setLayout(main_layout)

        # 连接相册选择
        self.timeline_panel.year_list.itemClicked.connect(self.on_year_selected)

    def show_photo_detail(self, file_id):
        # 显示图片
        rec = self.db_manager.get_file_by_id(file_id)
        if not rec:
            return
        # 使用全局照片存放路径 + 数据库中保存的相对路径来定位文件
        photo_dir = self.get_photo_dir()
        img_path = None
        rel = rec.get('file_path')
        if photo_dir and rel:
            img_path = os.path.join(photo_dir, rel)
        if img_path and os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            self.detail_img.setPixmap(pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            meta = self.get_image_meta(img_path)
            self.meta_text.setText(meta)
        else:
            self.detail_img.clear()
            self.meta_text.setText('图片文件不存在')
        # 显示人脸数据
        self.face_table.setRowCount(0)
        faces = self.get_faces_for_image(file_id)
        for i, face in enumerate(faces):
            self.face_table.insertRow(i)
            self.face_table.setItem(i, 0, QTableWidgetItem(str(face.get('id', ''))))
            self.face_table.setItem(i, 1, QTableWidgetItem(face.get('feature', '')))
            self.face_table.setItem(i, 2, QTableWidgetItem(face.get('bbox', '')))

    def get_faces_for_image(self, file_id):
        # 直接通过图片数据库id查找人脸数据
        try:
            return self.db_manager.get_faces_by_photo(file_id)
        except Exception:
            return []

    def get_image_meta(self, img_path):
        # 这里可以扩展为读取 EXIF、文件大小、创建时间等
        try:
            info = []
            info.append(f"文件名: {os.path.basename(img_path)}")
            info.append(f"路径: {img_path}")
            info.append(f"大小: {os.path.getsize(img_path)} bytes")
            info.append(f"修改时间: {datetime.fromtimestamp(os.path.getmtime(img_path))}")
            # 可扩展 EXIF 信息
            return '\n'.join(info)
        except Exception as e:
            return f"读取元信息失败: {e}"

    def on_year_selected(self, item):
        """选中年份时，按年份筛选照片"""
        year = int(item.text())
        start = datetime(year, 1, 1, 0, 0, 0)
        end = datetime(year + 1, 1, 1, 0, 0, 0)
        self.photo_list.load_photos_from_database(created_after=start, created_before=end)

    def create_menu_bar(self):
        menubar = self.menuBar()
        # 设置菜单
        settings_action = QAction("设置照片路径", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        menubar.addAction(settings_action)
        # 归集入口
        collect_action = QAction("自动归集", self)
        collect_action.triggered.connect(self.open_collect_dialog)
        menubar.addAction(collect_action)
        # 同步入口
        sync_action = QAction("同步照片库", self)
        sync_action.triggered.connect(self.start_sync)
        menubar.addAction(sync_action)
        # ...existing code...

    def open_settings_dialog(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.refresh_photo_list()

    def open_collect_dialog(self):
        """打开照片归集对话框"""
        dlg = CollectDialog(self, db_manager=self.db_manager)
        dlg.exec()

    def get_photo_dir(self):
        try:
            with open('settings.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('photo_dir', '')
        except Exception:
            return ''

    def refresh_photo_list(self):
        photo_dir = self.get_photo_dir()
        if photo_dir:
            pass

    def start_sync(self):
        """同步照片库入口"""
        dlg = QMessageBox(self)
        dlg.setWindowTitle("同步照片库")
        dlg.setText("同步功能已移除或未实现。")
        dlg.setIcon(QMessageBox.Information)
        dlg.exec()


def main():
    app = QApplication(sys.argv)
    
    window = MainWindow()
    
    # 设置应用图标
    icon_path = os.path.join(os.path.dirname(__file__), 'app_icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
