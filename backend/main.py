from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Header, BackgroundTasks, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
import os
import secrets
import uuid
import io
import pandas as pd
from sqlalchemy import create_engine, text
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv
import hashlib
import json

from ml_pipeline import BKRMachineLearningPipeline

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
INVITE_CODE_HASH = os.getenv("INVITE_CODE_HASH")

if not DATABASE_URL or not SECRET_KEY:
    raise ValueError("Помилка: DATABASE_URL або JWT_SECRET_KEY не знайдено у файлі .env чи середовищі")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

scheduler = AsyncIOScheduler()


def nightly_batch_processing():
    """Фонове завдання делта-завантаження та перерахунку ML-мо моделей за розкладом"""
    print(f"\n[CRON] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Старт оброблення даних...")
    try:
        with engine.begin() as conn:
            tenants = conn.execute(text("SELECT id FROM tenants")).fetchall()

        if not tenants:
            print("[CRON] Немає зареєстрованих тенантів. Пропуск")
            return

        for tenant in tenants:
            tenant_id = tenant[0]
            print(f"  -> Запуск ML Pipeline для Tenant ID: {tenant_id}")
            pipeline = BKRMachineLearningPipeline(tenant_id=tenant_id)
            pipeline.run_rfm_segmentation()
            pipeline.run_market_basket_analysis()

        print(f"[CRON] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - оброблення успішно завершено\n")
    except Exception as e:
        print(f"[CRON] Помилка під час оброблення: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        nightly_batch_processing,
        CronTrigger(hour=5, minute=0),
        id="nightly_ml_pipeline",
        replace_existing=True
    )
    scheduler.start()
    print("Автоматичний планувальник (APScheduler) успішно запущено через Lifespan")
    yield
    scheduler.shutdown()
    print("Планувальник успішно зупинено через Lifespan")


