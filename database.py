import sqlite3

class Database:
    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.connection.cursor()
        self.create_table()

    def create_table(self):
        with self.connection:
            # Создаем таблицу: user_id, role (user/model), content (текст)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT
                )
            """)

    def add_message(self, user_id, role, content):
        """Сохраняет сообщение в базу."""
        with self.connection:
            self.cursor.execute(
                "INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content)
            )
    def get_history(self, user_id, limit=40):
        """
        Получает историю и форматирует её для OpenAI.
        """
        self.cursor.execute(
            "SELECT role, content FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = self.cursor.fetchall()
        
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
        with self.connection:
            self.cursor.execute("DELETE FROM history WHERE user_id = ?", (user_id,))

    def clear_global_history(self):
        """Удаляет всю историю"""
        with self.connection:
            self.cursor.execute("DELETE FROM history")
            self.cursor.execute("VACUUM")

    def stats(self):
        """Возвращает статистику по базе"""
        with self.connection:
            user_count = self.cursor.execute("SELECT COUNT(DISTINCT user_id) FROM history").fetchone()[0]
            messages_count = self.cursor.execute("SELECT COUNT(*) FROM history").fetchone()[0]
            
            return user_count, messages_count