import os
import yfinance as yf
import pandas as pd
import numpy as np
import feedparser
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
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
                err_msg = getattr(response, 'body', {}).get('errorMessage', 'Unknown OANDA Error') if response.body else 'No response body'
                print(f"OANDA API Error {response.status}: {err_msg}")
                return self._fetch_yahoo(pair, interval, period)

            candles = getattr(response, "candles", [])
            if not candles:
                # v20 response objects keep data in 'body' sometimes or as direct attributes
                candles = response.get("candles", [])
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
            "USD/JPY": "USDJPY=X",
            "AUD/USD": "AUDUSD=X",
            "USD/CAD": "USDCAD=X",
            "USD/CHF": "USDCHF=X",
            "NZD/USD": "NZDUSD=X",
            "EUR/GBP": "EURGBP=X",
            "EUR/JPY": "EURJPY=X",
            "GBP/JPY": "GBPJPY=X",
            "EUR/CHF": "EURCHF=X",
            "CHF/JPY": "CHFJPY=X",
            "AUD/JPY": "AUDJPY=X",
            "NZD/JPY": "NZDJPY=X",
            "EUR/AUD": "EURAUD=X",
            "BTC/USD": "BTC-USD",
            "XAU/USD": "GC=F"
        }
        # In case the pair is passed without slash or in a different format
        normalized_pair = pair.replace("-", "/").replace("_", "/").upper().strip()
        return mapping.get(normalized_pair, normalized_pair if "=" in normalized_pair else f"{normalized_pair.replace('/', '')}=X")

    def fetch_dxy_data(self, interval="1h", period="20d"):
        """
        Fetches the US Dollar Index (DXY) from Yahoo Finance.
        Used for Macro Institutional Correlation checks.
        """
        try:
            df = yf.download("DX-Y.NYB", interval=interval, period=period, progress=False)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel('Ticker')
                return df
            return None
        except Exception as e:
            print(f"[DataEngine] Error fetching DXY data: {e}")
            return None

class FundamentalEngine:
    """
    Nivo Fundamental Intelligence Layer (V5).
    Fetches real-time institutional news flow via RSS and calculates
    NLP sentiment scores using the Gemini API cascade (Profile 1).
    """

    # Nivo Architecture Exhaustive Cascade (Profile 1: High Frequency)
    MODEL_CASCADE = [
        'gemini-2.0-flash-lite',
        'gemini-2.0-flash-lite-001',
        'gemini-2.5-flash-lite',
        'gemini-flash-lite-latest'
    ]
    
    @staticmethod
    def get_pair_sentiment(pair_name):
        """
        Fetches RSS news for a specific pair and uses Gemini to 
        calculate an institutional sentiment score (0 to 100).
        """
        symbol = DataEngine.get_symbol_map(pair_name)
        # Combine Yahoo Finance and MarketPulse (OANDA) for higher quality
        rss_urls = [
            f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US",
            "https://www.marketpulse.com/feed/"
        ]
        
        try:
            all_entries = []
            for rss_url in rss_urls:
                feed = feedparser.parse(rss_url)
                all_entries.extend(feed.entries)
            
            # Use max 15 recent headlines to conserve token context and increase speed
            entries = all_entries[:15]
            if not entries:
                print(f"[FundamentalEngine] WARNING: Zero headlines for {pair_name}. RSS feeds may be down. Using neutral 50.0")
                return [], 50.0

            news_items = []
            headlines_text = ""
            for i, entry in enumerate(entries):
                headlines_text += f"{i+1}. {entry.title}\n"
                news_items.append({
                    'title': entry.title, 
                    'link': entry.link, 
                    'score': 0  # Replaced by global Gemini score below
                })
            
            # Prepare Gemini request
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                print("[FundamentalEngine] WARNING: GOOGLE_API_KEY missing. Returning neutral 50.0")
                return news_items, 50.0

            genai.configure(api_key=api_key)
            
            prompt = f"""
            You are a senior institutional FX trader. Analyze the following recent news headlines related to the currency pair {pair_name}.
            
            Headlines:
            {headlines_text}
            
            Task:
            Evaluate the overall fundamental sentiment for the base currency in {pair_name} based on these headlines.
            Output ONLY a single floating-point number between 0.0 and 100.0, where:
            - 0.0 is extremely bearish (panic sell base currency)
            - 50.0 is completely neutral or mixed
            - 100.0 is extremely bullish (conviction buy base currency)
            
            Output nothing else. No explanation. Just the number.
            """

            final_score = 50.0
            success = False
            
            for model_name in FundamentalEngine.MODEL_CASCADE:
                try:
                    model = genai.GenerativeModel(model_name)
                    # We configure safety settings to NONE as financial news can trigger violence filters ("markets crushed")
                    response = model.generate_content(
                        prompt,
                        safety_settings={
                            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                        }
                    )
                    
                    if response.text:
                        score_str = response.text.replace('```', '').strip()
                        final_score = float(score_str)
                        # Clamp the score between 0 and 100
                        final_score = max(0.0, min(100.0, final_score))
                        print(f"[FundamentalEngine] Gemini Consensus ({model_name}) for {pair_name}: {final_score}")
                        success = True
                        break # Stop cascading on success
                        
                except Exception as cascade_e:
                    print(f"[FundamentalEngine] WARNING: Model {model_name} failed: {cascade_e}. Falling back...")
                    continue
                    
            if not success:
               print(f"[FundamentalEngine] ERROR: All models in the Profile 1 cascade failed. Using neutral 50.0")
               
            # Update individual items for UI compatibility (so dashboards mapping -1 to 1 still work somewhat)
            legacy_mapping = (final_score - 50.0) / 50.0
            for item in news_items:
                item['score'] = legacy_mapping
                
            return news_items, round(final_score, 2)
            
        except Exception as e:
            from src.self_healer import NivoSelfHealer
            print(f"[FundamentalEngine] Critical Error for {pair_name}: {e}")
            
            NivoSelfHealer.diagnose_and_alert(
                component="FundamentalEngine.Sentiment",
                error_msg=f"Error obteniendo sentimiento con Gemini IA para {pair_name}",
                exception_obj=e,
                context_data={"pair": pair_name}
            )
            return [], 50.0
