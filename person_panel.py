"""人员管理面板"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QPushButton, QDialog, 
    QLineEdit, QMessageBox
)
from database import DatabaseManager


class PersonPanel(QWidget):
    """人员管理面板"""
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self.layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['姓名', '操作'])
        self.layout.addWidget(self.table)
        btn_add = QPushButton("添加人员")
        btn_add.clicked.connect(self.add_person)
        self.layout.addWidget(btn_add)
        self.refresh_table()

    def refresh_table(self):
        persons = self.db_manager.get_all_persons()
        self.table.setRowCount(len(persons))
        for i, p in enumerate(persons):
            self.table.setItem(i, 0, QTableWidgetItem(p['name']))
            btn_del = QPushButton("删除")
            btn_del.clicked.connect(lambda _, pid=p['id']: self.delete_person(pid))
            self.table.setCellWidget(i, 1, btn_del)

    def add_person(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("添加人员")
        layout = QVBoxLayout(dlg)
        name_edit = QLineEdit()
        layout.addWidget(QLabel("姓名:"))
        layout.addWidget(name_edit)
        btn_ok = QPushButton("确定")
        layout.addWidget(btn_ok)
        btn_ok.clicked.connect(lambda: self._do_add_person(dlg, name_edit.text()))
        dlg.exec()

    def _do_add_person(self, dlg, name):
        if name.strip():
            self.db_manager.add_person(name, "")
            dlg.accept()
            self.refresh_table()

    def delete_person(self, pid):
        reply = QMessageBox.question(self, "确认", "确定要删除该人员吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db_manager.delete_person(pid)
            self.refresh_table()
