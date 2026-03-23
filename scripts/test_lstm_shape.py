import numpy as np
from src.nivo_cortex import NivoCortex

cortex = NivoCortex()

# Simulate a sequence calculation
sequence = np.random.randn(20) # Simulate seq_norm
print("Testing prediction trajectory...")
pred = cortex.predict_lstm_trajectory(sequence)
print("Prediction: ", pred)
