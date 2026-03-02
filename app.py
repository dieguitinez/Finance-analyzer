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
    }
}
t = translations[st.session_state.lang]

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
        "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY", "XAU/USD", "BTC/USD"
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
    st.subheader("Watchdog & AI Config")
    use_alerts = st.checkbox("🔔 Enable Notifications", value=False)
    
    with st.expander("🔑 Institutional API (OANDA)"):
        oanda_token = st.text_input("OANDA Token", type="password", value=st.secrets.get("oanda_token", ""), help="Leave blank to use Fallback Data Engine")
        oanda_id = st.text_input("Account ID", value=st.secrets.get("oanda_account_id", ""))
        
    with st.expander("💬 Gemini 2.5 Flash API"):
        gemini_key = st.text_input("Gemini API Key", type="password", value=st.secrets.get("gemini_api_key", ""))

# --- 2. Data Caching (TTL) & Async Threading ---
@st.cache_data(ttl=60, show_spinner=False, max_entries=5)
def fetch_market_data(pair_name, tf, token, acc_id):
    """ Cached 60s. Fetches price array """
    engine = DataEngine({'token': token, 'account_id': acc_id} if token else None)
    return engine.fetch_data(DataEngine.get_symbol_map(pair_name), tf), time.time()

@st.cache_data(ttl=900, show_spinner=False, max_entries=5)
def fetch_news_data(pair_name):
    """ Cached 15m. Proxies to the shared FundamentalEngine """
    return FundamentalEngine.get_pair_sentiment(pair_name)

@st.cache_data(ttl=86400, show_spinner=False, max_entries=5)
def fetch_seasonality_data(pair_name):
    """ Cached 24h """
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
        
        data, current_fetch_ts = f_price.result()
        news, avg_s = f_news.result()
        s_data = f_season.result()

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

tab1, tab2, tab3, tab4, tab6, tab7, tab8, tab5 = st.tabs([
    t['tab_tech'], t['tab_fund'], t['tab_season'], t['tab_kai'], 
    t['tab_quantum'], t['tab_risk'], t['tab_protocol'], t['tab_glossary']
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
                    regime = cortex.detect_market_regime()
                    regime_id, regime_desc = cortex.hmm.detect_regime(data) # Fetching specific HMM logic values
                    ai_prediction = cortex.predict_next_move()
                    
                    lstm_status, lstm_prob_val = cortex.lstm.predict_next_move(data)
                    lstm_desc = lstm_status
                    lstm_prob = lstm_prob_val
                    
                    oanda_sym = selected_pair_ui.replace("/", "_").replace(" ", "_")
                    book_data = cortex.analyze_order_book(oanda_sym)
                    
                    # --- AUTO EXECUTION SIGNAL (The Trigger) ---
                    auto_signal, auto_reason = cortex.get_auto_execution_signal(data, res)
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
        
        # Quick Metrics
        st.markdown("<br>", unsafe_allow_html=True)
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric(t['current_price'], f"{ar['res']['current_price']:.5f}")
        rc2.metric("ADX (14) Strength", f"{ar['brain_df']['ADX'].iloc[-1]:.1f}")
        rc3.metric(t['stop_loss'], f"{ar['res']['stop_loss']:.5f}")
        rc4.metric(t['take_profit'], f"{ar['res']['take_profit']:.5f}")

        # Plotly Charts
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="Price"), row=1, col=1)
        
        if show_ema:
            fig.add_trace(go.Scatter(x=data.index, y=ar['brain_df']['EMA_200'], line={'color': '#8B5CF6', 'width': 2}, name='EMA 200'), row=1, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=ar['brain_df']['EMA_50'], line={'color': '#3B82F6', 'width': 1.5}, name='EMA 50'), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=data.index, y=ar['brain_df']['RSI'], line={'color': 'purple', 'width': 1.5}, name='RSI'), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
        
        fig.update_layout(template="plotly_dark", height=700, margin=dict(l=10, r=10, t=20, b=10), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, width='stretch')
        
    else:
        st.error("No data available for this pair/timeframe. Try a higher timeframe.")

