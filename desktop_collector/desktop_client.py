import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import hashlib
import psutil
import os
import threading
import time
import json
from sqlalchemy import create_engine, text

COLOR_BG = "#F0F2F5"
COLOR_PRIMARY = "#0078D4"  # синій (первинне завантаження)
COLOR_SECONDARY = "#2B88D8"  # світло-синій (дельта)
COLOR_SUCCESS = "#107C10"
COLOR_ERROR = "#A4262C"
COLOR_TEXT = "#333333"
COLOR_BORDER = "#D1D1D1"

CONFIG_FILE = r"C:\bkr_analytics_project\config.json"


class BKRLocalCollector:
    def __init__(self, root):
        self.root = root
        self.root.title("BKR Analytics | Data Prep & ETL Collector")
        self.root.geometry("950x850")
        self.root.configure(bg=COLOR_BG)

        self.cloud_url = "https://bkr-analytics-api.onrender.com"
        self.load_configuration()
        self.setup_ui()

    def load_configuration(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.db_configs = json.load(f)
            except:
                messagebox.showerror("Помилка", "Файл config.json пошкоджений")
                self.db_configs = self.get_default_skeleton()
        else:
            self.db_configs = self.get_default_skeleton()
            self.save_configuration()

    def get_default_skeleton(self):
        return {
            "pg": {"url": "", "query": ""},
            "mysql": {"url": "", "query": ""},
            "mssql": {"url": "", "query": ""}
        }

    def save_configuration(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.db_configs, f, indent=4)

    def setup_ui(self):
        # Шапка
        header = tk.Frame(self.root, bg=COLOR_PRIMARY, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="BKR ETL | DATA PREPARATION (CRISP-DM)",
                 bg=COLOR_PRIMARY, fg="white", font=("Segoe UI", 13, "bold")).pack(side="left", padx=30, pady=20)

        main_container = tk.Frame(self.root, bg=COLOR_BG)
        main_container.pack(fill="both", expand=True, padx=40, pady=25)

        style = ttk.Style()
        style.configure("TLabelframe", background=COLOR_BG)
        style.configure("TLabelframe.Label", font=("Segoe UI Semibold", 10), background=COLOR_BG, foreground=COLOR_TEXT)

        auth_frame = ttk.LabelFrame(main_container, text=" Параметри підключення ")
        auth_frame.pack(fill="x", pady=(0, 20), ipady=5)

        f1 = tk.Frame(auth_frame, bg=COLOR_BG)
        f1.pack(fill="x", padx=20, pady=15)

        tk.Label(f1, text="Tenant Key:", bg=COLOR_BG, font=("Segoe UI", 10)).pack(side="left")
        self.key_entry = tk.Entry(f1, width=32, font=("Consolas", 10), relief="solid", bd=1)
        self.key_entry.pack(side="left", padx=(10, 25), ipady=4)

        tk.Label(f1, text="Джерело:", bg=COLOR_BG, font=("Segoe UI", 10)).pack(side="left")
        self.db_selector = ttk.Combobox(f1, values=["PostgreSQL", "MySQL", "MS SQL Server"], state="readonly", width=18,
                                        font=("Segoe UI", 10))
        self.db_selector.current(0)
        self.db_selector.pack(side="left", padx=(10, 25))

        self.btn_verify = tk.Button(f1, text="Верифікувати", bg=COLOR_SUCCESS, fg="white",
                                    font=("Segoe UI Bold", 10), relief="flat", padx=15, pady=4, cursor="hand2",
                                    command=self.verify_all)
        self.btn_verify.pack(side="left", padx=5)

        self.btn_settings = tk.Button(f1, text=" Налаштування", bg="#555555", fg="white",
                                      font=("Segoe UI Bold", 10), relief="flat", padx=15, pady=4, cursor="hand2",
                                      command=self.open_settings)
        self.btn_settings.pack(side="left", padx=5)

        status_frame = tk.Frame(main_container, bg="white", highlightbackground=COLOR_BORDER, highlightthickness=1)
        status_frame.pack(fill="x", pady=(0, 25))

        p = tk.Frame(status_frame, bg="white")
        p.pack(padx=20, pady=12, anchor="w")

        font_st = ("Segoe UI Semibold", 10)
        self.st_cloud = tk.Label(p, text=" Cloud API: --", bg="white", font=font_st, fg="#666666")
        self.st_cloud.pack(side="left", padx=(0, 40))
        self.st_pg = tk.Label(p, text=" Postgres: --", bg="white", font=font_st, fg="#666666")
        self.st_pg.pack(side="left", padx=40)
        self.st_my = tk.Label(p, text=" MySQL: --", bg="white", font=font_st, fg="#666666")
        self.st_my.pack(side="left", padx=40)
        self.st_ms = tk.Label(p, text=" MS SQL: --", bg="white", font=font_st, fg="#666666")
        self.st_ms.pack(side="left", padx=40)

        ctrl = tk.Frame(main_container, bg=COLOR_BG)
        ctrl.pack(fill="x", pady=(0, 15))

        self.btn_initial = tk.Button(ctrl, text=" Первинне завантаження", bg=COLOR_PRIMARY, fg="white",
                                     font=("Segoe UI Bold", 11), relief="flat", padx=20, pady=8, cursor="hand2",
                                     command=lambda: self.start_sync("initial"))
        self.btn_initial.pack(side="left", padx=(0, 10))

        self.btn_delta = tk.Button(ctrl, text=" Дельта-завантаження", bg=COLOR_SECONDARY, fg="white",
                                   font=("Segoe UI Bold", 11), relief="flat", padx=20, pady=8, cursor="hand2",
                                   command=lambda: self.start_sync("delta"))
        self.btn_delta.pack(side="left")

        ram_frame = tk.Frame(ctrl, bg="#E1F1FF", highlightbackground=COLOR_PRIMARY, highlightthickness=1)
        ram_frame.pack(side="right")
        self.ram_label = tk.Label(ram_frame, text="RAM: 0.00 MB", bg="#E1F1FF", fg=COLOR_PRIMARY,
                                  font=("Consolas", 11, "bold"), padx=15, pady=6)
        self.ram_label.pack()

        tk.Label(main_container, text="Журнал ETL-процесів:", bg=COLOR_BG, font=("Segoe UI Semibold", 10),
                 fg=COLOR_TEXT).pack(anchor="w", pady=(5, 5))

        self.log_area = scrolledtext.ScrolledText(main_container, height=15, bg="white", fg="#222222",
                                                  font=("Consolas", 10),
                                                  relief="flat", highlightbackground=COLOR_BORDER, highlightthickness=1)
        self.log_area.pack(fill="both", expand=True, pady=(0, 15))

        self.progress = ttk.Progressbar(main_container, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=(0, 10))

    def open_settings(self):
        set_win = tk.Toplevel(self.root)
        set_win.title(" Налаштування підключень")
        set_win.geometry("800x600")
        set_win.configure(bg=COLOR_BG)
        set_win.transient(self.root)

        notebook = ttk.Notebook(set_win)
        notebook.pack(fill="both", expand=True, padx=20, pady=20)

        self.settings_entries = {}
        db_map = [("pg", "PostgreSQL"), ("mysql", "MySQL"), ("mssql", "MS SQL Server")]

        for db_key, db_name in db_map:
            frame = tk.Frame(notebook, bg="white")
            notebook.add(frame, text=f"  {db_name}  ")

            tk.Label(frame, text="URL підключення:", bg="white", font=("Segoe UI Semibold", 10)).pack(anchor="w",
                                                                                                      padx=20,
                                                                                                      pady=(20, 5))
            url_entry = tk.Entry(frame, width=90, font=("Consolas", 10), relief="solid", bd=1)
            url_entry.insert(0, self.db_configs.get(db_key, {}).get("url", ""))
            url_entry.pack(padx=20, pady=5, ipady=4)

            tk.Label(frame, text="SQL Запит (потрібно AS transaction_date):", bg="white",
                     font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=20, pady=(20, 5))
            query_text = tk.Text(frame, height=12, width=90, font=("Consolas", 10), relief="solid", bd=1)
            query_text.insert("1.0", self.db_configs.get(db_key, {}).get("query", ""))
            query_text.pack(padx=20, pady=5)

            self.settings_entries[db_key] = {"url": url_entry, "query": query_text}

        btn_frame = tk.Frame(set_win, bg=COLOR_BG)
        btn_frame.pack(fill="x", pady=15)
        tk.Button(btn_frame, text=" Зберегти налаштування", bg=COLOR_PRIMARY, fg="white", font=("Segoe UI Bold", 11),
                  relief="flat", padx=30, pady=8, cursor="hand2",
                  command=lambda: self.save_settings_action(set_win)).pack()

    def save_settings_action(self, window):
        for db_key in ["pg", "mysql", "mssql"]:
            self.db_configs[db_key]["url"] = self.settings_entries[db_key]["url"].get()
            self.db_configs[db_key]["query"] = self.settings_entries[db_key]["query"].get("1.0", tk.END).strip()
        self.save_configuration()
        self.log("Налаштування успішно збережено", "Success")
        window.destroy()

    def log(self, message, status="INFO"):
        self.log_area.configure(state='normal')
        ts = time.strftime("%H:%M:%S")
        symbol = "✅" if status == "Success" else "❌" if status == "Error" else "⚠️" if status == "Warning" else "ℹ️"
        self.log_area.insert(tk.END, f"[{ts}] {symbol} {message}\n")
        self.log_area.configure(state='disabled')
        self.log_area.see(tk.END)
        self.root.update()

    def update_ram(self):
        mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        self.ram_label.config(text=f"RAM: {mem:.2f} MB")

    def verify_all(self):
        self.log("Діагностика вузлів мережі...", "INFO")
        key = self.key_entry.get().strip()

        try:
            res = requests.get(f"{self.cloud_url}/verify-me", headers={"X-Tenant-Key": key}, timeout=5)
            if res.status_code == 200:
                self.st_cloud.config(text="☁️ Cloud API: ", fg=COLOR_SUCCESS)
            else:
                self.st_cloud.config(text="☁️ Cloud API: ", fg="orange")
        except:
            self.st_cloud.config(text="☁️ Cloud API:", fg=COLOR_ERROR)

        db_checks = [("pg", self.st_pg, " Postgres"),
                     ("mysql", self.st_my, " MySQL"),
                     ("mssql", self.st_ms, " MS SQL")]

        for k, label, prefix in db_checks:
            try:
                engine = create_engine(self.db_configs[k]["url"])
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                label.config(text=f"{prefix}: ✅", fg=COLOR_SUCCESS)
            except:
                label.config(text=f"{prefix}: ❌", fg=COLOR_ERROR)

        self.log("Діагностику завершено.", "Success")

    def start_sync(self, mode):
        threading.Thread(target=self.run_etl, args=(mode,), daemon=True).start()

    def clean_and_transform_record(self, row):
        try:
            if row[0] is None or row[1] is None or row[3] is None: return None
            client_raw = str(row[0]).strip()
            sku = str(row[1]).strip()
            qty = int(row[2])
            price = float(row[3])
            dt = str(row[4])
            if not client_raw or not sku or price <= 0 or qty <= 0: return None
            hashed_id = hashlib.sha256(client_raw.encode()).hexdigest()
            return {"client_hash": hashed_id, "product_code": sku, "quantity": qty, "price": price, "order_date": dt}
        except:
            return None

    def run_etl(self, mode):
        self.btn_initial.config(state="disabled", bg="#A0A0A0")
        self.btn_delta.config(state="disabled", bg="#A0A0A0")

        self.progress['value'] = 0
        start_time = time.time()

        mode_name = "Первинне завантаження" if mode == "initial" else "Дельта-завантаження"
        self.log(f"Ініціалізація конвеєра: {mode_name}", "INFO")

        sel_name = self.db_selector.get()
        db_key = "pg" if "Postgre" in sel_name else "mysql" if "MySQL" in sel_name else "mssql"
        meta = self.db_configs[db_key]
        tenant_key = self.key_entry.get().strip()
        headers = {"X-Tenant-Key": tenant_key}

        MAIN_LIMIT = 25000

        try:
            base_query = meta['query'].strip()
            final_sql = base_query

            if mode == "delta":
                try:
                    sync_status = requests.get(f"{self.cloud_url}/api/sync/status", headers=headers, timeout=5)
                    if sync_status.status_code == 200:
                        last_sync_ts = sync_status.json().get("last_sync_date")
                        if last_sync_ts:
                            clean_ts = last_sync_ts.replace('T', ' ')[:19]
                            self.log(f"Отримано маркер часу: Фільтрація дат після {clean_ts}", "Warning")

                            if db_key == "pg":
                                final_sql = f"SELECT * FROM ({base_query}) AS t WHERE CAST(t.transaction_date AS TIMESTAMP) > '{clean_ts}'"
                            elif db_key == "mysql":
                                final_sql = f"SELECT * FROM ({base_query}) AS t WHERE t.transaction_date > '{clean_ts}'"
                            elif db_key == "mssql":
                                final_sql = f"SELECT * FROM ({base_query}) AS t WHERE CAST(t.transaction_date AS DATETIME) > '{clean_ts}'"
                        else:
                            self.log("Хмарна база ще порожня. Фільтр за датою не застосовано", "INFO")
                except Exception as e:
                    self.log(f"Не вдалося отримати статус синхронізації: {e}", "Error")
                    raise Exception("Помилка підключення до API під час перевірки статусу")
            else:
                self.log("Режим первинного завантаження. Вилучаємо всю історію (обмеження 25k).", "Warning")

            self.log(f"[EXTRACT] Підключення до джерела: {sel_name}...", "INFO")
            engine = create_engine(meta["url"])

            with engine.connect() as conn:
                count_query = f"SELECT COUNT(*) FROM ({final_sql}) AS subquery"
                total_rows = conn.execute(text(count_query)).scalar()

                if total_rows == 0:
                    self.log("Нових транзакцій не знайдено. База актуальна.", "Success")
                    return

                if total_rows > MAIN_LIMIT:
                    self.log(f"[EXTRACT] Обмеження Sampling: беремо {MAIN_LIMIT} з {total_rows}.", "Warning")
                    total_rows = MAIN_LIMIT

                self.log(f"[EXTRACT] Початок вилучення {total_rows} рядків...", "INFO")
                result = conn.execute(text(final_sql))

                chunk_size = 1000
                processed, filtered, sent = 0, 0, 0

                while processed < total_rows:
                    rows = result.fetchmany(chunk_size)
                    if not rows: break

                    self.log(f"--- Пакет {processed} - {processed + len(rows)} ---", "INFO")

                    self.log(f"[TRANSFORM] Очищення, валідація та SHA-256 хешування клієнтів...", "INFO")
                    payload = []
                    for row in rows:
                        if processed >= total_rows: break
                        processed += 1

                        cleaned = self.clean_and_transform_record(row)
                        if cleaned:
                            payload.append(cleaned)
                        else:
                            filtered += 1

                    if payload:
                        self.log(f"[LOAD] Відправка {len(payload)} валідних записів у хмарне сховище...", "INFO")
                        res = requests.post(f"{self.cloud_url}/upload-complex-sync", json={"records": payload},
                                            headers=headers)
                        res.raise_for_status()
                        sent += len(payload)

                    self.update_ram()
                    self.progress['value'] = (processed / total_rows) * 100
                    time.sleep(0.1)

            duration = time.time() - start_time
            self.log(f"ETL-конвеєр успішно завершено!", "Success")
            messagebox.showinfo("BKR Analytics",
                                f"Успішно завантажено: {sent} записів\nВідфільтровано шуму: {filtered}\nЧас виконання: {duration:.1f} сек.")

        except Exception as e:
            self.log(f"Критична помилка конвеєра: {str(e)}", "Error")
        finally:
            self.btn_initial.config(state="normal", bg=COLOR_PRIMARY)
            self.btn_delta.config(state="normal", bg=COLOR_SECONDARY)


if __name__ == "__main__":
    root = tk.Tk()
    app = BKRLocalCollector(root)
    root.mainloop()