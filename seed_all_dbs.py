import json
import os
import random
from datetime import datetime
from sqlalchemy import create_engine, text

CONFIG_FILE = r"C:\bkr_analytics_project\config.json"


def load_local_config():
    if not os.path.exists(CONFIG_FILE):
        print(f" Помилка: Файл {CONFIG_FILE} не знайдено за шляхом {CONFIG_FILE}!")
        return None
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_id_type(db_key):
    if db_key == "pg": return "SERIAL PRIMARY KEY"
    if db_key == "mysql": return "INT AUTO_INCREMENT PRIMARY KEY"
    if db_key == "mssql": return "INT IDENTITY(1,1) PRIMARY KEY"
    return "INT PRIMARY KEY"

def seed_postgresql(url):
    print("\n--- Наповнення PostgreSQL (стандарт: 4 таблиці) ---")
    engine = create_engine(url)
    with engine.connect() as conn:
        for table in ["pg_items", "pg_orders", "pg_prods", "pg_custs"]:
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))

        conn.execute(text(f"CREATE TABLE pg_custs (id {get_id_type('pg')}, f_name TEXT, email TEXT)"))
        conn.execute(text(f"CREATE TABLE pg_prods (id {get_id_type('pg')}, sku TEXT, price NUMERIC)"))
        conn.execute(text(
            f"CREATE TABLE pg_orders (id {get_id_type('pg')}, c_id INT, d_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
        conn.execute(text(f"CREATE TABLE pg_items (id {get_id_type('pg')}, o_id INT, p_id INT, qty INT)"))

        conn.execute(text("INSERT INTO pg_custs (f_name, email) VALUES ('Олександр Постгрес', 'alex@pg.com')"))
        conn.execute(text("INSERT INTO pg_prods (sku, price) VALUES ('SKU-100', 120.50), ('SKU-200', 80.00)"))
        conn.execute(text("INSERT INTO pg_orders (c_id) VALUES (1)"))
        conn.execute(text("INSERT INTO pg_items (o_id, p_id, qty) VALUES (1, 1, 3), (1, 2, 1)"))
        conn.commit()
    print(" PostgreSQL готово")


def seed_mysql(url):
    print("\n---  Наповнення MySQL (спрощено: 2 таблиці) ---")
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        conn.execute(text("DROP TABLE IF EXISTS my_sales_flat"))
        conn.execute(text("DROP TABLE IF EXISTS my_clients"))

        conn.execute(text(f"CREATE TABLE my_clients (uid {get_id_type('mysql')}, login VARCHAR(100))"))
        conn.execute(text(
            f"CREATE TABLE my_sales_flat (sid {get_id_type('mysql')}, client_id INT, item_sku VARCHAR(50), item_price DECIMAL(10,2), sale_dt DATETIME)"))

        conn.execute(text("INSERT INTO my_clients (login) VALUES ('dmytro_mysql')"))
        for i in range(5):
            conn.execute(
                text("INSERT INTO my_sales_flat (client_id, item_sku, item_price, sale_dt) VALUES (1, :sku, :pr, :dt)"),
                {"sku": f"M-SKU-{i}", "pr": random.randint(50, 500), "dt": datetime.now()})
        conn.commit()
    print(" MySQL готово")

def seed_mssql(url):
    print("\n---  Наповнення MS SQL (складно: 5 таблиць) ---")
    engine = create_engine(url)
    with engine.connect() as conn:
        for t_name in ["MS_Lines", "MS_Header", "MS_Catalog", "MS_Contact", "MS_Base"]:
            try:
                conn.execute(text(f"IF OBJECT_ID('{t_name}', 'U') IS NOT NULL DROP TABLE {t_name}"))
            except:
                pass

        conn.execute(text("CREATE TABLE MS_Base (BID INT IDENTITY PRIMARY KEY, InternalCode NVARCHAR(50))"))
        conn.execute(text("CREATE TABLE MS_Contact (CID INT IDENTITY PRIMARY KEY, BID INT, RealName NVARCHAR(100))"))
        conn.execute(text("CREATE TABLE MS_Catalog (PID INT IDENTITY PRIMARY KEY, Art NVARCHAR(50), Val MONEY)"))
        conn.execute(text("CREATE TABLE MS_Header (HID INT IDENTITY PRIMARY KEY, BID INT, DocDate DATETIME)"))
        conn.execute(text("CREATE TABLE MS_Lines (LID INT IDENTITY PRIMARY KEY, HID INT, PID INT, Qty INT)"))

        conn.execute(text("INSERT INTO MS_Base (InternalCode) VALUES ('C-999')"))
        conn.execute(text("INSERT INTO MS_Contact (BID, RealName) VALUES (1, N'Степан Майкрософт')"))
        conn.execute(text("INSERT INTO MS_Catalog (Art, Val) VALUES ('WIN-PRO', 4500)"))
        conn.execute(text("INSERT INTO MS_Header (BID, DocDate) VALUES (1, GETDATE())"))
        conn.execute(text("INSERT INTO MS_Lines (HID, PID, Qty) VALUES (1, 1, 1)"))
        conn.commit()
    print("MS SQL Server готово")


if __name__ == "__main__":
    configs = load_local_config()
    if configs:
        try:
            seed_postgresql(configs['pg']['url'])
        except Exception as e:
            print(f"Помилка PG: {e}")

        try:
            seed_mysql(configs['mysql']['url'])
        except Exception as e:
            print(f"Помилка MySQL: {e}")

        try:
            seed_mssql(configs['mssql']['url'])
        except Exception as e:
            print(f"Помилка MS SQL: {e}")

        print("\nТестове середовище підготовлено")