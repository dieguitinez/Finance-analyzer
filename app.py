import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import datetime
import time
import os
import warnings

import concurrent.futures
from google import genai
import gc

# Custom Modular Imports
from src.notifications import NotificationManager
from src.data_engine import DataEngine, FundamentalEngine
from quantum_engine.quantum_bridge import QuantumBridge
from quantum_engine.risk_manager import CapitalGuardian
from src.nivo_cortex import NivoCortex, MarketRegimeDetector

# Import availability flags for Lite Mode detection
try:
    from src.nivo_cortex import TORCH_AVAILABLE, HMM_AVAILABLE
except ImportError:
    TORCH_AVAILABLE, HMM_AVAILABLE = False, False

LITE_MODE = not (TORCH_AVAILABLE and HMM_AVAILABLE)

# --- App Configuration ---
st.set_page_config(
    page_title="Nivo FX Intelligence Suite",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main { background-color: #050507; }
    .stMetric { background-color: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.1); }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        background-color: rgba(255, 255, 255, 0.03); 
        border-radius: 5px 5px 0px 0px; 
        padding: 10px 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. Resource Caching (Heavy AI Models) ---
@st.cache_resource(show_spinner=False, max_entries=1)
def load_models():
    """ 
    Ensures Heavy AI classes are imported and pre-warmed in RAM ONCE to prevent 
    reload lag on every Interaction.
    """
    from src.nivo_trade_brain import NivoTradeBrain
    from src.nivo_cortex import NivoCortex
    return NivoTradeBrain, NivoCortex

BrainClass, CortexClass = load_models()

# --- Session State Management ---
if 'lang' not in st.session_state: st.session_state.lang = 'EN'
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'last_fetch_ts' not in st.session_state: st.session_state.last_fetch_ts = 0.0
if 'ai_results' not in st.session_state: st.session_state.ai_results = {}

# Translations
translations = {
    'EN': {
        'title': "Nivo FX Studio",
        'subtitle': "Institutional Grade Trading Suite",
        'lang_toggle': "Language / Idioma",
        'currency_pair': "Currency Pair",
        'timeframe': "Interval",
        'tf_options': {
            "1m": "1 Minute (Scalp)",
            "5m": "5 Minutes (Intraday)", 
            "15m": "15 Minutes (Intraday)", 
            "30m": "30 Minutes (Standard)",
            "1h": "1 Hour (Trend)", 
            "4h": "4 Hours (Macro Trend)",
            "1d": "1 Day (Max History)"
        },
        'indicators': "Chart Overlays",
        'show_ema': "Show EMAs (50, 200)",
        'show_bb': "Show Bollinger Bands",
        'alpha': "### The Alpha (Real-Time Stats)",
        'current_price': "Current Price",
        'stop_loss': "Nivo Stop Loss (1.5x ATR)",
        'take_profit': "Target Profit (3x ATR)",
        'tab_tech': "📈 Technical Analysis",
        'tab_fund': "📰 Fundamental Intelligence",
        'tab_season': "⏳ Time Travel Patterns",
        'tab_kai': "🤖 Kai FX Assistant",
        'news_title': "Real-Time NLP Sentiment & News Flow",
        'sentiment_overall': "Overall Sentiment Score",
        'kai_placeholder': "Ask Kai FX about the current market setup...",
        'tab_glossary': "📖 Glossary",
        'tab_quantum': "⚛️ Quantum Projections",
        'quantum_regime': "HQMM Regime Probabilities",
        'quantum_multiplier': "Quantum Final Multiplier",
        'quantum_direction': "QLSTM Bull Probability",
        'tab_risk': "🛡️ Risk Management",
        'risk_guardian': "Capital Guardian Status",
        'tab_protocol': "📜 Intelligence Protocol",
        'lite_mode_warning': "⚡ LITE MODE ACTIVE: Heavy AI models (HMM/LSTM) are offloaded to your Linux server to save cloud memory.",
        'lite_mode_info': "Technical info available. Neural analysis restricted to Linux terminal.",
    },
    'ES': {
        'title': "Nivo FX Studio",
        'subtitle': "Suite de Trading Institucional",
        'lang_toggle': "Idioma / Language",
        'currency_pair': "Par de Divisas",
        'timeframe': "Intervalo",
        'tf_options': {
            "1m": "1 Minuto (Scalping)",
            "5m": "5 Minutos (Intraday)", 
            "15m": "15 Minutos (Intraday)", 
            "30m": "30 Minutos (Estándar)",
            "1h": "1 Hora (Tendencia)",
            "4h": "4 Horas (Macro Tendencia)",
            "1d": "1 Día (Historial Máx)"
        },
        'indicators': "Capas del Gráfico",
        'show_ema': "Mostrar EMAs (50, 200)",
        'show_bb': "Mostrar Bandas Bollinger",
        'alpha': "### The Alpha (Estadísticas en Vivo)",
        'current_price': "Precio Atual",
        'stop_loss': "Nivo Stop Loss (1.5x ATR)",
        'take_profit': "Take Profit Sugerido (3x ATR)",
        'tab_tech': "📈 Análisis Técnico",
        'tab_fund': "📰 Inteligencia Fundamental",
        'tab_season': "⏳ Patrones Estacionales",
        'tab_kai': "🤖 Asistente Kai FX",
        'news_title': "Flujo de Noticias y Sentimiento NLP",
        'sentiment_overall': "Puntaje de Sentimiento General",
        'kai_placeholder': "Pregúntale a Kai FX sobre la configuración actual del mercado...",
        'tab_glossary': "📖 Glosario",
        'tab_quantum': "⚛️ Proyecciones Cuánticas",
        'quantum_regime': "Probabilidades de Régimen HQMM",
        'quantum_multiplier': "Multiplicador Cuántico Final",
        'quantum_direction': "Probabilidad Alcista QLSTM",
        'tab_risk': "🛡️ Gestión de Riesgos",
        'risk_guardian': "Estado del Guardián de Capital",
        'tab_protocol': "📜 Protocolo de Inteligencia",
        'lite_mode_warning': "⚡ MODO LITE ACTIVO: Los modelos pesados (HMM/LSTM) están corriendo en tu servidor Linux para ahorrar memoria en la web.",
        'lite_mode_info': "Información técnica disponible. Análisis neuronal restringido a la Terminal Linux.",
    }
}
t = translations[st.session_state.lang]

if LITE_MODE:
    st.warning(t['lite_mode_warning'])

# --- Sidebar UI ---
with st.sidebar:
    st.title(t['title'])
    st.caption(t['subtitle'])
    
    lang_choice = st.radio(t['lang_toggle'], ['English', 'Español'], index=0 if st.session_state.lang == 'EN' else 1)
    if (lang_choice == 'English' and st.session_state.lang == 'ES') or (lang_choice == 'Español' and st.session_state.lang == 'EN'):
        st.session_state.lang = 'EN' if lang_choice == 'English' else 'ES'
        st.rerun()

    pair_options = [
        "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", 
        "USD/CHF", "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY", 
        "EUR/CHF", "CHF/JPY", "AUD/JPY", "NZD/JPY", "EUR/AUD"
    ]
    selected_pair_ui = st.selectbox(t['currency_pair'], pair_options)
    
    tf_keys = ["5m", "15m", "1h", "1d"]
    tf_labels = [t['tf_options'][k] for k in tf_keys] # type: ignore
    selected_label = st.selectbox(t['timeframe'], tf_labels)
    selected_tf = tf_keys[tf_labels.index(selected_label)]
    
    st.subheader(t['indicators'])
    show_ema = st.checkbox(t['show_ema'], value=True)
    show_bb = st.checkbox(t['show_bb'], value=False)
    
    st.markdown("---")
    st.info("🎯 Nivo FX Sentinel Active")

# --- Institutional Config (Loaded from Secrets) ---
oanda_token = st.secrets.get("oanda_token", "")
oanda_id = st.secrets.get("oanda_account_id", "")
gemini_key = st.secrets.get("gemini_api_key", "")

# --- 2. Data Caching (TTL) & Async Threading ---
@st.cache_data(ttl=60, show_spinner=False, max_entries=2)
def fetch_market_data(pair_name, tf, token, acc_id):
    """ Cached 60s. Fetches price array """
    engine = DataEngine({'token': token, 'account_id': acc_id} if token else None)
    return engine.fetch_data(DataEngine.get_symbol_map(pair_name), tf), time.time()

@st.cache_data(ttl=300, show_spinner=False)
def fetch_global_scan(pair_list, tf, token, acc_id):
    """ Performs a lightweight technical scan across the entire watchlist. """
    results = {}
    engine = DataEngine({'token': token, 'account_id': acc_id} if token else None)
    
    def scan_one(p):
        try:
            df = engine.fetch_data(DataEngine.get_symbol_map(p), tf)
            if df is not None and not df.empty:
                brain = BrainClass(df)
                analysis = brain.analyze_market()
                return p, analysis['score'], analysis['signal']
        except: pass
        return p, 0, "ERROR"

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(scan_one, p): p for p in pair_list}
        for future in concurrent.futures.as_completed(future_map):
            p, score, signal = future.result()
            results[p] = {"score": score, "signal": signal}
    return results

