import numpy as np
import pandas as pd

class HybridQuantumHMM:
    def __init__(self, n_states=3):
        self.n_states = n_states
        # Quantum state probabilities vector (normalized)
        self.state_probs = np.ones(n_states) / n_states

    def detect_regime(self, df):
        """
        Returns a tuple of (regime_integer, probability_array)
        """
        if df is None or df.empty or 'Close' not in df.columns:
            return 0, self.state_probs
            
        returns = df['Close'].pct_change().fillna(0).values
        volatility = np.std(returns[-20:]) if len(returns) >= 20 else 0.001
        
        # Pseudo-quantum state transition based on volatility
        if volatility < 0.002: # Low Vol
            trans = np.array([0.7, 0.2, 0.1])
        elif volatility > 0.008: # High Vol / Crash
            trans = np.array([0.1, 0.3, 0.6])
        else: # Normal
            trans = np.array([0.2, 0.6, 0.2])
            
        # Update using a simple Markov step 
        self.state_probs = self.state_probs * 0.5 + trans * 0.5
        self.state_probs /= np.sum(self.state_probs)
        
        predicted_regime = int(np.argmax(self.state_probs))
        return predicted_regime, self.state_probs
