import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# 引入初始化逻辑
from rag_engine import init_settings, get_reranker
from database import engine, Base
from migrations import migrate_media_schema
from ingestion import start_worker, stop_worker
from system_metrics import start_metrics, stop_metrics

# 引入路由模块
from routers import auth, chat, files, admin, dashboard, documents, system

# 加载环境变量
load_dotenv()

# 去除代理影响
os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)


# 初始化脚本 (Lifespan)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 初始化数据库表
    Base.metadata.create_all(bind=engine)
    migrate_media_schema(engine)

    # 2. 初始化 RAG 设置
    init_settings()
    get_reranker()  # 预加载模型

    start_worker()
    start_metrics()
    try:
        yield
    finally:
        stop_metrics()
        stop_worker()


app = FastAPI(title="企业数字资产 AI 管理平台", lifespan=lifespan)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(admin.router)
app.include_router(documents.router)
app.include_router(dashboard.router)
app.include_router(system.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)