app = FastAPI(title="BKR E-commerce Analytics API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AdminRegister(BaseModel):
    company_name: str
    email: EmailStr
    password: str
    invite_code: str


class AnalystCreate(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class SyncRecord(BaseModel):
    client_hash: str
    product_code: str
    quantity: int
    price: float
    order_date: str


class SyncBatch(BaseModel):
    records: List[SyncRecord]


class MiningParams(BaseModel):
    min_support: float = 0.01
    min_threshold: float = 0.5


def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def set_db_tenant_context(conn, tenant_id: int):
    conn.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        with engine.connect() as conn:
            user = conn.execute(
                text("SELECT id, tenant_id, email, role, pref_theme, pref_lang FROM web_users WHERE id = :uid"),
                {"uid": user_id}).fetchone()
            if user is None:
                raise HTTPException(status_code=401, detail="User not found")
            return dict(user._mapping)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired or invalid")


async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin only")
    return current_user


auth_router = APIRouter(prefix="/api/auth", tags=["1. Authentication"])


@auth_router.post("/register/admin", response_model=Token)
async def register_tenant_admin(user: AdminRegister):
    if not INVITE_CODE_HASH:
        raise HTTPException(status_code=500, detail="Помилка конфігурації: відсутній хеш коду доступу на сервері")

    if not pwd_context.verify(user.invite_code, INVITE_CODE_HASH):
        raise HTTPException(status_code=403, detail="Недійсний код доступу для реєстрації нової компанії")

    with engine.begin() as conn:
        if conn.execute(text("SELECT id FROM web_users WHERE email = :e"), {"e": user.email}).fetchone():
            raise HTTPException(status_code=400, detail="Користувач з таким Email вже існує")

        new_key = f"bkr_{secrets.token_hex(16)}"
        res = conn.execute(text("INSERT INTO tenants (company_name, tenant_key) VALUES (:name, :key) RETURNING id"),
                           {"name": user.company_name, "key": new_key})
        tenant_id = res.scalar()

        hashed_pw = pwd_context.hash(user.password)
        res_user = conn.execute(text(
            "INSERT INTO web_users (tenant_id, email, hashed_password, role) VALUES (:tid, :email, :pw, 'admin') RETURNING id"),
            {"tid": tenant_id, "email": user.email, "pw": hashed_pw})

    return {
        "access_token": create_access_token({"sub": str(res_user.scalar()), "role": "admin", "tenant_id": tenant_id}),
        "token_type": "bearer"
    }


@auth_router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with engine.connect() as conn:
        u = conn.execute(text("SELECT id, tenant_id, hashed_password, role FROM web_users WHERE email = :e"),
                         {"e": form_data.username}).fetchone()
        if not u or not pwd_context.verify(form_data.password, u.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect credentials")
    return {"access_token": create_access_token({"sub": str(u.id), "role": u.role, "tenant_id": u.tenant_id}),
            "token_type": "bearer"}


main_router = APIRouter()


@main_router.get("/api/admin/analysts", tags=["2. Admin"])
async def get_analysts(admin: dict = Depends(require_admin)):
    with engine.connect() as conn:
        set_db_tenant_context(conn, admin["tenant_id"])
        query = text("""
                     SELECT id, email, created_at
                     FROM web_users
                     WHERE tenant_id = :tid
                       AND role = 'business_analyst'
                     ORDER BY created_at DESC
                     """)
        analysts = conn.execute(query, {"tid": admin["tenant_id"]}).fetchall()
    return [dict(row._mapping) for row in analysts]


@main_router.post("/api/admin/analysts", tags=["2. Admin"])
async def create_analyst(analyst: AnalystCreate, admin: dict = Depends(require_admin)):
    hashed_pw = pwd_context.hash(analyst.password)
    with engine.begin() as conn:
        set_db_tenant_context(conn, admin["tenant_id"])
        if conn.execute(text("SELECT id FROM web_users WHERE email = :e"), {"e": analyst.email}).fetchone():
            raise HTTPException(status_code=400, detail="Користувач з таким Email вже існує")

        conn.execute(text("""
                          INSERT INTO web_users (tenant_id, email, hashed_password, role)
                          VALUES (:tid, :email, :pw, 'business_analyst')
                          """), {"tid": admin["tenant_id"], "email": analyst.email, "pw": hashed_pw})
    return {"status": "success", "message": "Обліковий запис аналітика успешно створено"}


@main_router.delete("/api/admin/analysts/{analyst_id}", tags=["2. Admin"])
async def delete_analyst(analyst_id: str, admin: dict = Depends(require_admin)):
    with engine.begin() as conn:
        set_db_tenant_context(conn, admin["tenant_id"])
        result = conn.execute(
            text("""
                 DELETE
                 FROM web_users
                 WHERE id = CAST(:uid AS UUID)
                   AND tenant_id = :tid
                   AND role != 'admin'
                RETURNING id
                 """),
            {"uid": analyst_id, "tid": admin["tenant_id"]}
        ).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Аналітика не знайдено або доступ заборонено")
    return {"status": "success", "message": "Аналітика успішно видалено"}


@main_router.get("/api/admin/integration-key", tags=["2. Admin"])
async def get_key(admin: dict = Depends(require_admin)):
    with engine.connect() as conn:
        key = conn.execute(text("SELECT tenant_key FROM tenants WHERE id = :tid"), {"tid": admin["tenant_id"]}).scalar()
    return {"tenant_key": key}


@main_router.get("/api/analytics/kpis", tags=["3. Analytics"])
async def get_kpis(user: dict = Depends(get_current_user)):
    with engine.connect() as conn:
        set_db_tenant_context(conn, user["tenant_id"])
        res = conn.execute(text(
            "SELECT SUM(total_amount), COUNT(DISTINCT buyer_id) FROM analytical_dataset_view WHERE tenant_id = :tid"),
            {"tid": user["tenant_id"]}).fetchone()
    return {"total_revenue": float(res[0] or 0), "total_customers": int(res[1] or 0)}


@main_router.post("/api/analytics/run", tags=["3. Analytics"])
async def trigger_analytics(params: MiningParams, background_tasks: BackgroundTasks,
                            current_user: dict = Depends(get_current_user)):
    pipeline = BKRMachineLearningPipeline(tenant_id=current_user["tenant_id"])
    background_tasks.add_task(pipeline.run_rfm_segmentation)
    background_tasks.add_task(pipeline.run_market_basket_analysis, min_support=params.min_support,
                              min_threshold=params.min_threshold)
    return {"status": "accepted", "message": "Процес Data Mining ініційовано у фоновому режимі"}


@main_router.get("/api/analytics/export-csv", tags=["3. Analytics"])
async def export_csv(current_user: dict = Depends(get_current_user)):
    query = text(
        "SELECT payload FROM analysis_results WHERE tenant_id = :tid AND report_type = 'rfm_analysis' ORDER BY created_at DESC LIMIT 1")
    with engine.connect() as conn:
        set_db_tenant_context(conn, current_user["tenant_id"])
        result = conn.execute(query, {"tid": current_user["tenant_id"]}).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Звіт не знайдено")

    payload = result[0] if not isinstance(result[0], str) else json.loads(result[0])
    df = pd.DataFrame(payload.get('assignments', []))
    output = io.StringIO()
    df.to_csv(output, index=False)
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=bkr_rfm_segments.csv"})


@main_router.get("/api/analytics/export-json", tags=["3. Analytics"])
async def export_json(report_type: str = 'rfm_analysis', current_user: dict = Depends(get_current_user)):
    query = text(
        "SELECT payload FROM analysis_results WHERE tenant_id = :tid AND report_type = :rtype ORDER BY created_at DESC LIMIT 1")
    with engine.connect() as conn:
        set_db_tenant_context(conn, current_user["tenant_id"])
        result = conn.execute(query, {"tid": current_user["tenant_id"], "rtype": report_type}).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Звіт не знайдено")
    payload = result[0] if not isinstance(result[0], str) else json.loads(result[0])
    return payload

@app.get("/verify-me", tags=["4. ETL"])
async def verify(x_tenant_key: str = Header(None)):
    if not x_tenant_key: raise HTTPException(status_code=401)
    with engine.connect() as conn:
        if conn.execute(text("SELECT 1 FROM tenants WHERE tenant_key = :k"), {"k": x_tenant_key}).scalar():
            return {"status": "ok"}
    raise HTTPException(status_code=401)


@app.get("/api/sync/status", tags=["4. ETL"])
async def get_sync_status(x_tenant_key: str = Header(None)):
    if not x_tenant_key: raise HTTPException(status_code=401)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT last_sync_date FROM tenants WHERE tenant_key = :k"),
                           {"k": x_tenant_key}).fetchone()
        if not res: raise HTTPException(status_code=404)
        return {"last_sync_date": res[0].isoformat() if res[0] else None}


@app.post("/upload-complex-sync", tags=["4. ETL"])
async def complex_sync(batch: SyncBatch, x_tenant_key: str = Header(None)):
    if not x_tenant_key: raise HTTPException(status_code=401, detail="Missing Tenant Key")

    with engine.begin() as conn:
        tenant = conn.execute(text("SELECT id FROM tenants WHERE tenant_key = :k"), {"k": x_tenant_key}).fetchone()
        if not tenant: raise HTTPException(status_code=401, detail="Invalid Tenant Key")
        tenant_id = tenant[0]

        records = batch.records
        if not records: return {"status": "success", "inserted": 0}

        unique_hashes = list(set(r.client_hash for r in records))
        conn.execute(
            text("INSERT INTO customers (tenant_id, customer_hash) VALUES (:tid, :h) ON CONFLICT DO NOTHING"),
            [{"tid": tenant_id, "h": h} for h in unique_hashes]
        )
        cust_rows = conn.execute(
            text("SELECT id, customer_hash FROM customers WHERE tenant_id = :tid AND customer_hash IN :hashes"),
            {"tid": tenant_id, "hashes": tuple(unique_hashes)}
        ).fetchall()
        cust_map = {row.customer_hash: row.id for row in cust_rows}

        prod_data = {r.product_code: r.price for r in records}
        conn.execute(
            text(
                "INSERT INTO products (tenant_id, product_code, price) VALUES (:tid, :pc, :pr) ON CONFLICT (tenant_id, product_code) DO UPDATE SET price = EXCLUDED.price"),
            [{"tid": tenant_id, "pc": pc, "pr": pr} for pc, pr in prod_data.items()]
        )
        prod_rows = conn.execute(
            text("SELECT id, product_code FROM products WHERE tenant_id = :tid AND product_code IN :codes"),
            {"tid": tenant_id, "codes": tuple(prod_data.keys())}
        ).fetchall()
        prod_map = {row.product_code: row.id for row in prod_rows}

        orders_dict = {}
        order_items_payload = []

        for rec in records:
            c_id = cust_map.get(rec.client_hash)
            p_id = prod_map.get(rec.product_code)
            if not c_id or not p_id: continue

            basket_id_str = f"tenant_{tenant_id}_{rec.client_hash}_{rec.order_date}"
            det_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, basket_id_str))

            if det_uuid not in orders_dict:
                orders_dict[det_uuid] = {
                    "id": det_uuid, "tid": tenant_id, "cid": c_id,
                    "dt": rec.order_date, "ord_num": f"ORD-{det_uuid[:8].upper()}"
                }

            order_items_payload.append({
                "oid": det_uuid, "pid": p_id, "q": rec.quantity, "p": rec.price, "uid": c_id
            })

        if orders_dict:
            conn.execute(
                text(
                    "INSERT INTO orders (id, tenant_id, customer_id, transaction_date, order_number) VALUES (:id, :tid, :cid, :dt, :ord_num) ON CONFLICT (id) DO NOTHING"),
                list(orders_dict.values())
            )

        if order_items_payload:
            conn.execute(
                text(
                    "INSERT INTO order_items (order_id, product_id, quantity, price, user_id) VALUES (:oid, :pid, :q, :p, :uid)"),
                order_items_payload
            )

        conn.execute(text("UPDATE tenants SET last_sync_date = NOW() WHERE id = :tid"), {"tid": tenant_id})

    return {"status": "success", "processed_records": len(batch.records)}


app.include_router(auth_router)
app.include_router(main_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)