def fetch_news_data(pair_name):
    """ Proxies to the shared FundamentalEngine (No caching here, handled by ThreadPool result) """
    return FundamentalEngine.get_pair_sentiment(pair_name)

def fetch_seasonality_data(pair_name):
    """ Fetches seasonality data (No caching here) """
    df = DataEngine().fetch_data(DataEngine.get_symbol_map(pair_name), "1d", period="max")
    if df is not None:
        df['Return'] = df['Close'].pct_change() * 100
        df['Month'] = df.index.month
    return df

# Main parallel executor preloading all tabs at once
with st.spinner("⚡ Synchronizing Nivo Datasets..."):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        f_price = executor.submit(fetch_market_data, selected_pair_ui, selected_tf, oanda_token, oanda_id)
        f_news = executor.submit(fetch_news_data, selected_pair_ui)
        f_season = executor.submit(fetch_seasonality_data, selected_pair_ui)
        f_global = executor.submit(fetch_global_scan, pair_options, selected_tf, oanda_token, oanda_id)
        
        data, current_fetch_ts = f_price.result()
        news, avg_s = f_news.result()
        s_data = f_season.result()
        global_results = f_global.result()


# Top Navigation
c1, c2 = st.columns([0.8, 0.2])
c1.title(f"📊 {selected_pair_ui} Analysis")

