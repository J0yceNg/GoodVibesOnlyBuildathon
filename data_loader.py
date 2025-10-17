#!/usr/bin/env python3
"""
Easy data loading for training and real-time prediction
"""

import pandas as pd
import numpy as np
from datetime import datetime

class TrafficDataLoader:
    """
    Loads and prepares traffic data for model training and prediction
    """
    
    def __init__(self, train_path='train_data.csv', test_path='test_data.csv'):
        print("Loading traffic data...")
        self.train_df = pd.read_csv(train_path, parse_dates=['timestamp'])
        self.test_df = pd.read_csv(test_path, parse_dates=['timestamp'])
        
        # Feature columns for ML model
        self.feature_cols = [
            'hour', 'minute', 'day_of_week', 
            'is_rush_hour', 'is_weekend', 'is_olympic_event',
            'vehicle_count', 'is_olympic_corridor',
            'hour_sin', 'hour_cos', 'prev_hour_vehicles'
        ]
        
        print(f"✓ Loaded {len(self.train_df):,} training records")
        print(f"✓ Loaded {len(self.test_df):,} test records")
    
    def get_training_data(self):
        """Get X, y for model training"""
        X = self.train_df[self.feature_cols]
        y = self.train_df['congestion_level']
        return X, y
    
    def get_test_data(self):
        """Get X, y for model evaluation"""
        X = self.test_df[self.feature_cols]
        y = self.test_df['congestion_level']
        return X, y
    
    def get_data_for_intersection(self, intersection_id, dataset='train'):
        """Get data for specific intersection"""
        df = self.train_df if dataset == 'train' else self.test_df
        subset = df[df['intersection_id'] == intersection_id]
        return subset
    
    def prepare_realtime_features(self, current_time, intersection_id, 
                                   vehicle_count, prev_hour_vehicles=None):
        """
        Prepare features for making a prediction during simulation
        
        Args:
            current_time: datetime object of current simulation time
            intersection_id: string like 'B1', 'C1', etc.
            vehicle_count: current number of vehicles at intersection
            prev_hour_vehicles: optional, vehicles from 1 hour ago
        
        Returns:
            pandas DataFrame with features ready for model.predict()
        """
        
        hour = current_time.hour
        minute = current_time.minute
        day_of_week = current_time.weekday()
        
        # Calculate derived features
        is_rush_hour = 1 if (7 <= hour <= 9) or (17 <= hour <= 19) else 0
        is_weekend = 1 if day_of_week >= 5 else 0
        is_olympic_event = 0  # Set to 1 during Olympic event simulation
        is_olympic_corridor = 1 if intersection_id in ['B1', 'C1'] else 0
        
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        
        # Use current vehicle count if no historical data
        if prev_hour_vehicles is None:
            prev_hour_vehicles = vehicle_count
        
        features = pd.DataFrame([{
            'hour': hour,
            'minute': minute,
            'day_of_week': day_of_week,
            'is_rush_hour': is_rush_hour,
            'is_weekend': is_weekend,
            'is_olympic_event': is_olympic_event,
            'vehicle_count': vehicle_count,
            'is_olympic_corridor': is_olympic_corridor,
            'hour_sin': hour_sin,
            'hour_cos': hour_cos,
            'prev_hour_vehicles': prev_hour_vehicles
        }])
        
        return features[self.feature_cols]
    
    def get_statistics(self):
        """Get data statistics for analysis"""
        stats = {
            'total_records': len(self.train_df),
            'intersections': self.train_df['intersection_id'].unique().tolist(),
            'date_range': (self.train_df['timestamp'].min(), 
                          self.train_df['timestamp'].max()),
            'avg_congestion': self.train_df['congestion_level'].mean(),
            'avg_vehicles': self.train_df['vehicle_count'].mean(),
        }
        return stats


# Quick test
if __name__ == "__main__":
    loader = TrafficDataLoader()
    
    X_train, y_train = loader.get_training_data()
    print(f"\n✓ Training features shape: {X_train.shape}")
    print(f"✓ Training target shape: {y_train.shape}")
    
    # Test real-time feature preparation
    features = loader.prepare_realtime_features(
        current_time=datetime(2025, 10, 17, 8, 30),
        intersection_id='B1',
        vehicle_count=45
    )
    print(f"\n✓ Real-time features:\n{features}")
    
    stats = loader.get_statistics()
    print(f"\n✓ Dataset statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")