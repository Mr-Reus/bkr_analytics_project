import polars as pl
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, davies_bouldin_score
from mlxtend.frequent_patterns import fpgrowth, association_rules
from sqlalchemy import create_engine, text
import json
import os
import time
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class BKRMachineLearningPipeline:
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("Не знайдено DATABASE_URL у файлі .env")
        self.engine = create_engine(db_url)

    def _calculate_correlation_matrix(self, df: pl.DataFrame, features: list):
        print(" -> Обчислення кореляційної матриці (Polars)...")
        clean_df = df.select([pl.col(f).cast(pl.Float64) for f in features])
        with np.errstate(divide='ignore', invalid='ignore'):
            corr_df = clean_df.corr()

        corr_dict = {}
        for i, col_name in enumerate(features):
            corr_dict[col_name] = {}
            for j, row_name in enumerate(features):
                val = corr_df[col_name][j]
                if val is None or str(val).lower() == 'nan':
                    val = 0.0
                corr_dict[col_name][row_name] = round(float(val), 3)
        return corr_dict

    def _evaluate_model(self, X_weighted, k):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
        labels = kmeans.fit_predict(X_weighted)
        sil = silhouette_score(X_weighted, labels)
        db = davies_bouldin_score(X_weighted, labels)
        return sil, db

    def _find_optimal_clusters(self, X_weighted, max_k=8):
        print(f" -> Розрахунок метрик для різних k (збереження історії)...")
        results = {}
        for k in range(2, max_k + 1):
            sil, db = self._evaluate_model(X_weighted, k)
            results[k] = {"silhouette": round(sil, 4), "db_index": round(db, 4)}
        return results

    def _cleanup_old_results(self, report_type: str, keep_limit: int = 3):
        print(f"  ->  Очищення застарілих звітів '{report_type}' (залишаємо {keep_limit} останніх)...")
        query = text("""
            DELETE FROM analysis_results
            WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY tenant_id, report_type 
                        ORDER BY created_at DESC
                    ) as rn
                    FROM analysis_results
                    WHERE tenant_id = :tid AND report_type = :rtype
                ) t
                WHERE t.rn > :limit
            )
        """)
        with self.engine.begin() as conn:
            conn.execute(query, {"tid": self.tenant_id, "rtype": report_type, "limit": keep_limit})

    def run_rfm_segmentation(self):
        print(f"\n[RFM Pipeline] production версія для Tenant {self.tenant_id}")
        start_time = time.time()
        if self.tenant_id is None:
            print(" ->  Помилка: Tenant ID відсутній (None). Перевірте токен користувача")
            return

        query = text("""
                     SELECT buyer_id, last_order_date, frequency, monetary
                     FROM v_customer_rfm_metrics
                     WHERE tenant_id = :tenant_id
                     """)

        try:
            with self.engine.connect() as conn:
                import pandas as pd
                df_pd = pd.read_sql_query(query, con=conn, params={"tenant_id": self.tenant_id})
                df = pl.from_pandas(df_pd)
        except Exception as e:
            print(f" -> Помилка читання БД: {e}")
            return

        if df.height < 10:
            print(" ->  Замало даних для кластеризації")
            return

        max_date = df["last_order_date"].max()
        ref_date = max_date + timedelta(days=1)
        df = df.with_columns((ref_date - pl.col("last_order_date")).dt.total_days().alias("recency"))

        features = ["recency", "frequency", "monetary"]
        X_raw = df.select(features).to_numpy()
        X_scaled = StandardScaler().fit_transform(X_raw)

        base_k = 3
        base_sil, base_db = self._evaluate_model(X_scaled, base_k)

        print(" ->  Застосування ваг: Recency (x1.0), Frequency (x1.5), Monetary (x1.0)")
        X_weighted = X_scaled.copy()
        X_weighted[:, 1] *= 1.0

        tuning_history = self._find_optimal_clusters(X_weighted, max_k=min(9, df.height - 1))
        best_k = 3
        final_sil, final_db = self._evaluate_model(X_weighted, best_k)

        print("\n--- Порівняння та вибір ---")
        print(f"     Метрика          | Baseline (без ваг) | Optimized (з вагами, k={best_k}) | Різниця")
        print(f"     {'-' * 80}")
        print(f"     Silhouette (↑)   | {base_sil:<18.4f} | {final_sil:<32.4f} | {final_sil - base_sil:+.4f}")
        print(f"     Davies-Bouldin(↓)| {base_db:<18.4f} | {final_db:<32.4f} | {final_db - base_db:+.4f}")

        kmeans = KMeans(n_clusters=best_k, random_state=42, n_init='auto')
        df = df.with_columns(pl.Series("cluster_id", kmeans.fit_predict(X_weighted)))

        summary_df = df.group_by("cluster_id").agg([
            pl.col("recency").mean().round(2),
            pl.col("frequency").mean().round(2),
            pl.col("monetary").mean().round(2),
            pl.len().alias("customer_count")
        ]).sort("cluster_id")

        payload = {
            "strategy": "feature_weighting_fixed_k",
            "weights": {"recency": 1.0, "frequency": 1.0, "monetary": 1.0},
            "performance": {
                "optimized_k": best_k,
                "silhouette": round(final_sil, 4),
                "davies_bouldin": round(final_db, 4)
            },
            "tuning_history": tuning_history,
            "correlation": self._calculate_correlation_matrix(df, features),
            "segments": {str(r["cluster_id"]): r for r in summary_df.to_dicts()},
            "assignments": [{"id": str(r["buyer_id"]), "cid": int(r["cluster_id"])} for r in df.to_dicts()]
        }

        self._save_results_to_db("rfm_analysis", payload)
        self._cleanup_old_results("rfm_analysis") # Автоматичне очищення
        print(f"\n Пайплайн успішно завершено за {round(time.time() - start_time, 2)} сек")

    def run_market_basket_analysis(self, min_support=0.01, min_threshold=0.5):
        print(f"\n [FP-Growth] Початок market basket analysis для tenant {self.tenant_id}")
        start_time = time.time()

        query = text("""
                     SELECT oi.order_id, p.product_code
                     FROM order_items oi
                     JOIN orders o ON oi.order_id = o.id
                     JOIN products p ON oi.product_id = p.id
                     WHERE o.tenant_id = :tenant_id
                     """)

        try:
            print(" ->  Завантаження транзакцій з бази...")
            with self.engine.connect() as conn:
                df_transactions = pd.read_sql_query(query, con=conn, params={"tenant_id": self.tenant_id})
            print(f"  > Отримано {len(df_transactions)} позицій у чеках")
        except Exception as e:
            print(f"  Помилка читання БД: {e}")
            return

        if df_transactions.empty:
            print("  >  Немає даних про транзакції для цього tenant")
            return

        print(" -> Оптимізація пам'яті: фільтрація топ-2000 позицій...")
        top_items = df_transactions['product_code'].value_counts().head(2000).index.tolist()
        df_transactions = df_transactions[df_transactions['product_code'].isin(top_items)]

        print("  -> Формування матриці транзакцій...")
        basket = (df_transactions
                  .groupby(['order_id', 'product_code'])['product_code']
                  .count().unstack().reset_index().fillna(0)
                  .set_index('order_id'))

        def encode_units(x):
            if x <= 0: return False
            if x >= 1: return True

        basket_sets = basket.map(encode_units)
        print(f" -> Проаналізовано {len(basket_sets)} унікальних замовлень")

        if len(basket_sets) < 10:
            print(" ->  Замало замовлень для аналізу асоціацій")
            return

        print(f"  -> Запуск FP-Growth (min_support={min_support})...")
        frequent_itemsets = fpgrowth(basket_sets, min_support=min_support, use_colnames=True)

        if frequent_itemsets.empty:
            print("  -> ️ Не знайдено частих наборів. Спробуйте зменшити min_support")
            return

        print(f" -> Формування правил (min_confidence={min_threshold})...")
        rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=min_threshold)

        if rules.empty:
            print(" ->  Не знайдено сильних правил. Спробуйте зменшити min_threshold")
            return

        rules["antecedents"] = rules["antecedents"].apply(lambda x: list(x))
        rules["consequents"] = rules["consequents"].apply(lambda x: list(x))

        top_rules = rules[['antecedents', 'consequents', 'support', 'confidence', 'lift']].sort_values(by='confidence', ascending=False)

        rules_list = []
        for _, row in top_rules.iterrows():
            rules_list.append({
                "if_bought": row["antecedents"],
                "then_buy": row["consequents"],
                "support": round(row["support"], 4),
                "confidence": round(row["confidence"], 4),
                "lift": round(row["lift"], 4)
            })

        print(f" -> Знайдено {len(rules_list)} сильних правил")

        payload = {
            "algorithm": "FP-Growth",
            "parameters": {"min_support": min_support, "min_threshold": min_threshold},
            "summary": {
                "total_orders": len(basket_sets),
                "rules_found": len(rules_list)
            },
            "association_rules": rules_list
        }

        self._save_results_to_db("fp_growth_rules", payload)
        self._cleanup_old_results("fp_growth_rules")
        print(f"\n [FP-Growth] Завершено за {round(time.time() - start_time, 2)} сек")

    def _save_results_to_db(self, report_type, payload):
        print(" -> Збереження результатів у Supabase...")
        query = text("INSERT INTO analysis_results (tenant_id, report_type, payload) VALUES (:tid, :rtype, :json_data)")
        with self.engine.begin() as conn:
            conn.execute(query, {"tid": self.tenant_id, "rtype": report_type, "json_data": json.dumps(payload)})
        print(f" ->  Дані звіту '{report_type}' збережено успішно")