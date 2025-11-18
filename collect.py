# 导入 CollectDialog 所需的 Qt 组件和依赖
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QHBoxLayout,
    QComboBox, QCheckBox, QProgressBar, QTextEdit, QLabel, QMessageBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QWidget
)
import insightface
import numpy as np
import cv2
from PIL import Image
import io

# 初始化 insightface 模型（buffalo_sc）
face_model = insightface.app.FaceAnalysis(name='buffalo_sc', providers=['CPUExecutionProvider'])
face_model.prepare(ctx_id=0)

def extract_faces(image_path, confidence_threshold=0.5):
    """
    检测图片中的人脸，返回人脸特征和 bbox 列表
    :param image_path: 图片路径
    :param confidence_threshold: 置信度阈值，低于该值的人脸将被过滤
    :return: List[dict] 每个 dict 包含 feature(str), bbox(str)
    """
    try:
        print(image_path)
        img = None
        # 优先使用 np.fromfile + cv2.imdecode 来支持 Windows 上的 Unicode 路径
        try:
            data = np.fromfile(image_path, dtype=np.uint8)
            if data.size:
                img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            img = None

        # 回退：有时 imdecode 也会失败，尝试使用 cv2.imread
        if img is None:
            try:
                img = cv2.imread(image_path)
            except Exception:
                img = None

        print('#' * 10)
        if img is None:
            return []

        faces = face_model.get(img)
        result = []
        for face in faces:
            if face.det_score < confidence_threshold:
                continue
            # feature: ndarray, bbox: list
            feature = face.normed_embedding.astype(np.float32).tolist()
            feature_str = ','.join([f'{x:.6f}' for x in feature])
            bbox_str = ','.join([str(int(x)) for x in face.bbox])
            result.append({'feature': feature_str, 'bbox': bbox_str})
        return result
    except Exception:
        return []
from datetime import datetime
from database import DatabaseManager

