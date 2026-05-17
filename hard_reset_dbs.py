import json
import os
from sqlalchemy import create_engine, text

CONFIG_FILE = r"C:\bkr_analytics_project\config.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f" Помилка: {CONFIG_FILE} не знайдено")
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f" Помилка читання JSON: {e}")
        return None


def wipe_database(db_key, url):
    print(f"\n---  ПОВНЕ ОЧИЩЕННЯ {db_key.upper()} ---")
    try:
        engine = create_engine(url, pool_pre_ping=True)

        with engine.connect() as conn:
            if db_key == "mysql":
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            elif db_key == "mssql":
                pass

            if db_key == "pg":
                query = "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public';"
            elif db_key == "mysql":
                query = "SHOW TABLES;"
            elif db_key == "mssql":
                query = "SELECT name FROM sys.tables;"
            else:
                return

            result = conn.execute(text(query))
            tables = [row[0] for row in result]

            if not tables:
                print(f"  [i] База {db_key} вже порожня (немає таблиць)")
                return

            print(f"  Знайдено таблиць для видалення: {len(tables)}")

            for table in tables:
                try:
                    if db_key == "pg":
                        conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE;'))
                    elif db_key == "mssql":
                        conn.execute(text(f"DROP TABLE [{table}];"))
                    else:
                        conn.execute(text(f"DROP TABLE IF EXISTS `{table}`;"))
                    print(f"  [OK] Видалено: {table}")
                except Exception as e:
                    print(f"  [!] Помилка видалення {table}: {e}")

            if db_key == "mysql":
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

            conn.commit()
        print(f" {db_key.upper()} повністю очищена (всі таблиці видалено)")

    except Exception as e:
        print(f" Не вдалося підключитися до {db_key}: {e}")


if __name__ == "__main__":
    configs = load_config()
    if configs:
        print(" Увага. Цей скрипт видалить ВСІ таблиці у PostgreSQL, MySQL та MS SQL")
        print("Це необхідно для 'чистого' завантаження даних з Excel")
        confirm = input("\nВи впевнені? (наберіть 'WIPE' для підтвердження): ")

        if confirm == "WIPE":
            for db_key in ["pg", "mysql", "mssql"]:
                if db_key in configs:
                    wipe_database(db_key, configs[db_key]['url'])

            print("\n Чистий аркуш створено. Тепер бази порожні")
        else:
            print(" Очищення скасовано")