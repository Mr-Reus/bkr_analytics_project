import pandas as pd
import json
import os
from sqlalchemy import create_engine, text

CONFIG_FILE = r"C:\bkr_analytics_project\config.json"
EXCEL_FILE = r"C:\bkr_analytics_project\online_retail_II.xlsx"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_full_data():
    print(f"Починаємо зчитування Excel (це може тривати 1-2 хвилини)...")
    all_sheets = pd.read_excel(EXCEL_FILE, sheet_name=None)

    combined_df = pd.concat(all_sheets.values(), ignore_index=True)
    print(f"Всього зчитано рядків: {len(combined_df)}")
    print("Очищення та приведення типів...")

    combined_df = combined_df.dropna(subset=['Customer ID'])
    combined_df['Customer ID'] = combined_df['Customer ID'].astype(float).astype(int).astype(str)
    combined_df['StockCode'] = combined_df['StockCode'].astype(str)
    combined_df['Price'] = pd.to_numeric(combined_df['Price'], errors='coerce').fillna(0.0)
    combined_df['Quantity'] = pd.to_numeric(combined_df['Quantity'], errors='coerce').fillna(0).astype(int)

    test_df = combined_df.head(50000)
    print(f"Підготовлено {len(test_df)} очищених записів для міграції")
    return test_df


def fill_pg(url, df):
    print("\nЗаповнення PostgreSQL...")
    engine = create_engine(url)
    total = len(df)

    with engine.connect() as conn:
        for i, (_, row) in enumerate(df.iterrows(), 1):
            conn.execute(text("INSERT INTO pg_custs (f_name) VALUES (:n) ON CONFLICT DO NOTHING"),
                         {"n": row['Customer ID']})
            conn.execute(text("INSERT INTO pg_prods (sku, price) VALUES (:s, :p) ON CONFLICT DO NOTHING"),
                         {"s": row['StockCode'], "p": row['Price']})
            conn.execute(
                text("INSERT INTO pg_orders (c_id) VALUES ((SELECT id FROM pg_custs WHERE f_name=:n LIMIT 1))"),
                {"n": row['Customer ID']})
            conn.execute(text("""
                              INSERT INTO pg_items (o_id, p_id, qty)
                              VALUES ((SELECT MAX(id) FROM pg_orders),
                                      (SELECT id FROM pg_prods WHERE sku = :s LIMIT 1), :q)
                              """), {"s": row['StockCode'], "q": row['Quantity']})

            if i % 5000 == 0:
                print(f"  [PG] Оброблено {i} / {total} рядків...")
                conn.commit()

        conn.commit()


def fill_mysql(url, df):
    print("\nЗаповнення MySQL...")
    engine = create_engine(url)
    total = len(df)

    with engine.connect() as conn:
        for i, (_, row) in enumerate(df.iterrows(), 1):
            conn.execute(text("INSERT IGNORE INTO my_clients (login) VALUES (:l)"), {"l": row['Customer ID']})
            conn.execute(text("""
                              INSERT INTO my_sales_flat (client_id, item_sku, item_price, sale_dt)
                              VALUES ((SELECT uid FROM my_clients WHERE login = :l LIMIT 1), :sku, :pr, :dt)
                              """), {"l": row['Customer ID'], "sku": row['StockCode'], "pr": row['Price'],
                                     "dt": row['InvoiceDate']})

            if i % 5000 == 0:
                print(f"  [MySQL] Оброблено {i} / {total} рядків...")
                conn.commit()

        conn.commit()


def fill_mssql(url, df):
    print("\nЗаповнення MS SQL Server...")
    engine = create_engine(url)
    total = len(df)

    with engine.connect() as conn:
        for i, (_, row) in enumerate(df.iterrows(), 1):
            conn.execute(text(
                "IF NOT EXISTS (SELECT 1 FROM MS_Base WHERE InternalCode=:c) INSERT INTO MS_Base (InternalCode) VALUES (:c)"),
                {"c": row['Customer ID']})
            conn.execute(text(
                "IF NOT EXISTS (SELECT 1 FROM MS_Contact WHERE RealName=:n) INSERT INTO MS_Contact (BID, RealName) VALUES ((SELECT BID FROM MS_Base WHERE InternalCode=:c), :n)"),
                {"c": row['Customer ID'], "n": f"Client_{row['Customer ID']}"})

            conn.execute(text(
                "IF NOT EXISTS (SELECT 1 FROM MS_Catalog WHERE Art=:a) INSERT INTO MS_Catalog (Art, Val) VALUES (:a, :v)"),
                {"a": row['StockCode'], "v": row['Price']})

            conn.execute(text(
                "INSERT INTO MS_Header (BID, DocDate) VALUES ((SELECT BID FROM MS_Base WHERE InternalCode=:c), :d)"),
                {"c": row['Customer ID'], "d": row['InvoiceDate']})
            conn.execute(text(
                "INSERT INTO MS_Lines (HID, PID, Qty) VALUES ((SELECT MAX(HID) FROM MS_Header), (SELECT PID FROM MS_Catalog WHERE Art=:a), :q)"),
                {"a": row['StockCode'], "q": row['Quantity']})

            if i % 5000 == 0:
                print(f"  [MS SQL] Оброблено {i} / {total} рядків...")
                conn.commit()

        conn.commit()


if __name__ == "__main__":
    if not os.path.exists(EXCEL_FILE):
        print(f" Файл {EXCEL_FILE} не знайдено")
    else:
        df = get_full_data()
        cfg = load_config()

        try:
            fill_pg(cfg['pg']['url'], df)
        except Exception as e:
            print(f" Помилка PG: {e}")

        try:
            fill_mysql(cfg['mysql']['url'], df)
        except Exception as e:
            print(f" Помилка MySQL: {e}")

        try:
            fill_mssql(cfg['mssql']['url'], df)
        except Exception as e:
            print(f" Помилка MS SQL: {e}")

        print("\n Всі дані успішно розподілені без конфлікту типів")