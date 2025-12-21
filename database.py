import sqlite3
import threading

class Database:
    def __init__(self, db_file: str):
        self.connection = sqlite3.connect(db_file, check_same_thread=False)
        self.lock = threading.Lock()
        self.create_table()

    def create_table(self):
        with self.lock:
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT
                )
            """)

            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    user_id INTEGER PRIMARY KEY
                )
            """)
            self.connection.commit()
    
    def add_message(self, user_id, role, content):
        """Сохраняет сообщение в базу с блокировкой потока."""
        with self.lock:
            try:
                self.connection.execute(
                    "INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)",
                    (user_id, role, content)
                )
                self.connection.commit()
            except sqlite3.Error:
                self.connection.rollback()
                raise

    def get_history(self, user_id, limit=40):
        """
        Получает историю и форматирует её для OpenAI.
        Возвращает список {'role': ..., 'content': ...} в хронологическом порядке.
        """
        with self.lock:
            cursor = self.connection.execute(
                "SELECT role, content FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            )
            rows = cursor.fetchall()
        
        messages = []
        for row in reversed(rows):
            messages.append({
                "role": row[0],
                "content": row[1] 
            })
        return messages

    def clear_history(self, user_id):
        """Очистка истории пользователя."""
        with self.lock:
            self.connection.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
            self.connection.commit()

    def clear_global_history(self):
        """Удаляет всю историю"""
        with self.lock:
            self.connection.execute("DELETE FROM history")
            self.connection.execute("VACUUM")
            self.connection.commit()

    def stats(self):
        """Возвращает статистику по базе"""
        with self.lock:
            cursor = self.connection.cursor()
            user_count = cursor.execute("SELECT COUNT(DISTINCT user_id) FROM history").fetchone()[0]
            messages_count = cursor.execute("SELECT COUNT(*) FROM history").fetchone()[0]
            return user_count, messages_count
        
    def add_blacklist(self, user_id: int):
        """Добавить пользователя в ЧС"""
        with self.lock:
            self.connection.execute("INSERT OR IGNORE INTO blacklist (user_id) VALUES (?)", (user_id,))
            self.connection.commit()

    def remove_blacklist(self, user_id: int) -> None:
        """Убрать пользователя из ЧС"""
        with self.lock:
            self.connection.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
            self.connection.commit()

    def is_blacklisted(self, user_id: int) -> bool:
        """Проверить, забанен ли пользователь (True/False)"""
        with self.lock:
            res = self.connection.execute("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,)).fetchone()
            return bool(res)

    def __del__(self):
        self.connection.close()
