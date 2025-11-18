"""
数据库管理模块
使用 SQLite 管理相册和文件列表
"""
import sqlite3
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class DatabaseManager:
    """SQLite 数据库管理类"""

    def __init__(self, db_file: str = "data.db"):
        self.db_file = db_file
        self._init_db()

    def _init_db(self):
        """初始化数据库和表"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            # 启用外键约束
            cursor.execute("PRAGMA foreign_keys = ON")
            # 创建文件表（无 album_id，增加 tags 字段）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP,
                    is_deleted INTEGER DEFAULT 0,
                    thumbnail BLOB,
                    tags TEXT DEFAULT ''
                )
            """)
            # 创建人脸表（无 album 关联字段）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS faces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    photo_id INTEGER NOT NULL,
                    feature TEXT NOT NULL,
                    bbox TEXT NOT NULL,
                    person_id INTEGER DEFAULT 0,
                    is_deleted INTEGER DEFAULT 0
                )
            """)
            # 创建人员表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    feature TEXT
                )
            """)
            conn.commit()
        except Exception as e:
            print(f"数据库初始化失败: {e}")

    # ===== 人脸数据管理 =====
    def add_face(self, photo_id: int, feature: str, bbox: str, person_id: int = 0) -> bool:
        """添加人脸数据"""
        return self._execute(
            "INSERT INTO faces (photo_id, feature, bbox, person_id) VALUES (?, ?, ?, ?)",
            (photo_id, feature, bbox, person_id)
        )

    def get_faces_by_photo(self, photo_id: int):
        """获取某张照片的所有人脸数据。默认不包含已删除记录。"""
        results = self._fetch_all(
            "SELECT id, feature, bbox, person_id, is_deleted FROM faces WHERE photo_id = ? AND is_deleted = 0",
            (photo_id,)
        )
        return [
            {"id": row[0], "feature": row[1], "bbox": row[2], "person_id": row[3], "is_deleted": row[4]}
            for row in results
        ]

    def get_faces_by_person(self, person_id: int):
        """获取某个人的所有人脸数据。默认不包含已删除记录。"""
        results = self._fetch_all(
            "SELECT id, photo_id, feature, bbox, is_deleted FROM faces WHERE person_id = ? AND is_deleted = 0",
            (person_id,)
        )
        return [
            {"id": row[0], "photo_id": row[1], "feature": row[2], "bbox": row[3], "is_deleted": row[4]}
            for row in results
        ]

    # ===== 人员数据管理 =====
    def add_person(self, name: str, feature: str) -> bool:
        """添加新人员"""
        return self._execute(
            "INSERT INTO persons (name, feature) VALUES (?, ?)",
            (name, feature)
        )

    def get_person(self, person_id: int) -> Optional[Dict]:
        """获取人员信息"""
        result = self._fetch_one(
            "SELECT id, name, feature, created_at, updated_at FROM persons WHERE id = ?",
            (person_id,)
        )
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'feature': result[2],
                'created_at': result[3],
                'updated_at': result[4]
            }
        return None

    def get_person_by_name(self, name: str) -> Optional[Dict]:
        """通过姓名获取人员信息"""
        result = self._fetch_one(
            "SELECT id, name, feature, created_at, updated_at FROM persons WHERE name = ?",
            (name,)
        )
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'feature': result[2],
                'created_at': result[3],
                'updated_at': result[4]
            }
        return None

    def get_all_persons(self) -> List[Dict]:
        """获取所有人员"""
        results = self._fetch_all(
            "SELECT id, name, feature FROM persons ORDER BY id"
        )
        return [
            {
                'id': row[0],
                'name': row[1],
                'feature': row[2]
            }
            for row in results
        ]

    def update_person(self, person_id: int, name: str = None, feature: str = None) -> bool:
        """更新人员信息（name 和 feature 可选更新）"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            if name is not None and feature is not None:
                cursor.execute(
                    "UPDATE persons SET name = ?, feature = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (name, feature, person_id)
                )
            elif name is not None:
                cursor.execute(
                    "UPDATE persons SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (name, person_id)
                )
            elif feature is not None:
                cursor.execute(
                    "UPDATE persons SET feature = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (feature, person_id)
                )
            else:
                return False
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新人员信息失败: {e}")
            return False

    def delete_person(self, person_id: int) -> bool:
        """删除人员信息，同时将相关 faces 的 person_id 重置为 0（未识别）"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            # 启用外键约束以确保数据一致性
            cursor.execute("PRAGMA foreign_keys = ON")
            # 先将所有指向此人员的人脸记录的 person_id 重置为 0
            cursor.execute("UPDATE faces SET person_id = 0 WHERE person_id = ?", (person_id,))
            # 再删除人员记录
            cursor.execute("DELETE FROM persons WHERE id = ?", (person_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"删除人员失败: {e}")
            return False

    def _execute(self, query: str, params: Tuple = ()):
        """执行数据库查询（内部方法）"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"执行查询失败: {e}")
            return False

    def _fetch_one(self, query: str, params: Tuple = ()):
        """获取单行数据"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(query, params)
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            print(f"{query} 查询失败: {e}")
            return None

    def _fetch_all(self, query: str, params: Tuple = ()):
        """获取所有数据"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            return results
        except Exception as e:
            print(f"{query} 查询失败: {e}")
            return []

    # ===== 文件列表管理 =====
    @staticmethod
    def _calculate_md5_hash(file_path: str, chunk_size: int = 8192) -> str:
        """计算文件的 MD5 哈希值（前32字节）"""
        try:
            hash_obj = hashlib.md5()
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    hash_obj.update(data)
            return hash_obj.hexdigest()
        except Exception:
            return ""

    def add_file(self, file_path: str, file_hash: Optional[str] = None, thumbnail: Optional[bytes] = None, created_at: Optional[str] = None) -> bool:
        """添加文件到列表。
        支持 created_at 字段。
        """
        if not file_hash:
            # 尝试直接对 file_path 计算哈希（file_path 可能为绝对或相对路径）
            if os.path.isabs(file_path):
                file_hash = self._calculate_md5_hash(file_path)
            else:
                file_hash = None
        if not file_hash:
            return False
        return self._execute(
            "INSERT OR IGNORE INTO files (file_hash, file_path, is_deleted, thumbnail, created_at) VALUES (?, ?, 0, ?, ?)",
            (file_hash, file_path, thumbnail, created_at)
        )

    def remove_file(self, file_id: int) -> bool:
        """标记文件为已删除（软删除）。默认同时软删除对应的 faces 数据。"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("UPDATE files SET is_deleted = 1 WHERE id = ?", (file_id,))
            # 同时软删除人脸数据
            cursor.execute("UPDATE faces SET is_deleted = 1 WHERE photo_id = ?", (file_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"软删除失败: {e}")
            return False

    def restore_file(self, file_id: int) -> bool:
        """将软删除的文件恢复。默认同时恢复对应的 faces 数据。"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("UPDATE files SET is_deleted = 0 WHERE id = ?", (file_id,))
            cursor.execute("UPDATE faces SET is_deleted = 0 WHERE photo_id = ?", (file_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"恢复失败: {e}")
            return False

    def delete_file_permanently(self, file_id: int) -> bool:
        """永久删除文件记录，同时删除该照片对应的人脸记录"""
        try:
            # 删除 faces 中关联的记录
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM faces WHERE photo_id = ?", (file_id,))
            cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"删除记录失败: {e}")
            return False

    def get_file_by_hash(self, file_hash: str) -> Optional[Dict]:
        result = self._fetch_one(
            "SELECT id, file_hash, file_path, added_at, created_at, is_deleted FROM files WHERE file_hash = ?",
            (file_hash,)
        )
        if result:
            return {
                'id': result[0],
                'file_hash': result[1],
                'file_path': result[2],
                'added_at': result[3],
                'created_at': result[4],
                'is_deleted': result[5]
            }
        return None

    def get_file_by_path(self, file_path: str) -> Optional[Dict]:
        result = self._fetch_one(
            "SELECT id, file_hash, file_path, added_at, created_at, is_deleted FROM files WHERE file_path = ?",
            (file_path,)
        )
        if result:
            return {
                'id': result[0],
                'file_hash': result[1],
                'file_path': result[2],
                'added_at': result[3],
                'created_at': result[4],
                'is_deleted': result[5]
            }
        return None

    def get_file_by_id(self, file_id: int) -> Optional[Dict]:
        result = self._fetch_one(
            "SELECT id, file_hash, file_path, added_at, created_at, is_deleted FROM files WHERE id = ?",
            (file_id,)
        )
        if result:
            return {
                'id': result[0],
                'file_hash': result[1],
                'file_path': result[2],
                'added_at': result[3],
                'created_at': result[4],
                'is_deleted': result[5]
            }
        return None

    def get_all_files(self, include_deleted: bool = False, created_after=None, created_before=None, tags=None, person_ids=None) -> List[Dict]:
        """获取所有文件记录。
        :param include_deleted: 是否包含已删除的文件
        :param created_after: 创建时间筛选（大于等于），datetime 对象
        :param created_before: 创建时间筛选（小于），datetime 对象
        :param tags: 标签列表筛选（任一标签匹配）
        :param person_ids: 人员 ID 列表筛选（需要照片包含该人员的人脸）
        """
        # 构建查询条件
        conditions = []
        params = []
        
        if not include_deleted:
            conditions.append("is_deleted = 0")
        
        # 时间筛选
        if created_after:
            conditions.append("created_at >= ?")
            params.append(created_after.strftime('%Y-%m-%d %H:%M:%S'))
        
        if created_before:
            conditions.append("created_at < ?")
            params.append(created_before.strftime('%Y-%m-%d %H:%M:%S'))
        
        # 标签筛选（简单实现：检查 tags 字段是否包含任一标签）
        if tags:
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f'%{tag}%')
            conditions.append(f"({' OR '.join(tag_conditions)})")
        
        # 构建基础查询
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 如果有 person_ids 筛选，需要 JOIN faces 表
        if person_ids:
            query = f"""
                SELECT DISTINCT f.id, f.file_hash, f.file_path, f.added_at, f.created_at, f.is_deleted
                FROM files f
                INNER JOIN faces fc ON f.id = fc.photo_id
                WHERE {where_clause} AND fc.person_id IN ({','.join('?' * len(person_ids))}) AND fc.is_deleted = 0
                ORDER BY f.added_at
            """
            params.extend(person_ids)
        else:
            query = f"""
                SELECT id, file_hash, file_path, added_at, created_at, is_deleted
                FROM files
                WHERE {where_clause}
                ORDER BY added_at
            """
        
        results = self._fetch_all(query, tuple(params))
        files = []
        for row in results:
            files.append({
                'id': row[0],
                'file_hash': row[1],
                'file_path': row[2],
                'added_at': row[3],
                'created_at': row[4],
                'is_deleted': row[5]
            })
        return files

    def check_file_exists(self, file_path: str) -> bool:
        """检查文件是否已在数据库中（未删除）"""
        result = self._fetch_one(
            "SELECT id FROM files WHERE file_path = ? AND is_deleted = 0",
            (file_path,)
        )
        return result is not None

    def check_hash_exists(self, file_hash: str) -> bool:
        """检查文件哈希是否已存在（未删除）"""
        result = self._fetch_one(
            "SELECT id FROM files WHERE file_hash = ? AND is_deleted = 0",
            (file_hash,)
        )
        return result is not None

    def get_all_photos(self):
        """
        获取所有照片元信息（不包含缩略图，避免一次性占用大量内存）。
        :return: List[Dict] 每个字典包含 id 和 file_path。
        """
        rows = self._fetch_all("SELECT id, file_path FROM files WHERE is_deleted = 0")
        return [{"id": row[0], "file_path": row[1]} for row in rows]

    def update_file_thumbnail(self, file_path: str, thumbnail: bytes):
        """
        更新指定文件的缩略图数据。
        :param file_path: 文件的相对路径
        :param thumbnail: 缩略图二进制数据
        """
        self._execute(
            "UPDATE files SET thumbnail = ? WHERE file_path = ?",
            (thumbnail, file_path)
        )

    def get_thumbnail(self, file_id: int):
        """根据文件 id 返回缩略图二进制数据（或 None）。"""
        result = self._fetch_one("SELECT thumbnail FROM files WHERE id = ?", (file_id,))
        if result:
            return result[0]
        return None