# Performance visual indicator requested by prompt
if current_fetch_ts == st.session_state.last_fetch_ts:
    c2.info("⚡ Data loaded from Cache")
    needs_ai_recalc = False
else:
    c2.warning("🔄 Fresh Data Downloaded")
    st.session_state.last_fetch_ts = current_fetch_ts
    needs_ai_recalc = True

tab1, tab_q, tab_f, tab_r, tab_k, tab_charts, tab_p = st.tabs([
    t['tab_tech'], t['tab_quantum'], t['tab_fund'], t['tab_risk'], 
    t['tab_kai'], "📊 Charts", t['tab_glossary']
])

with tab1:
    if isinstance(data, pd.DataFrame) and not data.empty:
        # --- 3. Persistent Session State for Signal calculations ---
        # We only recalculate the Artificial Intelligence and TradeBrain if the Cache TTL expired
        # or if the user changed the trading pair/timeframe.
        
        # We use a state key combining the timestamp + pair + tf to ensure freshness
        cache_key = f"{selected_pair_ui}_{selected_tf}_{current_fetch_ts}"
        
        if needs_ai_recalc or st.session_state.get('ai_key') != cache_key:
            # 1. Execute Brain
            brain = BrainClass(data)
            res = brain.analyze_market()
            
            # Execute Quantum Engine
            q_bridge = QuantumBridge()
            q_res = q_bridge.execute_pipeline(data)
            res['score'] = min(100.0, res['score'] * q_res['quantum_multiplier'])
            
            # --- API Risk Management & Kill Switch Intercept ---
            if 'pnl_history' not in st.session_state: 
                # Dummy PnL history for visualization of the kill switch active limits
                st.session_state.pnl_history = [-0.5, 0.2, -1.0, -1.8, -2.1]
                
            guardian = CapitalGuardian(max_daily_loss_pct=-2.0, max_position_size=2.0)
            current_pnl = st.session_state.pnl_history[-1] if len(st.session_state.pnl_history) > 0 else 0.0
            
            proposed_weight = q_res.get('optimal_position_size', 1.0)
            
            final_guardian_signal, capped_weight, guardian_status = guardian.evaluate_trade(
                raw_signal=res['signal'], # Base signal from brain
                q_position_weight=proposed_weight,
                current_daily_pnl_pct=current_pnl,
                lang=st.session_state.lang.lower()
            )
            
            q_res['optimal_position_size'] = capped_weight
            q_res['guardian_status'] = guardian_status
            
            if "HOLD" in final_guardian_signal or "CANCEL" in final_guardian_signal:
                res['signal'] = "WAIT (BLOCKED BY GUARDIAN)"
                res['reasons'].append(f"Guardian: {guardian_status}")
            # ---------------------------------------------------
            
            raw_signal = res['signal']
            if "BUY" in raw_signal: technical_signal = "BUY"
            elif "SELL" in raw_signal: technical_signal = "SELL"
            else: technical_signal = "WAIT"
            
            # Execute Cortex 
            final_decision, regime, ai_prediction, lstm_desc = "WAIT", "None", "None", "Unknown"
            lstm_prob, regime_id, regime_desc = 0.5, -1, "Unknown"
            book_data = {"outlook": "Disabled"}
            
            if technical_signal in ["BUY", "SELL"]:
                try:
                    cortex = CortexClass(data, oanda_token=oanda_token, oanda_id=oanda_id)
                    
                    if not LITE_MODE:
                        regime = cortex.detect_market_regime()
                        regime_id, regime_desc = cortex.hmm.detect_regime(data)
                        ai_prediction = cortex.predict_next_move()
                        
                        lstm_status, lstm_prob_val = cortex.lstm.predict_next_move(data)
                        lstm_desc = lstm_status
                        lstm_prob = lstm_prob_val
                    else:
                        regime, ai_prediction = "REMOTE_SENTINEL", "REMOTE_SENTINEL"
                        regime_id, regime_desc = -1, "Active on Linux Server"
                        lstm_desc, lstm_prob = "Calculation Offloaded", 50.0

                    oanda_sym = selected_pair_ui.replace("/", "_").replace(" ", "_")
                    book_data = cortex.analyze_order_book(oanda_sym)
                    
                    # --- AUTO EXECUTION SIGNAL (The Trigger) ---
                    if not LITE_MODE:
                        auto_signal, auto_reason = cortex.get_auto_execution_signal(data, res)
                    else:
                        auto_signal, auto_reason = "SENTINEL_WATCH", "AI Veto monitored by Linux Server"
                except Exception as e:
                    auto_signal, auto_reason = "ERROR", str(e)
                
                if regime in ["None", "UNKNOWN"] or ai_prediction in ["None", "UNKNOWN"]:
                    final_decision = f"⚠️ {technical_signal} (Low Confidence)"
                else:
                    if technical_signal == "BUY" and regime == "LOW_VOLATILITY" and ai_prediction == "UP":
                        final_decision = "🚀 EXECUTE LONG (High Probability)"
                    elif technical_signal == "SELL" and regime == "LOW_VOLATILITY" and ai_prediction == "DOWN":
                        final_decision = "📉 EXECUTE SHORT (High Probability)"
                    elif regime == "CRASH_MODE":
                        final_decision = "🛑 BLOCKED BY AI (High Risk Regime Detected)"
                    elif regime == "HIGH_VOLATILITY":
                        final_decision = "⚠️ CAUTION (Volatile Regime)"
                    else:
                        final_decision = f"⚠️ {technical_signal} (Mixed AI Validation)"
            else:
                final_decision = "⏳ NO TRADE (Waiting for Setup)"
                auto_signal, auto_reason = "STANDBY", "Brain Signal: WAIT"
            
            # Save strictly to memory state
            st.session_state.ai_results = {
                'res': res, 'raw_signal': raw_signal, 'final_decision': final_decision,
                'regime': regime, 'regime_id': regime_id, 'regime_desc': regime_desc,
                'ai_prediction': ai_prediction, 'lstm_prob': lstm_prob, 'lstm_desc': lstm_desc,
                'book_data': book_data, 'brain_df': brain.df, 'q_res': q_res,
                'auto_signal': auto_signal, 'auto_reason': auto_reason
            }
            st.session_state.ai_key = cache_key
            
            # Explicitly free memory for heavy models
            if 'cortex' in locals():
                del cortex
            del brain
            gc.collect()
            
        # Retrieve from state logic
        ar = st.session_state.ai_results
        
        # --- UI Rendering Layer ---
        st.markdown("## The Supervisor Handshake")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### ⚙️ Technical Layer (Brain)")
            st.metric("Brain Score", f"{ar['res']['score']:.1f} / 100", ar['raw_signal'])
            st.caption(f"{' | '.join(ar['res']['reasons'])}")
            
        with col2:
            st.markdown("### 🧠 Intelligence Layer (Cortex)")
            if ar['regime'] in ["None", "UNKNOWN"] or ar['ai_prediction'] in ["None", "UNKNOWN"]:
                st.write("**Market Mood:** ⚠️ Cortex Standby")
                st.write("**AI Confidence:** ⚠️ Awaiting VM Deployment")
                st.caption("ℹ️ HMM/LSTM models require Python ≤3.12. Full activation on GCP VM.")
            else:
                st.write(f"**Market Mood:** {ar['regime']}")
                st.write(f"**AI Bias:** {ar['ai_prediction']}")
            
            # --- Visual Atomic Signal ---
            if ar['auto_signal'] == "EXECUTE_LONG":
                st.success(f"**ATOMIC SIGNAL:**\n### 🚀 {ar['auto_signal']}")
            elif ar['auto_signal'] == "EXECUTE_SHORT":
                st.error(f"**ATOMIC SIGNAL:**\n### 📉 {ar['auto_signal']}")
            else:
                st.warning(f"**ATOMIC SIGNAL:**\n### ⏳ {ar['auto_signal']}")
            st.caption(f"Reason: {ar['auto_reason']}")
            
            st.info(f"**FINAL DECISION:**\n### {ar['final_decision']}")
            
        with st.expander("🔮 NivoCortex Deep Research Layer (Internal Stats)"):
            cx1, cx2, cx3 = st.columns(3)
            with cx1:
                st.markdown("**1. Market Regime (HMM)**")
                st.metric("Current State", f"Regime {ar['regime_id']}", ar['regime_desc'], delta_color="normal" if ar['regime_id'] < 2 else "inverse")
            with cx2:
                st.markdown("**2. Microstructure (DOM)**")
                if "error" in ar['book_data']:
                    st.metric("Bid/Ask Imbalance", "Error", ar['book_data']["error"])
                else:
                    st.metric("Bid/Ask Imbalance", ar['book_data'].get('outlook', 'Unknown'))
            with cx3:
                st.markdown("**3. AI Predictor (LSTM)**")
                if isinstance(ar['lstm_prob'], str): # If it returned an error string instead of float
                    st.metric("Next Candle Forecast", "Error", ar['lstm_prob'])
                else:
                    st.metric("Next Candle Forecast", f"{ar['lstm_prob']:.1f}% Bullish" if "Bullish" in ar['lstm_desc'] else f"{ar['lstm_prob']:.1f}% Bearish", ar['lstm_desc'], delta_color="normal" if "Bullish" in ar['lstm_desc'] else "inverse")
        
        # Quick Metrics (Optimized layout)
        st.markdown("<br>", unsafe_allow_html=True)
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric(t['current_price'], f"{ar['res']['current_price']:.5f}")
        rc2.metric("ADX (14) Strength", f"{ar['brain_df']['ADX'].iloc[-1]:.1f}")
        rc3.metric(t['stop_loss'], f"{ar['res']['stop_loss']:.5f}")
        rc4.metric(t['take_profit'], f"{ar['res']['take_profit']:.5f}")
    else:
        st.error("No data available for this pair/timeframe. Try a higher timeframe.")

