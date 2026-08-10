import psycopg2
from config import DATABASE_URL

try:
    conn = psycopg2.connect(DATABASE_URL)
    print("Подключение к PostgreSQL успешно")
    conn.close()
except Exception as e:
    print(f"Ошибка: {e}")