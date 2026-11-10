"""
TradeMind AI — Locust Load Testing Script
Simulates realistic concurrent trading workloads (50+ users)
against FastAPI backend endpoints.
"""

from locust import HttpUser, task, between
import random
import os


class PaperTraderUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Use a disposable test-account token for protected endpoints."""
        self.headers = {"Content-Type": "application/json"}
        token = os.getenv("LOCUST_AUTH_TOKEN")
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.tickers = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN"]

    @task(3)
    def check_health(self):
        """Health check endpoint probe."""
        self.client.get("/health", headers=self.headers)

    @task(5)
    def fetch_watchlist_and_prices(self):
        """User views live watchlist and price cache."""
        if not self.headers.get("Authorization"):
            return
        self.client.get("/api/v1/market/watchlist", headers=self.headers)
        self.client.get("/api/v1/market/prices", headers=self.headers)

    @task(4)
    def view_fno_chain(self):
        """User inspects Black-Scholes priced F&O chain."""
        if not self.headers.get("Authorization"):
            return
        ticker = random.choice(["RELIANCE", "INFY", "TCS"])
        self.client.get(f"/api/v1/market/fno/chain?underlying={ticker}", headers=self.headers)

    @task(3)
    def view_news_signals(self):
        """User browses news intelligence signals and impact scores."""
        if not self.headers.get("Authorization"):
            return
        ticker = random.choice(self.tickers)
        self.client.get(f"/api/v1/news/signal?ticker={ticker}", headers=self.headers)

    @task(2)
    def browse_leagues(self):
        """User checks active competitions and leaderboards."""
        if not self.headers.get("Authorization"):
            return
        self.client.get("/api/v1/league/", headers=self.headers)

    @task(1)
    def simulate_order_flow(self):
        """Write test orders only when explicitly enabled for a disposable account."""
        if (
            not self.headers.get("Authorization")
            or os.getenv("LOCUST_ENABLE_ORDER_WRITES", "").lower() != "true"
        ):
            return
        ticker = random.choice(self.tickers)
        payload = {
            "ticker": ticker,
            "order_type": "MARKET",
            "side": random.choice(["BUY", "SELL"]),
            "settlement_type": "DELIVERY",
            "quantity": random.choice([5, 10, 20]),
        }
        self.client.post("/api/v1/orders/", json=payload, headers=self.headers)