with tab_f:
    st.markdown(f"### {t['news_title']}")
    st.metric(t['sentiment_overall'], f"{avg_s:.3f}", "Bullish" if avg_s > 0 else "Bearish")
    for n in news:
        icon = "🟢" if n['score'] > 0.1 else "🔴" if n['score'] < -0.1 else "⚪"
        st.write(f"{icon} **[{n['title']}]({n['link']})**")

with tab_charts:
    st.markdown("### 📊 Advanced Visuals & Price Action")
    if isinstance(data, pd.DataFrame) and not data.empty:
        ar = st.session_state.ai_results
        
        # Plotly Charts (Moved here to optimize performance of analysis tabs)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="Price"), row=1, col=1)
        
        if show_ema:
            fig.add_trace(go.Scatter(x=data.index, y=ar['brain_df']['EMA_200'], line={'color': '#8B5CF6', 'width': 2}, name='EMA 200'), row=1, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=ar['brain_df']['EMA_50'], line={'color': '#3B82F6', 'width': 1.5}, name='EMA 50'), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=data.index, y=ar['brain_df']['RSI'], line={'color': 'purple', 'width': 1.5}, name='RSI'), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
        
        fig.update_layout(template="plotly_dark", height=600, margin=dict(l=10, r=10, t=20, b=10), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, width='stretch')
        
    st.markdown("---")
    st.markdown(f"### {t['tab_season']}")
    if s_data is not None:
        avg_ret = s_data.groupby('Month')['Return'].mean()
        fig_sea = px.bar(avg_ret, title="Historical Avg Return by Month")
        st.plotly_chart(fig_sea, width='stretch')

