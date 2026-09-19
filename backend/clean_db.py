import asyncio
from app.database import engine
from sqlalchemy import text

async def clean():
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM backtest_results WHERE equity_curve IS NOT NULL AND equity_curve::text LIKE '%NaN%'"))
        await conn.execute(text("DELETE FROM backtest_results WHERE window_results IS NOT NULL AND window_results::text LIKE '%NaN%'"))
        await conn.commit()
        print('Cleaned NaN records')

asyncio.run(clean())
