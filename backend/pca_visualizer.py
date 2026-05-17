import polars as pl
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine
import os
import time
from datetime import timedelta
from dotenv import load_dotenv


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

log("--- Початок роботи PCA Visualizer (версія 2.0) ---")

load_dotenv()
standard_url = os.getenv("DATABASE_URL")
polars_url = os.getenv("POLARS_DATABASE_URL")

if not standard_url or not polars_url:
    log(" Помилка: Перевірте DATABASE_URL та POLARS_DATABASE_URL у .env")
    exit()

TARGET_TENANT_ID = 6
log(f" Аналіз даних для Tenant ID: {TARGET_TENANT_ID}")

query = f"""
    SELECT buyer_id, last_order_date, frequency, monetary
    FROM v_customer_rfm_metrics
    WHERE tenant_id = {TARGET_TENANT_ID}
"""

df = None
start_time = time.time()

try:
    log(" Спроба 1: підключення через ADBC (Порт 5432)...")
    adbc_url = polars_url.replace(":6543", ":5432")
    df = pl.read_database_uri(query=query, uri=adbc_url, engine="adbc")
    log(f" Успішно завантажено через ADBC")
except Exception as e:
    log(f" ADBC не зміг підключитися. Причина: {str(e)[:50]}...")

    try:
        log(" Спроба 2: підключення через SQLAlchemy (план Б)...")
        engine = create_engine(standard_url)
        df = pl.read_database(query=query, connection=engine)
        log(f" Успішно завантажено через SQLAlchemy")
    except Exception as e2:
        log(f" Критична помилка підключення: {e2}")
        exit()

elapsed = round(time.time() - start_time, 2)
log(f" Разом отримано рядків: {df.height} за {elapsed} сек")

log(" Обчислення параметра Recency...")
try:
    max_date = df["last_order_date"].max()
    ref_date = max_date + timedelta(days=1)

    df = df.with_columns(
        (ref_date - pl.col("last_order_date")).dt.total_days().alias("recency")
    )
except Exception as e:
    log(f" Помилка обробки даних: {e}")
    exit()

features = ["recency", "frequency", "monetary"]
X = df.select(features).to_numpy()
n_features = len(features)
log(" Нормалізація даних (StandardScaler)...")
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
log(" Розрахунок головних компонент...")
pca = PCA(n_components=n_features)
pca.fit(X_scaled)
explained_variance_ratio = pca.explained_variance_ratio_ * 100
cumulative_variance = np.cumsum(explained_variance_ratio)

log(" Побудова графіка...")
plt.figure(figsize=(11, 6))
# стовпчики дисперсії
bars = plt.bar(range(1, n_features + 1), explained_variance_ratio,
               alpha=0.7, color='#3498db', label='Дисперсія компоненти (%)')
# лінія накопичення
plt.plot(range(1, n_features + 1), cumulative_variance,
         marker='o', color='#e67e22', linewidth=2, markersize=8, label='Кумулятивна дисперсія (%)')
# текстові підписи відсотків
for i, var in enumerate(cumulative_variance):
    plt.text(i + 1, var + 3, f'{var:.1f}%', ha='center', fontsize=10, fontweight='bold')
plt.title(f'Аналіз головних компонент (PCA) | Tenant {TARGET_TENANT_ID}', fontsize=14, pad=20)
plt.xlabel('Порядковий номер компоненти (PC)', fontsize=12)
plt.ylabel('Відсоток збереженої інформації (%)', fontsize=12)
plt.xticks(range(1, n_features + 1), [f'PC{i}' for i in range(1, n_features + 1)])
plt.ylim(0, 115)
plt.grid(axis='y', linestyle='--', alpha=0.3)
plt.legend(loc='lower right')

plt.tight_layout()
log(" Відображення графіка. Перевірте панель завдань")
plt.show()

log("--- Роботу завершено ---")