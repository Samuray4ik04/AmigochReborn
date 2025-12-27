import sqlite3
import threading

class Database:
    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file, check_same_thread=False)
        self._lock = threading.Lock()
        self.create_table()

    def create_table(self):
        with self._lock, self.connection:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS blacklist (
                    user_id INTEGER PRIMARY KEY
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY
                )
                """
            )

    def add_message(self, user_id, role, content):
        """Сохраняет сообщение в базу."""
        with self._lock, self.connection:
            cursor = self.connection.cursor()
            cursor.execute(
                "INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content)
            )
    def get_history(self, user_id, limit=40):
        """
        Получает историю и форматирует её для OpenAI.
        """
        with self._lock:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT role, content FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            )
            rows = cursor.fetchall()
        
        messages = []
        for row in reversed(rows):
            # Формат OpenAI - просто {'role': ROLE, 'content': CONTENT}
            messages.append({
                "role": row[0],
                "content": row[1] 
            })
        return messages

    # ... (метод clear_history, get_stats и т.д.)
    def clear_history(self, user_id):
        """Очистка истории пользователя."""
        with self._lock, self.connection:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM history WHERE user_id = ?", (user_id,))

    def clear_global_history(self):
        """Удаляет всю историю"""
        with self._lock, self.connection:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM history")
            cursor.execute("VACUUM")

    def stats(self):
        """Возвращает статистику по базе"""
        with self._lock:
            cursor = self.connection.cursor()
            user_count = cursor.execute("SELECT COUNT(DISTINCT user_id) FROM history").fetchone()[0]
            messages_count = cursor.execute("SELECT COUNT(*) FROM history").fetchone()[0]
            return user_count, messages_count
        
    def add_blacklist(self, user_id: int):
        """Добавить пользователя в ЧС"""
        with self._lock:
            cursor = self.connection.cursor()
            cursor.execute("INSERT OR IGNORE INTO blacklist (user_id) VALUES (?)", (user_id,))
            self.connection.commit()

    def remove_blacklist(self, user_id: int):
        """Убрать пользователя из ЧС"""
        with self._lock:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
            self.connection.commit()

    def is_blacklisted(self, user_id: int) -> bool:
        """Проверить, забанен ли пользователь (True/False)"""
        with self._lock:
            cursor = self.connection.cursor()
            res = cursor.execute("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,)).fetchone()
            return bool(res)

    def add_admin(self, user_id: int) -> None:
        """Добавить администратора"""
        with self._lock:
            cursor = self.connection.cursor()
            cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
            self.connection.commit()

    def remove_admin(self, user_id: int) -> None:
        """Удалить администратора"""
        with self._lock:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            self.connection.commit()

    def get_admins(self) -> list[int]:
        """Список администраторов"""
        with self._lock:
            cursor = self.connection.cursor()
            rows = cursor.execute("SELECT user_id FROM admins").fetchall()
            return [row[0] for row in rows]

    def is_admin(self, user_id: int) -> bool:
        """Проверить, админ ли пользователь"""
        with self._lock:
            cursor = self.connection.cursor()
            res = cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)).fetchone()
            return bool(res)