class CollectDialog(QDialog):
    """文件收集对话框"""
    def __init__(self, parent=None, db_manager=None):
        super().__init__(parent)
        self.setWindowTitle("照片归集")
        self.db_manager = db_manager
        layout = QVBoxLayout(self)
        # 源目录选择控件
        src_layout = QHBoxLayout()
        self.src_label = QLabel("选择源目录:")
        src_layout.addWidget(self.src_label)
        self.src_edit = QLineEdit()
        src_layout.addWidget(self.src_edit)
        self.src_browse_btn = QPushButton("浏览...")
        self.src_browse_btn.clicked.connect(self.browse_src_dir)
        src_layout.addWidget(self.src_browse_btn)
        layout.addLayout(src_layout)

        # 目标路径显示（只读）
        self.path_label = QLabel("照片存放路径:")
        layout.addWidget(self.path_label)
        self.photo_dir = self.get_photo_dir()
        self.path_edit = QLineEdit(self.photo_dir)
        self.path_edit.setReadOnly(True)
        layout.addWidget(self.path_edit)

        # 移动/复制选项
        self.move_checkbox = QCheckBox("移动文件（否则为复制）")
        layout.addWidget(self.move_checkbox)

        # 日志显示
        self.log = []
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # 进度条
        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        # 状态标签
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        # 控制按钮
        btn_layout = QHBoxLayout()
        self.btn_collect = QPushButton("开始归集")
        self.btn_collect.clicked.connect(self.start_collect)
        btn_layout.addWidget(self.btn_collect)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.cancel_collect)
        self.btn_cancel.setEnabled(False)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # 检查目标路径有效性
        if not self.photo_dir or not os.path.isdir(self.photo_dir):
            QMessageBox.warning(self, "提示", "请先设置有效的照片存放路径！")
            self.open_settings_dialog()
            self.close()

    def browse_src_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择源目录")
        if d:
            self.src_edit.setText(d)
    
    def get_photo_dir(self):
        import json
        try:
            with open('settings.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('photo_dir', '')
        except Exception:
            return ''
    
    def open_settings_dialog(self):
        from main import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec()
    
    def append_log(self, text: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log.append(f"[{ts}] {text}")
        self.log_text.setPlainText('\n'.join(self.log))
    
    def start_collect(self):
        src = self.src_edit.text().strip()
        
        if not src or not os.path.isdir(src):
            QMessageBox.warning(self, "错误", "请先选择有效的源目录。")
            return
        
        self.btn_collect.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.log.clear()
        self.log_text.clear()
        self.progress.setValue(0)
        
        self.worker = CollectThread(src, self.photo_dir, move_files=self.move_checkbox.isChecked(), db_manager=self.db_manager)
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
        self.btn_collect.setEnabled(True)
        self.btn_cancel.setEnabled(False)
"""
照片和视频自动归集模块
包含文件收集、元数据提取和转移逻辑、线程类
"""


import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import struct
import zlib

from PIL import Image, ExifTags
from exif import Image as ExifImage
from PySide6.QtCore import QThread, Signal

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif', '.heic'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.mts'}
ALL_EXTS = IMAGE_EXTS | VIDEO_EXTS


def get_exif_datetime(path: str):
    """从图像 EXIF 数据提取拍摄时间"""
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
    """从 MP4/MOV 原子中解析创建时间（不使用外部工具）
    
    许多 MP4/MOV 文件在 'moov' 内的 'mvhd' 原子中存储创建时间。
    创建时间是自 1904-01-01 UTC 以来的秒数。
    这个解析器是轻量级的，只处理基本的原子遍历。
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
    """获取文件系统时间戳，返回最早的时间作为文件创建时间"""
    try:
        stat = os.stat(path)
        # On Windows, st_ctime is creation time; on Unix it's metadata change
        # Use creation time if available
        ctime = getattr(stat, 'st_ctime', None)
        mtime = getattr(stat, 'st_mtime', None)
        atime = getattr(stat, 'st_atime', None)

        # 获取所有时间戳并过滤掉 None
        timestamps = [t for t in [ctime, mtime, atime] if t]
        if timestamps:
            # 返回最早的时间戳
            return datetime.fromtimestamp(min(timestamps))
    except Exception:
        pass
    return None


def get_media_datetime(path: str):
    """尝试从 EXIF/元数据获取日期时间，然后回退到文件时间
    优先级：EXIF -> MP4 原子 -> 文件时间戳
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


def file_crc32(path: str):
    """计算文件的 CRC32 校验和"""
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


def collect_files(src: str, dst: str, move_files: bool = False,
                 stop_check=None, log_callback=None, progress_callback=None, stats_callback=None,
                 db_manager=None):
    """收集并整理照片和视频文件
    
    Args:
        src: 源目录
        dst: 目标根目录
        move_files: 是否移动（True）还是复制（False）
        stop_check: 可调用对象，返回 True 时停止处理
        log_callback: 日志回调函数，签名: log_callback(message)
        progress_callback: 进度回调函数，签名: progress_callback(processed, total)
        stats_callback: 统计回调函数，签名: stats_callback(total, copied_moved, skipped)
    
    Returns:
        tuple: (total_files, copied_moved, skipped)
    """
    # 默认的空回调函数
    if stop_check is None:
        stop_check = lambda: False
    if log_callback is None:
        log_callback = lambda msg: None
    if progress_callback is None:
        progress_callback = lambda p, t: None
    if stats_callback is None:
        stats_callback = lambda t, c, s: None
    
    total_files = 0
    copied_moved = 0
    skipped = 0
    
    try:
        # gather files
        files = []
        for root, dirs, filenames in os.walk(src):
            for fn in filenames:
                if Path(fn).suffix.lower() in ALL_EXTS:
                    files.append(os.path.join(root, fn))
        
        total_files = len(files)
        processed = 0
        
        log_callback(f"找到 {total_files} 个媒体文件。")
        stats_callback(total_files, copied_moved, skipped)

        for src_path in files:
            if stop_check():
                log_callback("取消操作，已停止处理。")
                break
            
            try:
                dt = get_media_datetime(src_path)
                if not dt:
                    dt = datetime.now()
                    log_callback(f"无法读取元数据，使用当前时间：{src_path}")
                
                year = dt.year
                month = dt.month
                target_dir = os.path.join(dst, str(year), f"{month:02d}")
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
                        log_callback(f"跳过（内容一致）: {src_path} -> {candidate_path}")
                        skipped += 1
                        skipped_file = True
                        break
                    # 文件名递增
                    candidate_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
                    counter += 1
                
                if not skipped_file:
                    # candidate_path 不存在或内容不同
                    if move_files:
                        shutil.move(src_path, candidate_path)
                        log_callback(f"移动: {src_path} -> {candidate_path}")
                    else:
                        shutil.copy2(src_path, candidate_path)
                        log_callback(f"复制: {src_path} -> {candidate_path}")
                    copied_moved += 1
                    # 如果提供了数据库管理器，则将新文件添加到数据库
                    try:
                        if db_manager is not None:
                            # 使用相对于相册根路径的相对路径写入数据库（若提供 album_id）
                            try:
                                # 计算 MD5 并写入数据库（以相对于相册的路径）
                                file_hash = None
                                try:
                                    # 计算绝对路径的 MD5
                                    file_hash = db_manager._calculate_md5_hash(candidate_path)
                                except Exception:
                                    file_hash = None
                                    
                                rel = os.path.relpath(candidate_path, dst)
                                rel = rel.replace('\\', os.sep)
                                # 生成缩略图
                                thumbnail = generate_thumbnail(candidate_path)
                                created_at = dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None
                                db_manager.add_file(rel, file_hash, thumbnail=thumbnail, created_at=created_at)
                                # 提取人脸并写入数据库（仅图片）
                                try:
                                    if Path(candidate_path).suffix.lower() in IMAGE_EXTS:
                                        faces = extract_faces(candidate_path, confidence_threshold=0.5)
                                        if faces:
                                            # 获取数据库中新插入/存在的记录 id
                                            rec = db_manager.get_file_by_path(rel)
                                            if rec:
                                                photo_id = rec.get('id')
                                                for f in faces:
                                                    try:
                                                        db_manager.add_face(photo_id, f['feature'], f['bbox'])
                                                        log_callback(f"添加人脸数据: photo_id={photo_id} bbox={f['bbox']}")
                                                    except Exception as e:
                                                        log_callback(f"写入人脸数据失败: {candidate_path} 错误: {e}")
                                except Exception as e:
                                    log_callback(f"提取或写入人脸数据失败: {candidate_path} 错误: {e}")
                            except Exception as e:
                                # 不阻塞主流程，但记录错误
                                log_callback(f"将文件写入数据库失败: {candidate_path} 错误: {e}")
                    except Exception as e:
                        # 不阻塞主流程，但记录错误
                        log_callback(f"将文件写入数据库失败: {candidate_path} 错误: {e}")

            except Exception as e:
                log_callback(f"处理文件失败: {src_path}  错误: {e}")

            processed += 1
            progress_callback(processed, total_files)
            stats_callback(total_files, copied_moved, skipped)

    except Exception as e:
        log_callback(f"收集文件失败: {e}")
    
    return total_files, copied_moved, skipped


class CollectThread(QThread):
    """文件收集线程"""
    progress_changed = Signal(int, int)  # processed, total
    log = Signal(str)
    error = Signal(str)
    finished_signal = Signal()
    stats_changed = Signal(int, int, int)  # total, copied_moved, skipped

    def __init__(self, src: str, dst: str, move_files: bool = False, db_manager=None):
        super().__init__()
        self.src = src
        self.dst = dst
        self.move_files = move_files
        self._stop_requested = False
        self.db_manager = db_manager

    def stop(self):
        self._stop_requested = True

    def run(self):
        try:
            total, copied_moved, skipped = collect_files(
                self.src,
                self.dst,
                self.move_files,
                stop_check=lambda: self._stop_requested,
                log_callback=self.log.emit,
                progress_callback=self.progress_changed.emit,
                stats_callback=self.stats_changed.emit,
                db_manager=self.db_manager,
            )
            self.finished_signal.emit()
        except Exception as e:
            self.error.emit(f"线程失败: {e}")
            self.finished_signal.emit()


class SyncThread(QThread):
    """后台执行同步操作的线程"""
    log = Signal(str)
    finished_signal = Signal()

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager

    def run(self):
        try:
            self.finished_signal.emit()
        except Exception as e:
            self.log.emit(f"同步线程失败: {e}")
            self.finished_signal.emit()
import numpy as np

def match_face_to_person(db_manager, face_feature, threshold=0.5):
    """返回最相似的person_id（欧氏距离或余弦相似度），无匹配则返回0"""
    persons = db_manager.get_all_persons()
    if not persons or not face_feature:
        return 0
    face_vec = np.array([float(x) for x in face_feature.split(',')])
    best_id, best_score = 0, threshold
    for p in persons:
        if not p['feature']:
            continue
        p_vec = np.array([float(x) for x in p['feature'].split(',')])
        score = np.dot(face_vec, p_vec) / (np.linalg.norm(face_vec) * np.linalg.norm(p_vec))
        if score > best_score:
            best_id, best_score = p['id'], score
    return best_id

def generate_thumbnail(image_path, size=(320, 240)):
    """
    生成缩略图数据
    :param image_path: 图片路径
    :param size: 缩略图大小，默认 320x240
    :return: 缩略图的二进制数据
    """
    with Image.open(image_path) as img:
        img.thumbnail(size)
        with io.BytesIO() as output:
            img.save(output, format="JPEG")
            return output.getvalue()