with tab_k:
    st.markdown(f"### {t['tab_kai']}")
    if not gemini_key:
        st.info("Please provide a Gemini API Key in the sidebar to talk to Kai FX.")
    else:
        client = genai.Client(api_key=gemini_key)
        
        chat_container = st.container()
        for chat in st.session_state.chat_history:
            with chat_container.chat_message(chat['role']):
                st.write(chat['text'])
        
        if prompt := st.chat_input(t['kai_placeholder']):
            st.session_state.chat_history.append({"role": "user", "text": prompt})
            if len(st.session_state.chat_history) > 50:
                st.session_state.chat_history = st.session_state.chat_history[-50:]
                
            with chat_container.chat_message("user"):
                st.write(prompt)
                
            with chat_container.chat_message("assistant"):
                # Pass market context to Kai (Local and Global)
                global_ctx = ", ".join([f"{k}: {v['score']:.1f} ({v['signal']})" for k, v in global_results.items()])
                context = f"Selected Market: {selected_pair_ui}, Score: {ar['res']['score'] if 'ar' in locals() else 'N/A'}. Details: {ar['res']['reasons'] if 'ar' in locals() else ''}. ALL MARKETS SUMMARY: {global_ctx}"
                full_prompt = f"System Context: {context}\nUser: {prompt}\nAnalyze the best opportunities across all pairs if asked."
                
                # Resilient model cascade - All Free Tier, each with independent quota
                model_cascade = [
                    'gemini-2.5-flash',       # Smarter, primary
                    'gemini-2.0-flash',       # Fast, secondary
                    'gemini-2.0-flash-lite',  # Lightest, separate quota
                    'gemini-2.5-flash-lite',  # Light v2.5, separate quota
                    'gemini-flash-latest',    # Alias fallback
                ]
                response_text = None
                
                for model_name in model_cascade:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=full_prompt
                        )
                        response_text = response.text
                        break  # Success, exit cascade
                    except Exception as api_err:
                        if "429" in str(api_err) or "ResourceExhausted" in str(type(api_err).__name__):
                            continue  # Try next model in cascade
                        else:
                            response_text = f"⚠️ Kai FX Error: {api_err}"
                            break
                
                if response_text is None:
                    response_text = "⚠️ Kai FX is temporarily unavailable. Your Gemini API free tier daily quota has been exhausted across all models. Please wait ~1 minute or try again tomorrow. Your trading signals (Brain + Cortex) are NOT affected."
                
                st.write(response_text)
                st.session_state.chat_history.append({"role": "assistant", "text": response_text})
                if len(st.session_state.chat_history) > 50:
                    st.session_state.chat_history = st.session_state.chat_history[-50:]

