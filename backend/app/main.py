from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import auth, users, orders, portfolio, market, strategies, news, backtest, league

app = FastAPI(title="TradeMind AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(orders.router)
app.include_router(portfolio.router)
app.include_router(market.router)
app.include_router(strategies.router)
app.include_router(news.router)
app.include_router(backtest.router)
app.include_router(league.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "trademind-backend"}
