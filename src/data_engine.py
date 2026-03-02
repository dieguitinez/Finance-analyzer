import os
import yfinance as yf
import pandas as pd
import numpy as np
import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from src.notifications import NotificationManager

class DataEngine:
    """
    Handles data ingestion from multiple sources.
    Prioritizes OANDA v20 (Institutional) with Yahoo Finance as fallback.
    """
    
    def __init__(self, oanda_config=None):
        self.oanda_config = oanda_config
        self.is_oanda_ready = False
        if oanda_config and oanda_config.get('token') and oanda_config.get('account_id'):
            self.is_oanda_ready = True

    def fetch_data(self, pair, interval, period="60d"):
        """
        Main entry point for data fetching. Expects UI pair format (e.g. 'EUR/USD')
        """
        if self.is_oanda_ready:
            return self._fetch_oanda(pair, interval, period)
        else:
            return self._fetch_yahoo(pair, interval, period)

    def _fetch_yahoo(self, pair, interval, period):
        from src.self_healer import NivoSelfHealer
        
        # Auto-Fix Strategy 1: Try mapped ticker
        primary_symbol = self.get_symbol_map(pair)
        symbols_to_try = [primary_symbol]
        
        # Auto-Fix Strategy 2: Generate algorithmic fallbacks
        if primary_symbol == pair:
            symbols_to_try.extend(NivoSelfHealer.get_ticker_fallbacks(pair))
            
        last_error = None
        for sym in symbols_to_try:
            try:
                df = yf.download(tickers=sym, interval=interval, period=period, progress=False)
                if df is not None and not df.empty:
                    # Standardize columns
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.droplevel('Ticker')
                    return df
            except Exception as e:
                last_error = e
                continue
                
        # If all fallbacks fail, alert via Self-Healer
        print(f"Yahoo Fetch Error: Failed for all fallbacks for {pair}")
        NivoSelfHealer.diagnose_and_alert(
            component="DataEngine.YahooFetch",
            error_msg=f"Falló la descarga de datos técnicos para {pair}.",
            exception_obj=last_error,
            context_data={"pair": pair, "tried_symbols": symbols_to_try}
        )
        return None

    def _fetch_oanda(self, pair, interval, period):
        """
        Implementation of the OANDA v20 REST API fetch.
        """
        import v20
        try:
            # Map symbol to OANDA format (e.g. EUR/USD -> EUR_USD)
            oanda_symbol = pair.replace("/", "_").replace(" ", "_")
            
            # Map interval to OANDA format
            gran_map = {
                "1m": "M1", 
                "5m": "M5", 
                "15m": "M15", 
                "30m": "M30", 
                "1h": "H1", 
                "4h": "H4", 
                "1d": "D"
            }
            granularity = gran_map.get(interval, "H1")

            ctx = v20.Context("api-fxtrade.oanda.com" if "live" in self.oanda_config.get('account_id', '') else "api-fxpractice.oanda.com",
                             443, True, application="NivoFix", token=self.oanda_config['token'])
            
            # Request candles
            response = ctx.instrument.candles(oanda_symbol, granularity=granularity, count=500)
            
            if response.status != 200:
                print(f"OANDA API Error: {response.body.get('errorMessage')}")
                return self._fetch_yahoo(pair, interval, period)

            candles = response.get("candles", 200)
            data_list = []
            for candle in candles:
                if not candle.complete: continue
                data_list.append({
                    "Time": candle.time,
                    "Open": float(candle.mid.o),
                    "High": float(candle.mid.h),
                    "Low": float(candle.mid.l),
                    "Close": float(candle.mid.c),
                    "Volume": int(candle.volume)
                })
            
            df = pd.DataFrame(data_list)
            df['Time'] = pd.to_datetime(df['Time'])
            df.set_index('Time', inplace=True)
            return df
            
        except Exception as e:
            print(f"OANDA Exception: {e}")
            return self._fetch_yahoo(pair, interval, period)

    @staticmethod
    def get_symbol_map(pair):
        """Maps UI pairs to Yahoo Finance tickers."""
        mapping = {
            "EUR/USD": "EURUSD=X",
            "GBP/USD": "GBPUSD=X",
            "USD/JPY": "JPY=X",
            "AUD/USD": "AUDUSD=X",
            "USD/CAD": "USDCAD=X",
            "USD/CHF": "CHF=X",
            "NZD/USD": "NZDUSD=X",
            "EUR/GBP": "EURGBP=X",
            "EUR/JPY": "EURJPY=X",
            "GBP/JPY": "GBPJPY=X",
            "XAU/USD": "GC=F",
            "BTC/USD": "BTC-USD"
        }
        # In case the pair is passed without slash or in a different format
        normalized_pair = pair.replace("-", "/").replace("_", "/").upper()
        return mapping.get(normalized_pair, mapping.get(pair, pair))

class FundamentalEngine:
    """
    Nivo Fundamental Intelligence Layer.
    Fetches real-time institutional news flow via RSS and calculates
    NLP sentiment scores for specific currency pairs.
    """
    
    @staticmethod
    def get_pair_sentiment(pair_name):
        """
        Fetches RSS news from Yahoo Finance for a specific pair and 
        returns (news_items, average_sentiment_0_to_100).
        """
        analyzer = SentimentIntensityAnalyzer()
        symbol = DataEngine.get_symbol_map(pair_name)
        rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
        
        try:
            feed = feedparser.parse(rss_url)
            news_items = []
            total_vader_score = 0
            
            # Use max 10 recent headlines
            entries = feed.entries[:10]
            if not entries:
                return [], 50.0  # Neutral fallback
                
            for entry in entries:
                # Vader compound score is between -1.0 and 1.0
                compound_score = analyzer.polarity_scores(entry.title)['compound']
                total_vader_score += compound_score
                news_items.append({
                    'title': entry.title, 
                    'link': entry.link, 
                    'score': compound_score
                })
            
            avg_compound = total_vader_score / len(entries)
            
            # Map -1.0..1.0 to 0..100 scale for QuantumBridge compatibility
            # (score + 1) * 50
            final_score = (avg_compound + 1.0) * 50.0
            
            return news_items, round(final_score, 2)
            
        except Exception as e:
            from src.self_healer import NivoSelfHealer
            print(f"Fundamental Analysis Error for {pair_name}: {e}")
            
            NivoSelfHealer.diagnose_and_alert(
                component="FundamentalEngine.Sentiment",
                error_msg=f"Error obteniendo noticias/sentimiento para {pair_name}",
                exception_obj=e,
                context_data={"pair": pair_name}
            )
            return [], 50.0 # Return neutral sentiment on failure
