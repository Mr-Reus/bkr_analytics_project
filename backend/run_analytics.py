from ml_pipeline import BKRMachineLearningPipeline

if __name__ == "__main__":
    print("--- Запуск аналітичного рушія БКР ---")
    TARGET_TENANT_ID = 6
    pipeline = BKRMachineLearningPipeline(tenant_id=TARGET_TENANT_ID)
    pipeline.run_rfm_segmentation()
    pipeline.run_market_basket_analysis(min_support=0.01, min_threshold=0.5)
    print("--- Аналітичні процеси завершено ---")