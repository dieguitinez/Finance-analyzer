import os
import time
import json
from datetime import datetime

class NivoDiagnostic:
    def __init__(self):
        self.root = os.getcwd()
        self.fx_lessons = os.path.join(self.root, "quantum_engine", "lessons_learned.json")
        self.stock_log = os.path.join(self.root, "ai_stock_sentinel", "sentinel.log")
        self.stock_env = os.path.join(self.root, "ai_stock_sentinel", ".env")

    def check_health(self):
        print("🔍 --- NIVO SENTINEL DIAGNOSTIC (Ryzen 5 Local) ---")
        
        # 1. Check FX Learning Loop
        print("\n[FX BOT - Intelligence Suite]")
        if os.path.exists(self.fx_lessons):
            with open(self.fx_lessons, 'r') as f:
                data = json.load(f)
                ts = data.get("last_analysis_time", "Unknown")
                pnl = data.get("total_pnl", 0)
                adj = data.get("threshold_adjustment", 0)
                print(f"✅ Learning Loop: ACTIVE")
                print(f"🕒 Ultima actualización: {ts}")
                print(f"📊 PnL Reciente: ${pnl:+.2f}")
                print(f"🧠 Ajuste de Umbral: {adj:+.1f} pts")
        else:
            print("⚠️ Learning Loop: No se ha generado el archivo de lecciones todavía.")

        # 2. Check Stock Sentinel Log
        print("\n[STOCK BOT - AI Sentinel]")
        if os.path.exists(self.stock_log):
            mtime = os.path.getmtime(self.stock_log)
            last_edit = datetime.fromtimestamp(mtime)
            print(f"✅ Log System: ACTIVE")
            print(f"🕒 Log modificado hace: {datetime.now() - last_edit}")
            
            # Read last 3 lines
            with open(self.stock_log, 'r') as f:
                lines = f.readlines()
                print("📝 Last Event: " + (lines[-1].strip() if lines else "None"))
        else:
            print("❌ Log System: No se encuentra sentinel.log. ¿Está el bot iniciado?")

        # 3. Check Workspace Consistency
        print("\n[WORKSPACE - Security]")
        with open('.gitignore', 'r') as f:
            content = f.read()
            if "notebooklmcontext/" in content:
                print("✅ Privacy Filter: notebooklmcontext is correctly ignored.")
            else:
                print("❌ Privacy Filter: WARNING! notebooklmcontext is NOT in .gitignore.")

        print("\n✨ Diagnóstico completado.")

if __name__ == "__main__":
    diag = NivoDiagnostic()
    diag.check_health()
