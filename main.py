import sys
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path

from PIL import Image, ExifTags
from exif import Image as ExifImage
import struct
from datetime import timedelta
import zlib

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QProgressBar,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QLineEdit,
    QCheckBox,
)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif', '.heic'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.mts'}
ALL_EXTS = IMAGE_EXTS | VIDEO_EXTS


def get_exif_datetime(path: str):
    try:
        img = Image.open(path)
        exif = img.getexif()
        img.close()
        if not exif:
            return None
        # map tag id to name
        tagmap = {v: k for k, v in ExifTags.TAGS.items()}
        # DateTimeOriginal tag name is 'DateTimeOriginal'
        for tag_name in ('DateTimeOriginal', 'DateTime'):
            tag_id = tagmap.get(tag_name)
            if tag_id and tag_id in exif:
                val = exif[tag_id]
                # typical format: "YYYY:MM:DD HH:MM:SS"
                try:
                    return datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
                except Exception:
                    pass
        return None
    except Exception:
        return None


def get_mp4_creation_time(path: str):
    """Parse MP4/MOV atoms to find mvhd creation_time without external tools.

    Many MP4/MOV files store creation_time in the 'mvhd' atom inside 'moov'.
    The creation_time is seconds since 1904-01-01 UTC.
    This parser is lightweight and only handles basic atom traversal.
    """
    try:
        with open(path, 'rb') as f:
            filesize = os.fstat(f.fileno()).st_size
            def read_atom_header():
                hdr = f.read(8)
                if len(hdr) < 8:
                    return None, None
                size, typ = struct.unpack('>I4s', hdr)
                return size, typ.decode('utf-8', errors='ignore')

            def parse_container(end_offset):
                while f.tell() < end_offset:
                    pos = f.tell()
                    size, typ = read_atom_header()
                    if not size or size < 8:
                        break
                    # handle extended size
                    header_size = 8
                    if size == 1:
                        largesize_data = f.read(8)
                        if len(largesize_data) < 8:
                            break
                        size = struct.unpack('>Q', largesize_data)[0]
                        header_size += 8
                    data_size = size - header_size

                    # if it's 'moov' or other container, descend
                    if typ == 'moov' or typ == 'trak' or typ == 'udta' or typ == 'meta':
                        # parse inside this container
                        parse_container(pos + size)
                        f.seek(pos + size)
                        continue

                    if typ == 'mvhd':
                        # read version (1 byte) and flags (3 bytes)
                        v = f.read(1)
                        if not v:
                            return None
                        version = v[0]
                        f.read(3)
                        if version == 1:
                            data = f.read(8)
                            if len(data) < 8:
                                return None
                            creation = struct.unpack('>Q', data)[0]
                        else:
                            data = f.read(4)
                            if len(data) < 4:
                                return None
                            creation = struct.unpack('>I', data)[0]
                        # MP4 epoch starts at 1904-01-01
                        try:
                            dt = datetime(1904, 1, 1) + timedelta(seconds=creation)
                            return dt
                        except Exception:
                            return None

                    # otherwise skip this atom
                    f.seek(data_size, os.SEEK_CUR)
                return None

            # start parsing from file start
            f.seek(0)
            return parse_container(filesize)
    except Exception:
        return None


def get_file_datetime(path: str):
    try:
        stat = os.stat(path)
        # On Windows, st_ctime is creation time; on Unix it's metadata change
        # Use creation time if available
        ctime = getattr(stat, 'st_ctime', None)
        mtime = getattr(stat, 'st_mtime', None)
        if ctime:
            return datetime.fromtimestamp(ctime)
        elif mtime:
            return datetime.fromtimestamp(mtime)
    except Exception:
        pass
    return None


def get_media_datetime(path: str):
    """Try to get datetime from EXIF/metadata, then fallback to file times.
    Priority: EXIF -> MP4 atom -> File timestamp
    """
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXTS:
        # first try exif library for images
        try:
            dt = get_exif_datetime(path)
            if dt:
                return dt
        except Exception:
            pass
    # Try MP4 atom parser for mov/mp4 (and potentially other formats)
    try:
        dt = get_mp4_creation_time(path)
        if dt:
            return dt
    except Exception:
        pass
    # fallback to file times
    return get_file_datetime(path)


