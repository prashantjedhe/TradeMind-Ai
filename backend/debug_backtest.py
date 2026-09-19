import asyncio
from app.database import engine
from app.services.backtest_service import _equity_to_json, _simulate_strategy
import pandas as pd
from datetime import datetime, timedelta, timezone
from app.models.ohlcv import BarInterval
from app.services.ohlcv_service import load_bars_dataframe
from app.database import AsyncSession
import json

async def test():
    async with AsyncSession(engine) as db:
        df = await load_bars_dataframe(db, 'RELIANCE', BarInterval.ONE_DAY, limit=300)
        print(f'DF shape: {df.shape}')
        print(f'DF empty: {df.empty}')

        if not df.empty:
            equity, trades = _simulate_strategy(df, None, 1000000.0)
            print(f'Equity series length: {len(equity)}')
            eq_json = _equity_to_json(equity)
            print(f'JSON keys: {list(eq_json.keys())}')
            print(f'First date: {eq_json["dates"][0]}, value type: {type(eq_json["values"][0])}')
            json_str = json.dumps(eq_json)
            print(f'JSON serializable: {len(json_str)} chars')

            # Try the actual DB insert path
            from app.models.backtest_copy_league import BacktestResult, BacktestStatus
            from app.models.user import User
            from sqlalchemy import select

            result = await db.execute(select(User).where(User.email == 'newstest@test.com'))
            user = result.scalar_one()
            print(f'User found: {user.email}')

            bt = BacktestResult(
                user_id=user.id, ticker='RELIANCE', timeframe='1d',
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
                status=BacktestStatus.COMPLETE,
                cagr=0.05, sharpe=1.0, max_drawdown=0.1,
                win_rate=0.6, total_trades=10, total_pnl=5000,
                final_equity=1050000, initial_capital=1000000,
                equity_curve=eq_json,
            )
            db.add(bt)
            await db.commit()
            print('DB insert OK!')

asyncio.run(test())
