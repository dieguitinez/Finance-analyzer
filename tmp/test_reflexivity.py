import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from quantum_engine.quantum_bridge import QuantumBridge

def test_reflexivity():
    bridge = QuantumBridge()
    
    print("--- Nivo FX: Reflexivity Convergence Test ---")
    
    # Test Case 1: Synergy (Both Bullish)
    # tech=70, fund=70, regime=1 (trending), delta=60 (bullish), weight=1.0
    score_synergy = bridge.calculate_nivo_q_score(70, 70, 1, 60, 1.0)
    print(f"Synergy (Both Bullish) -> Tech:70, Fund:70 | Result: {score_synergy:.2f}")
    
    # Test Case 2: Synergy (Both Bearish)
    # tech=30, fund=30, regime=1 (trending), delta=40 (bearish), weight=1.0
    score_synergy_bear = bridge.calculate_nivo_q_score(30, 30, 1, 40, 1.0)
    print(f"Synergy (Both Bearish) -> Tech:30, Fund:30 | Result: {score_synergy_bear:.2f}")
    
    # Test Case 3: Friction (Divergence)
    # tech=70 (Bull), fund=30 (Bear), regime=1, delta=50, weight=1.0
    score_friction = bridge.calculate_nivo_q_score(70, 30, 1, 50, 1.0)
    print(f"Friction (Divergent) -> Tech:70, Fund:30 | Result: {score_friction:.2f}")

    # Test Case 4: Neutral alignment
    score_neutral = bridge.calculate_nivo_q_score(50, 50, 1, 50, 1.0)
    print(f"Neutral (No alignment) -> Tech:50, Fund:50 | Result: {score_neutral:.2f}")

    # Validation logic
    # Synergy calculation: base = 70*0.6 + 70*0.4 = 70. delta = 60*0.6 = 36. sum = 106. reflex = 1.25. result = 132.5 (clipped to 100)
    # Neutral calculation: base = 50*0.6 + 50*0.4 = 50. delta = 50*0.6 = 30. sum = 80. reflex = 1.0. result = 80.0
    
    print("\n--- Test Finished ---")

if __name__ == "__main__":
    test_reflexivity()
