#!/usr/bin/env python3
"""
Real-time traffic prediction API for use during simulation
"""

import joblib
import pandas as pd
from datetime import datetime
from data_loader import TrafficDataLoader

class TrafficPredictor:
    """
    Predicts traffic congestion 15-30 minutes ahead
    """
    
    def __init__(self, model_path='traffic_predictor_model.pkl'):
        print("Loading traffic prediction model...")
        try:
            self.model = joblib.load(model_path)
            self.loader = TrafficDataLoader()
            print("✓ Model loaded and ready")
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Model file '{model_path}' not found. "
                "Please run 'python3 train_predictor.py' first to train the model."
            )
        
        # Cache for storing recent vehicle counts (for prev_hour_vehicles feature)
        self.vehicle_history = {}
    
    def predict_congestion(self, intersection_id, current_time, vehicle_count):
        """
        Predict congestion level 15 minutes from now
        
        Args:
            intersection_id: string like 'B1', 'C1', etc.
            current_time: datetime object or simulation step
            vehicle_count: current number of vehicles at intersection
        
        Returns:
            float: predicted congestion level (0.0 to 1.0)
        """
        
        # Convert simulation step to datetime if needed
        if isinstance(current_time, (int, float)):
            # Assume simulation starts at 8 AM
            start_time = datetime(2025, 10, 17, 8, 0, 0)
            current_time = start_time + pd.Timedelta(seconds=current_time)
        
        # Get historical vehicle count for this intersection
        prev_hour_vehicles = self.vehicle_history.get(intersection_id, vehicle_count)
        
        # Prepare features
        features = self.loader.prepare_realtime_features(
            current_time=current_time,
            intersection_id=intersection_id,
            vehicle_count=vehicle_count,
            prev_hour_vehicles=prev_hour_vehicles
        )
        
        # Make prediction
        prediction = self.model.predict(features)[0]
        
        # Update history (store for next prediction)
        self.vehicle_history[intersection_id] = vehicle_count
        
        return prediction
    
    def predict_all_intersections(self, current_time, vehicle_counts):
        """
        Predict congestion for all intersections at once
        
        Args:
            current_time: datetime object
            vehicle_counts: dict like {'B1': 45, 'C1': 38, ...}
        
        Returns:
            dict: predictions like {'B1': 0.75, 'C1': 0.68, ...}
        """
        predictions = {}
        for intersection_id, vehicle_count in vehicle_counts.items():
            predictions[intersection_id] = self.predict_congestion(
                intersection_id, current_time, vehicle_count
            )
        return predictions
    
    def get_congestion_level_label(self, prediction):
        """Convert prediction to human-readable label"""
        if prediction >= 0.8:
            return "SEVERE"
        elif prediction >= 0.6:
            return "HEAVY"
        elif prediction >= 0.4:
            return "MODERATE"
        elif prediction >= 0.2:
            return "LIGHT"
        else:
            return "CLEAR"


# Test the predictor
if __name__ == "__main__":
    predictor = TrafficPredictor()
    
    # Test prediction
    test_time = datetime(2025, 10, 17, 8, 30, 0)  # Morning rush hour
    test_intersection = 'B1'  # Olympic corridor
    test_vehicle_count = 55
    
    prediction = predictor.predict_congestion(
        test_intersection,
        test_time,
        test_vehicle_count
    )
    
    level = predictor.get_congestion_level_label(prediction)
    
    print("\n" + "=" * 60)
    print("PREDICTION TEST")
    print("=" * 60)
    print(f"Time: {test_time}")
    print(f"Intersection: {test_intersection}")
    print(f"Current vehicles: {test_vehicle_count}")
    print(f"Predicted congestion: {prediction:.2f} ({level})")
    print("=" * 60)