class CollectorThread(QThread):
    progress_changed = Signal(int, int)  # processed, total
    log = Signal(str)
    error = Signal(str)
    finished_signal = Signal()
    stats_changed = Signal(int, int, int)  # total, copied_moved, skipped

    def __init__(self, src: str, dst: str, move_files: bool = False):
        super().__init__()
        self.src = src
        self.dst = dst
        self.move_files = move_files
        self._stop_requested = False
        self.total_files = 0
        self.copied_moved = 0
        self.skipped = 0

    def stop(self):
        self._stop_requested = True

    def run(self):
        try:
            # gather files
            files = []
            for root, dirs, filenames in os.walk(self.src):
                for fn in filenames:
                    if Path(fn).suffix.lower() in ALL_EXTS:
                        files.append(os.path.join(root, fn))
            self.total_files = len(files)
            processed = 0
            self.log.emit(f"找到 {self.total_files} 个媒体文件。")
            self.stats_changed.emit(self.total_files, self.copied_moved, self.skipped)

            def file_crc32(path):
                try:
                    bufsize = 65536
                    crc = 0
                    with open(path, 'rb') as f:
                        while True:
                            data = f.read(bufsize)
                            if not data:
                                break
                            crc = zlib.crc32(data, crc)
                    return crc & 0xFFFFFFFF
                except Exception:
                    return None

            for src_path in files:
                if self._stop_requested:
                    self.log.emit("取消操作，已停止处理。")
                    break
                try:
                    dt = get_media_datetime(src_path)
                    if not dt:
                        dt = datetime.now()
                        self.log.emit(f"无法读取元数据，使用当前时间：{src_path}")
                    year = dt.year
                    target_dir = os.path.join(self.dst, str(year))
                    os.makedirs(target_dir, exist_ok=True)

                    base = os.path.basename(src_path)
                    name, ext = os.path.splitext(base)
                    target_path = os.path.join(target_dir, base)

                    src_crc = file_crc32(src_path)
                    candidate_path = target_path
                    counter = 1
                    skipped_file = False
                    while os.path.exists(candidate_path):
                        dst_crc = file_crc32(candidate_path)
                        if dst_crc == src_crc:
                            self.log.emit(f"跳过（内容一致）: {src_path} -> {candidate_path}")
                            self.skipped += 1
                            skipped_file = True
                            break
                        # 文件名递增
                        candidate_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
                        counter += 1
                    
                    if not skipped_file:
                        # candidate_path 不存在或内容不同
                        if self.move_files:
                            shutil.move(src_path, candidate_path)
                            self.log.emit(f"移动: {src_path} -> {candidate_path}")
                        else:
                            shutil.copy2(src_path, candidate_path)
                            self.log.emit(f"复制: {src_path} -> {candidate_path}")
                        self.copied_moved += 1

                except Exception as e:
                    self.error.emit(f"处理文件失败: {src_path}  错误: {e}")

                processed += 1
                self.progress_changed.emit(processed, self.total_files)
                self.stats_changed.emit(self.total_files, self.copied_moved, self.skipped)

            self.finished_signal.emit()
        except Exception as e:
            self.error.emit(f"线程失败: {e}")
            self.finished_signal.emit()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("照片和视频自动归集")
        self.resize(800, 500)

        layout = QVBoxLayout()

        # source
        hsrc = QHBoxLayout()
        self.src_edit = QLineEdit()
        btn_src = QPushButton("选择源目录")
        btn_src.clicked.connect(self.choose_src)
        hsrc.addWidget(QLabel("源目录:"))
        hsrc.addWidget(self.src_edit)
        hsrc.addWidget(btn_src)
        layout.addLayout(hsrc)

        # dest
        hdst = QHBoxLayout()
        self.dst_edit = QLineEdit()
        btn_dst = QPushButton("选择目标目录")
        btn_dst.clicked.connect(self.choose_dst)
        hdst.addWidget(QLabel("目标目录:"))
        hdst.addWidget(self.dst_edit)
        hdst.addWidget(btn_dst)
        layout.addLayout(hdst)

        # options
        opts = QHBoxLayout()
        self.btn_start = QPushButton("开始")
        self.btn_start.clicked.connect(self.start_collect)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_collect)
        self.move_checkbox = QCheckBox("移动文件（否则为复制）")
        opts.addWidget(self.btn_start)
        opts.addWidget(self.btn_cancel)
        opts.addWidget(self.move_checkbox)
        layout.addLayout(opts)

        # progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        # log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        # status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        layout.addLayout(status_layout)

        self.setLayout(layout)

        self.worker = None

    def choose_src(self):
        d = QFileDialog.getExistingDirectory(self, "选择源目录")
        if d:
            self.src_edit.setText(d)

    def choose_dst(self):
        d = QFileDialog.getExistingDirectory(self, "选择目标目录")
        if d:
            self.dst_edit.setText(d)

    def append_log(self, text: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log.append(f"[{ts}] {text}")

    def start_collect(self):
        src = self.src_edit.text().strip()
        dst = self.dst_edit.text().strip()
        if not src or not os.path.isdir(src):
            QMessageBox.warning(self, "错误", "请先选择有效的源目录。")
            return
        if not dst:
            QMessageBox.warning(self, "错误", "请先选择目标目录。")
            return
        os.makedirs(dst, exist_ok=True)

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.log.clear()
        self.progress.setValue(0)

        self.worker = CollectorThread(src, dst, move_files=self.move_checkbox.isChecked())
        self.worker.progress_changed.connect(self.on_progress)
        self.worker.log.connect(self.append_log)
        self.worker.error.connect(self.on_error)
        self.worker.stats_changed.connect(self.on_stats_changed)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def cancel_collect(self):
        if self.worker:
            self.worker.stop()
            self.append_log("已请求取消，正在停止…")
            self.btn_cancel.setEnabled(False)

    def on_progress(self, processed: int, total: int):
        if total == 0:
            self.progress.setValue(100)
        else:
            val = int(processed / total * 100)
            self.progress.setValue(val)

    def on_stats_changed(self, total: int, copied_moved: int, skipped: int):
        self.status_label.setText(
            f"总数: {total} | 已复制/移动: {copied_moved} | 已跳过: {skipped}"
        )

    def on_error(self, text: str):
        self.append_log(f"错误: {text}")

    def on_finished(self):
        self.append_log("处理完成")
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    # 设置应用图标（如果存在）
    icon_path = os.path.join(os.path.dirname(__file__), 'app_icon.ico')
    if os.path.exists(icon_path):
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