with tab_p:
    p_tab, g_tab = st.tabs(["📜 Protocol", "📖 Glossary"])
    with p_tab:
        st.markdown("### Institutional Intelligence Protocol")
        st.write("- **Regime:** HQMM risk detection.")
        st.write("- **Reflexivity:** Sentiment/Price synergy.")
    with g_tab:
        st.markdown("### 📖 Nivo Glossary")
        st.write("- **EMA:** Exponential Moving Average.")
        st.write("- **RSI:** Relative Strength Index.")

with tab_q:
    st.markdown(f"### {t['tab_quantum']}")
    if 'ar' in locals() and 'q_res' in ar:
        q_res = ar['q_res']
        qc1, qc2, qc3 = st.columns(3)
        qc1.metric(t['quantum_multiplier'], f"{q_res.get('quantum_multiplier', 1.0):.2f}x")
        qc2.metric("Optimal Position Size", f"{q_res.get('optimal_position_size', 1.0):.2f}x Leverage")
        qc3.metric(t['quantum_direction'], f"{q_res.get('qlstm_bull_prob', 0.5)*100:.1f}%")
        
        st.markdown(f"#### {t['quantum_regime']}")
        probs = q_res.get('hqmm_probs', [0.33, 0.33, 0.34])
        labels = ["Low Volatility", "Trending", "Chaotic"]
        fig_q = px.bar(x=labels, y=probs, labels={'x': 'Regime', 'y': 'Probability'}, color=labels, title="HQMM State Vector", template="plotly_dark")
        fig_q.update_layout(height=400)
        st.plotly_chart(fig_q, width='stretch')
    else:
        st.info("Quantum engine calculating...")

