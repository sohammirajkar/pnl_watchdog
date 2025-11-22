import numpy as np
import pickle
import os
from collections import deque
from sklearn.ensemble import IsolationForest
from typing import Dict, Any


class AIBrain:
    def __init__(self, model_path: str = "pnl_brain.pkl"):
        self.model_path = model_path

        # 1. STATISTICAL MEMORY (Short-term)
        # Keeps the last 100 trades to calculate rolling Z-Scores
        self.latency_window = deque(maxlen=100)
        self.slippage_window = deque(maxlen=100)

        # 2. ML MODEL (Long-term)
        # Isolation Forest: Excellent for anomaly detection in unsupervised data
        self.ml_model = IsolationForest(contamination=0.01, random_state=42)
        self.is_trained = False

        # Buffer to collect data before first training
        self.training_buffer = []

        # Attempt to load existing brain
        self.load()

    def learn(self, slippage: float, latency_ms: float):
        """
        Ingests new trade data to update statistical models and ML training buffer.
        """
        # Update Stats
        self.slippage_window.append(slippage)
        self.latency_window.append(latency_ms)

        # Update ML Buffer
        self.training_buffer.append([slippage, latency_ms])

        # Auto-Retrain ML model every 50 new trades
        if len(self.training_buffer) >= 50:
            self._retrain_model()

    def analyze(self, slippage: float, latency_ms: float) -> Dict[str, Any]:
        """
        Runs the trade through both Statistical and ML engines.
        """
        report = {
            "is_anomaly": False,
            "reasons": [],
            "confidence": 0.0
        }

        # --- CHECK 1: Statistical Z-Score (The "Speed" Check) ---
        if len(self.latency_window) > 10:
            lat_mean = np.mean(self.latency_window)
            lat_std = np.std(self.latency_window)

            # Avoid division by zero
            if lat_std > 0:
                z_score_lat = (latency_ms - lat_mean) / lat_std
                if z_score_lat > 3:  # 3 Sigma event (99.7% outlier)
                    report["is_anomaly"] = True
                    report["reasons"].append(
                        f"Latency Spike ({z_score_lat:.1f}x sigma)")

        # --- CHECK 2: ML Isolation Forest (The "Pattern" Check) ---
        if self.is_trained:
            # Prediction: 1 = Normal, -1 = Anomaly
            prediction = self.ml_model.predict([[slippage, latency_ms]])[0]

            if prediction == -1:
                report["is_anomaly"] = True
                score = self.ml_model.score_samples(
                    [[slippage, latency_ms]])[0]
                report["reasons"].append(
                    f"Unusual Pattern Detected (Score: {score:.2f})")

        return report

    def _retrain_model(self):
        """Re-fits the Isolation Forest on historical data."""
        try:
            print("🧠 AI Brain: Retraining ML model...")
            # Convert list to numpy array
            X = np.array(self.training_buffer)

            # Train the model
            self.ml_model.fit(X)
            self.is_trained = True
            self.save()  # Persist to disk

            # Clear buffer (or keep it if you want cumulative training)
            # Here we keep growing the dataset for better accuracy

        except Exception as e:
            print(f"❌ AI Training Failed: {e}")

    def save(self):
        """Saves the trained model to disk."""
        with open(self.model_path, "wb") as f:
            pickle.dump({
                "model": self.ml_model,
                "is_trained": self.is_trained,
                "buffer": self.training_buffer
            }, f)

    def load(self):
        """Loads the model from disk if exists."""
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)
                    self.ml_model = data["model"]
                    self.is_trained = data["is_trained"]
                    self.training_buffer = data.get("buffer", [])
                print("🧠 AI Brain: Loaded successfully.")
            except Exception:
                print("🧠 AI Brain: Starting fresh.")