with tab2:
    st.markdown(f"### {t['news_title']}")
    st.metric(t['sentiment_overall'], f"{avg_s:.3f}", "Bullish" if avg_s > 0 else "Bearish")
    for n in news:
        icon = "🟢" if n['score'] > 0.1 else "🔴" if n['score'] < -0.1 else "⚪"
        st.write(f"{icon} **[{n['title']}]({n['link']})**")

with tab3:
    st.markdown(f"### {t['tab_season']}")
    if s_data is not None:
        avg_ret = s_data.groupby('Month')['Return'].mean()
        fig_sea = px.bar(avg_ret, title="Historical Avg Return by Month")
        st.plotly_chart(fig_sea, width='stretch')

with tab4:
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
                # Pass market context to Kai
                context = f"Market: {selected_pair_ui}, Score: {ar['res']['score'] if 'ar' in locals() else 'N/A'}. Details: {ar['res']['reasons'] if 'ar' in locals() else ''}"
                full_prompt = f"System Context: {context}\nUser: {prompt}"
                
                # Resilient model cascade - All Free Tier, each with independent quota
                model_cascade = [
                    'gemini-2.0-flash',       # Fast, primary
                    'gemini-2.0-flash-lite',  # Lightest, separate quota
                    'gemini-2.5-flash',       # Smarter, separate quota
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

with tab8:
    if st.session_state.lang == 'EN':
        st.markdown("""
### 📜 Nivo Intelligence Protocol — The Nexus Workflow

The Nivo FX system executes a precise **5-Step Intelligence Nexus** every 60 seconds for each currency pair. This process merges institutional mathematical paradigms (Simons, Soros) with Deep Learning.

#### STEP 1: Structural Regime Analysis (Jim Simons Paradigm)
- **Engine:** `MarketRegimeDetector` (HQMM). **[QUANTUM ENGINE ACTIVE]**
- **Process:** We first classify the market into **Low Volatility**, **Trending**, or **Chaotic**.
- **Impact:** If the market is **Chaotic (Regime 2)**, the brain automatically dampens all signals to protect capital from erratic noise.

#### STEP 2: Linear Baseline Synchronization
- **Engine:** `NivoTradeBrain`.
- **Process:** Classical scan of Exponential Moving Averages (EMA 50/200), RSI, and MACD.
- **Goal:** Establishes the primary price direction based on mathematical momentum.

#### STEP 3: Fundamental Sentiment Filter
- **Engine:** `FundamentalEngine` (NLP Sentinel).
- **Process:** Real-time extraction of global news. VADER (Natural Language Processing) scores the news from -1 (Extremely Bearish) to +1 (Extremely Bullish).
- **Goal:** Determines if the global economic narrative supports the price movement.

#### STEP 4: Reflexivity Convergence (George Soros Paradigm)
- **Engine:** `QuantumBridge.calculate_nivo_q_score`. **[QUANTUM ENGINE ACTIVE]**
- **Logic:** 
    - **SYNERGY (+25% Boost):** If Step 2 (Price) and Step 3 (News) align, we detect a **Positive Feedback Loop**.
    - **FRICTION (-25% Dampening):** If they diverge, we assume the trend is unsustainable.
- **Impact:** Only high-convergence signals reach the execution threshold.

#### STEP 5: Deep Learning Veto (LSTM Neural Net)
- **Engine:** `CPUOptimizedLSTM`. **[QUANTUM ENGINE ACTIVE]**
- **Process:** A neural network analyzes the last 60 bars to predict the most likely "Next Candle".
- **Impact:** If the LSTM disagrees with the Technical + Fundamental logic, it issues a **Veto**, canceling the trade to avoid "Bull/Bear Traps".

---

### 🛡️ Final Execution Thresholds
- **Final Q-Score > 65:** Atomic Signal: **BUY**.
- **Final Q-Score < 35:** Atomic Signal: **SELL**.
- **Stop Loss:** **1.5x ATR** (Volatility buffer).
- **Take Profit:** **3.0x ATR** (Triple volatility target).
""")
    else:
        st.markdown("""
### 📜 Protocolo de Inteligencia Nivo — El Flujo Nexus

El sistema Nivo FX ejecuta un **Nexus de Inteligencia de 5 Pasos** cada 60 segundos para cada par de divisas. Este proceso fusiona paradigmas matemáticos institucionales (Simons, Soros) con el Deep Learning.

#### PASO 1: Análisis Estructural (Paradigma de Jim Simons)
- **Motor:** `MarketRegimeDetector` (HQMM). **[CÁLCULO CUÁNTICO ACTIVO]**
- **Proceso:** Clasificamos el mercado en **Baja Volatilidad**, **Tendencia** o **Caótico**.
- **Impacto:** Si el mercado es **Caótico (Régimen 2)**, el sistema reduce automáticamente todas las señales para proteger el capital del ruido errático.

#### PASO 2: Sincronización de Línea Base Lineal
- **Motor:** `NivoTradeBrain`.
- **Proceso:** Escaneo clásico de Medias Móviles Exponenciales (EMA 50/200), RSI y MACD.
- **Objetivo:** Establece la dirección primaria del precio basada en el impulso matemático.

#### PASO 3: Filtro Fundamental de Sentimiento
- **Motor:** `FundamentalEngine` (NLP Sentinel).
- **Proceso:** Extracción en tiempo real de noticias globales. VADER (Procesamiento de Lenguaje Natural) califica las noticias desde -1 (Extremadamente Bajista) hasta +1 (Extremadamente Alcista).
- **Objetivo:** Determina si la narrativa económica global respalda el movimiento del precio.

#### PASO 4: Convergencia de Reflexividad (Paradigma de George Soros)
- **Motor:** `QuantumBridge.calculate_nivo_q_score`. **[CÁLCULO CUÁNTICO ACTIVO]**
- **Lógica:** 
    - **SINERGIA (+25% de Aumento):** Si el Paso 2 (Precio) y el Paso 3 (Noticias) se alinean, detectamos un **Bucle de Retroalimentación Positiva**.
    - **FRICCIÓN (-25% de Reducción):** Si divergen, asumimos que la tendencia es insostenible.
- **Impacto:** Solo las señales de alta convergencia alcanzan el umbral de ejecución.

#### PASO 5: Veto de Deep Learning (Red Neuronal LSTM)
- **Motor:** `CPUOptimizedLSTM`. **[CÁLCULO CUÁNTICO ACTIVO]**
- **Proceso:** Una red neuronal analiza las últimas 60 barras para predecir la "Siguiente Vela" más probable.
- **Impacto:** Si la LSTM no está de acuerdo con la lógica Técnica + Fundamental, emite un **Veto**, cancelando la operación para evitar trampas de mercado.

---

### 🛡️ Umbrales de Ejecución Final
- **Score Q Final > 65:** Señal Atómica: **COMPRA**.
- **Score Q Final < 35:** Señal Atómica: **VENTA**.
- **Stop Loss:** **1.5x ATR** (Buffer de volatilidad).
- **Take Profit:** **3.0x ATR** (Objetivo de triple volatilidad).
""")

with tab5:
    if st.session_state.lang == 'EN':
        st.markdown("""
## 📖 Nivo FX Intelligence Suite — Glossary

### Currency Pairs
| Pair | Name | OANDA | Category | Precision |
|------|------|-------|----------|-----------|
| EUR/USD | Euro / US Dollar | EUR_USD | Major | 5 Decimals |
| GBP/USD | British Pound / US Dollar | GBP_USD | Major | 5 Decimals |
| USD/JPY | US Dollar / Japanese Yen | USD_JPY | Major | 3 Decimals |
| AUD/USD | Australian Dollar / US Dollar | AUD_USD | Major | 5 Decimals |
| USD/CAD | US Dollar / Canadian Dollar | USD_CAD | Major | 5 Decimals |
| NZD/USD | NZ Dollar / US Dollar | NZD_USD | Major | 5 Decimals |
| EUR/GBP | Euro / British Pound | EUR_GBP | Major | 5 Decimals |
| EUR/JPY | Euro / Japanese Yen | EUR_JPY | Minor | 3 Decimals |
| GBP/JPY | British Pound / Yen | GBP_JPY | Minor | 3 Decimals |
| XAU/USD | Gold | XAU_USD | Commodity | 3 Decimals |
| BTC/USD | Bitcoin | BTC_USD | Crypto | 5 Decimals (Mirror) |

### Technical Indicators (Brain)
| Indicator | Period | Signal | Weight |
|-----------|--------|--------|--------|
| **EMA 50/200** | 50 & 200 candles | Above EMA 200 = Bullish | 3.0 pts |
| **RSI** | 14 candles | <35 Oversold, >65 Overbought | 2.0 pts |
| **Bollinger Bands** | 20, 2σ | Band rejection = reversal | 2.0 pts |
| **MACD** | 12, 26, 9 | Crossover = momentum shift | 2.0 pts |
| **ATR** | 14 candles | Volatility for SL/TP | Risk Mgmt |
| **ADX** | 14 candles | >25 = Strong Trend | 1.0 pt |

### AI Layer (Cortex)
| Component | Technology | Output |
|-----------|-----------|--------|
| **HMM** | Hidden Markov Model | LOW_VOL / HIGH_VOL / CRASH |
| **LSTM** | PyTorch Neural Net | UP / DOWN prediction |
| **DOM** | OANDA Order Book | Bid/Ask imbalance ratio |
| **Swing Expansion** | Volatility Filter | 15 bps Threshold (Sentinel) |
| **Reflexivity** | Soros Paradigm | Sentiment + Technical synergy |

### Supervisor Handshake (Final Decision)
| Brain | Cortex Regime | LSTM | Decision |
|-------|-------------|------|----------|
| BUY | LOW_VOL | UP | 🚀 EXECUTE LONG |
| SELL | LOW_VOL | DOWN | 📉 EXECUTE SHORT |
| Any | CRASH | Any | 🛑 BLOCKED (AI Veto) |
| Any | HIGH_VOL | Any | ⚠️ CAUTION |
| WAIT | — | — | ⏳ NO TRADE |

### Acronyms
| Term | Meaning |
|------|---------|
| EMA | Exponential Moving Average |
| RSI | Relative Strength Index |
| MACD | Moving Average Convergence Divergence |
| ATR | Average True Range |
| ADX | Average Directional Index |
| BB | Bollinger Bands |
| HMM | Hidden Markov Model |
| LSTM | Long Short-Term Memory |
| DOM | Depth of Market |
| TTL | Time To Live (cache) |
| NLP | Natural Language Processing |
| SL | Stop Loss |
| TP | Take Profit |
| TS | Trailing Stop |
""")
    else:
        st.markdown("""
## 📖 Nivo FX Intelligence Suite — Glosario

### Pares de Divisas
| Par | Nombre | OANDA | Categoría | Decimals |
|-----|--------|-------|-----------|----------|
| EUR/USD | Euro / Dólar US | EUR_USD | Mayor | 5 Decimales |
| GBP/USD | Libra / Dólar US | GBP_USD | Mayor | 5 Decimales |
| USD/JPY | Dólar US / Yen | USD_JPY | Mayor | 3 Decimales |
| AUD/USD | Dólar Australiano / Dólar US | AUD_USD | Mayor | 5 Decimales |
| USD/CAD | Dólar US / Dólar Canadiense | USD_CAD | Mayor | 5 Decimales |
| NZD/USD | Dólar NZ / Dólar US | NZD_USD | Mayor | 5 Decimales |
| EUR/GBP | Euro / Libra | EUR_GBP | Mayor | 5 Decimales |
| EUR/JPY | Euro / Yen | EUR_JPY | Menor | 3 Decimales |
| GBP/JPY | Libra / Yen | GBP_JPY | Menor | 3 Decimales |
| XAU/USD | Oro | XAU_USD | Commodity | 3 Decimales |
| BTC/USD | Bitcoin | BTC_USD | Cripto | 5 Decimales (Espejo) |

### Indicadores Técnicos (Brain)
| Indicador | Período | Señal | Peso |
|-----------|---------|-------|------|
| **EMA 50/200** | 50 y 200 velas | Sobre EMA 200 = Alcista | 3.0 pts |
| **RSI** | 14 velas | <35 Sobreventa, >65 Sobrecompra | 2.0 pts |
| **Bandas Bollinger** | 20, 2σ | Rechazo de banda = reversión | 2.0 pts |
| **MACD** | 12, 26, 9 | Cruce = cambio de impulso | 2.0 pts |
| **ATR** | 14 velas | Volatilidad para SL/TP | Gestión Riesgo |
| **ADX** | 14 velas | >25 = Tendencia Fuerte | 1.0 pt |

### Capa de IA (Cortex)
| Componente | Tecnología | Salida |
|------------|-----------|--------|
| **HMM** | Modelo Oculto de Markov | BAJA_VOL / ALTA_VOL / CRASH |
| **LSTM** | Red Neuronal PyTorch | Predicción SUBE / BAJA |
| **DOM** | Libro de Órdenes OANDA | Ratio desequilibrio Bid/Ask |
| **Swing Expansion** | Filtro Volatilidad | Umbral 15 bps (Sentinel) |
| **Reflexividad** | Paradigma Soros | Sinergia Sentimiento + Técnico |

### Apretón de Manos del Supervisor (Decisión Final)
| Brain | Régimen Cortex | LSTM | Decisión |
|-------|---------------|------|----------|
| BUY | BAJA_VOL | UP | 🚀 EJECUTAR LARGO |
| SELL | BAJA_VOL | DOWN | 📉 EJECUTAR CORTO |
| Cualquier | CRASH | Cualquier | 🛑 BLOQUEADO (Veto IA) |
| Cualquier | ALTA_VOL | Cualquier | ⚠️ PRECAUCIÓN |
| WAIT | — | — | ⏳ SIN OPERACIÓN |

### Acrónimos
| Término | Significado |
|---------|-------------|
| EMA | Media Móvil Exponencial |
| RSI | Índice de Fuerza Relativa |
| MACD | Convergencia/Divergencia de Medias Móviles |
| ATR | Rango Verdadero Promedio |
| ADX | Índice Direccional Promedio |
| BB | Bandas de Bollinger |
| HMM | Modelo Oculto de Markov |
| LSTM | Memoria de Largo-Corto Plazo |
| DOM | Profundidad de Mercado |
| TTL | Tiempo de Vida (caché) |
| NLP | Procesamiento de Lenguaje Natural |
| SL | Stop Loss (Parar Pérdida) |
| TP | Take Profit (Límite de Ganancia) |
| TS | Trailing Stop (Stop Seguimiento) |
""")

with tab6:
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

with tab7:
    st.markdown(f"### {t['tab_risk']}")
    if 'ar' in locals() and ar is not None and 'q_res' in ar:
        q_res = ar['q_res']
        
        # Display the Kill Switch Bilingual Status
        if "HALTED" in q_res.get('guardian_status', '') or "DETENIDO" in q_res.get('guardian_status', ''):
            st.error(f"**{t['risk_guardian']}:** {q_res.get('guardian_status', '')}")
        else:
            st.success(f"**{t['risk_guardian']}:** {q_res.get('guardian_status', '')}")
            
        # Display the Plotly Dashboard
        guardian_vis = CapitalGuardian(max_daily_loss_pct=-2.0, max_position_size=2.0)
        
        # Use live PnL history if available from the engine, otherwise zero-state
        pnl_hist = q_res.get('pnl_history', [0.0])
        if not pnl_hist:
            pnl_hist = [0.0]
            
        fig_risk = guardian_vis.plot_risk_dashboard(pnl_hist, lang=st.session_state.lang.lower())
        st.plotly_chart(fig_risk, width='stretch')
    else:
        st.info("Risk Guardian standby...")

# --- Financial Disclaimer Footer ---
st.divider()
if st.session_state.lang == "ES":
    st.caption("⚠️ **Aviso Legal:** Nivo FX es una plataforma con fines puramente experimentales y didácticos. El material y los datos presentados aquí no constituyen asesoramiento financiero, recomendaciones de inversión ni incitación a la compra o venta de activos. Cualquier uso de esta información para operar en mercados reales es bajo el propio riesgo del usuario.")
else:
    st.caption("⚠️ **Disclaimer:** Nivo FX is a platform strictly for experimental and educational purposes. The material and data presented here do not constitute financial advice, investment recommendations, or an offer to buy or sell any assets. Any use of this information to trade in live markets is at the user's own risk.")