with tab_r:
    st.markdown(f"### {t['tab_risk']}")
    # Initialize guardian_vis and pnl_hist outside the if block to ensure they are always defined
    guardian_vis = CapitalGuardian(max_daily_loss_pct=-2.0, max_position_size=2.0)
    pnl_hist = [0.0] # Default empty history
    
    if 'ar' in locals() and ar is not None and 'q_res' in ar:
        q_res = ar['q_res']
        
        # Display the Kill Switch Bilingual Status
        if "HALTED" in q_res.get('guardian_status', '') or "DETENIDO" in q_res.get('guardian_status', ''):
            st.error(f"**{t['risk_guardian']}:** {q_res.get('guardian_status', '')}")
        else:
            st.success(f"**{t['risk_guardian']}:** {q_res.get('guardian_status', '')}")
            
        # Use live PnL history if available from the engine, otherwise zero-state
        pnl_hist = q_res.get('pnl_history', [0.0])
        if not pnl_hist:
            pnl_hist = [0.0]
            
    fig_risk = guardian_vis.plot_risk_dashboard(pnl_hist, lang=st.session_state.lang.lower())
    st.plotly_chart(fig_risk, width='stretch')

    with st.expander("💼 Portafolio en Vivo (OANDA Open Positions)"):
        if oanda_token and oanda_id:
            try:
                from src.auto_execution import NivoAutoTrader
                trader = NivoAutoTrader(oanda_token, oanda_id)
                watchlist = [p.replace("/", "_") for p in pair_options]
                positions = []
                for p in watchlist:
                    perf = trader.get_position_performance(p)
                    if perf:
                        perf['Instrument'] = p.replace("_", "/")
                        positions.append(perf)
                if positions:
                    pos_df = pd.DataFrame(positions)
                    st.table(pos_df[['Instrument', 'units', 'pips', 'pnl_usd', 'entry_price', 'current_price']])
                else: st.info("No hay posiciones abiertas.")
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Conecte OANDA para ver posiciones.")

# --- Financial Disclaimer Footer ---
st.divider()
if st.session_state.lang == "ES":
    st.caption("⚠️ **Aviso Legal:** Nivo FX es una plataforma con fines puramente experimentales y didácticos.")
else:
    st.caption("⚠️ **Disclaimer:** Nivo FX is a platform strictly for experimental and educational purposes.")

# CortexClass alias for backward compatibility (defined at the end to avoid forward reference NameError)
CortexClass = NivoCortex
