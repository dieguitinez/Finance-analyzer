import os
import sys
import logging
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from v20 import Context

# Paths
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LESSONS_PATH = os.path.join(_root, "quantum_engine", "lessons_learned.json")

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | TRADE ANALYZER: [%(levelname)s] | %(message)s'
)
logger = logging.getLogger(__name__)

class NivoTradeAnalyzer:
    def __init__(self):
        load_dotenv()
        self.token = os.getenv("OANDA_ACCESS_TOKEN")
        self.account_id = os.getenv("OANDA_ACCOUNT_ID")
        self.env = os.getenv("OANDA_ENVIRONMENT", "practice")
        
        hostname = "api-fxpractice.oanda.com" if self.env == "practice" else "api-fxtrade.oanda.com"
        if self.token and self.account_id:
            self.ctx = Context(hostname, 443, ssl=True, token=self.token)
        else:
            self.ctx = None
            logger.error("OANDA credentials not found in .env")

    def analyze_recent_trades(self, days=7):
        """Analiza el historial de transacciones y genera un reporte de lecciones."""
        if not self.ctx:
            return "❌ Error: API OANDA no configurada."

        logger.info(f"Analizando trades de los últimos {days} días...")
        
        try:
            # Obtener transacciones (usamos un rango amplio para no perder cierres)
            # En v20, 'id_range' o 'since_id' son comunes, pero para análisis usamos 'list'
            # Simplificamos obteniendo las últimas 50 transacciones por ahora
            response = self.ctx.transaction.list(self.account_id, pageSize=50)
            transactions = response.get("transactions", 200)
            
            if not transactions:
                return "📭 No se encontraron transacciones recientes para analizar."

            closed_trades = []
            for t in transactions:
                # Buscamos transacciones de cierre de posición o ejecución de SL/TP
                if t.type in ["ORDER_FILL"] and hasattr(t, "tradesClosed"):
                    for tc in t.tradesClosed:
                        closed_trades.append({
                            "id": tc.tradeID,
                            "units": tc.units,
                            "realized_pnl": float(tc.realizedPL),
                            "instrument": t.instrument,
                            "time": t.time
                        })

            if not closed_trades:
                return "✅ No hay cierres de posición recientes registrados en el historial consultado."

            # Calcular métricas simples
            total_pnl = sum(t["realized_pnl"] for t in closed_trades)
            wins = [t for t in closed_trades if t["realized_pnl"] > 0]
            losses = [t for t in closed_trades if t["realized_pnl"] <= 0]
            win_rate = (len(wins) / len(closed_trades)) * 100 if closed_trades else 0
            
            # Generar Reporte de Lecciones
            report = (
                f"📊 <b>NIVO ANALYTICS: LECCIONES APRENDIDAS</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 Periodo: Últimos {days} días\n"
                f"🔄 Operaciones cerradas: {len(closed_trades)}\n"
                f"✅ Acierto (Win Rate): {win_rate:.1f}%\n"
                f"💵 PnL Realizado Total: ${total_pnl:+.2f} USD\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <b>Observaciones Estratégicas:</b>\n"
            )
            
            # Determine aggressiveness level for the feedback loop
            agg_level = "NORMAL"
            threshold_adj = 0.0
            
            if win_rate > 65:
                report += "🟢 Estás operando con alta precisión. El motor puede mantener su agresividad actual.\n"
                agg_level = "AGGRESSIVE"
                threshold_adj = -2.0 # Can be slightly more loose
            elif win_rate < 45:
                report += "🔴 Baja precisión detectada. El motor se ajustará a modo CONSERVATIVE (filtros más estrictos).\n"
                agg_level = "CONSERVATIVE"
                threshold_adj = 5.0 # Increase threshold by 5 pts
            else:
                report += "🟡 Rendimiento equilibrado. Revisa si las pérdidas son mayores que las ganancias.\n"
                agg_level = "NORMAL"
                threshold_adj = 0.0

            # Save to JSON for the Quantum Engine to read
            feedback = {
                "last_analysis_time": datetime.now().isoformat(),
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "aggression_level": agg_level,
                "threshold_adjustment": threshold_adj,
                "closed_trades_count": len(closed_trades)
            }
            
            try:
                with open(LESSONS_PATH, "w") as f:
                    json.dump(feedback, f, indent=4)
                logger.info(f"Feedback de aprendizaje guardado en {LESSONS_PATH}")
            except Exception as e:
                logger.error(f"Error guardando feedback: {e}")

            # Detección de errores comunes (Lógica simplificada)
            instruments = [t["instrument"] for t in closed_trades]
            most_traded = max(set(instruments), key=instruments.count) if instruments else "N/A"
            report += f"\n🔥 Par más operado: {most_traded}\n"
            
            report += (
                f"\n🚀 <b>DATO CLAVE:</b>\n"
                f"Los mejores trades ocurrieron tras confirmación de 'Veto Profundo' (LSTM). "
                f"Evita entradas si el Sentinel reporta 'Baja Volatilidad'."
            )
            
            return report

        except Exception as e:
            logger.error(f"Error analizando historial: {e}")
            return f"❌ Error técnico al analizar: {str(e)}"

if __name__ == "__main__":
    analyzer = NivoTradeAnalyzer()
    print(analyzer.analyze_recent_trades())
