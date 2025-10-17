#!/usr/bin/env python3
"""
Generate synthetic historical traffic data for training the prediction model
Matches the intersections in olympic_corridor.net.xml
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_traffic_data():
    """
    Generate 30 days of synthetic traffic data
    Based on the actual intersections in your SUMO network
    """
    
    # These match SUMO network node IDs
    intersections = ['A1', 'B0', 'B1', 'B2', 'C0', 'C1', 'C2', 'D1']
    
    data = []
    start_date = datetime(2025, 9, 1)  # Start 30 days ago
    
    print("Generating 30 days of traffic data...")
    
    for day in range(30):
        current_date = start_date + timedelta(days=day)
        is_weekend = current_date.weekday() >= 5
        
        # Simulate Olympic event days (days 15-25)
        is_olympic_event_day = 15 <= day <= 25
        
        # Generate data every 5 minutes throughout the day
        for hour in range(24):
            for minute in [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]:
                timestamp = current_date.replace(hour=hour, minute=minute)
                
                for intersection in intersections:
                    # Determine base congestion based on time and intersection
                    congestion, vehicle_count = calculate_base_traffic(
                        hour, intersection, is_weekend, is_olympic_event_day
                    )
                    
                    # Add randomness
                    congestion = np.clip(congestion + np.random.normal(0, 0.05), 0, 1)
                    vehicle_count = int(vehicle_count * (1 + np.random.normal(0, 0.15)))
                    
                    data.append({
                        'timestamp': timestamp,
                        'intersection_id': intersection,
                        'vehicle_count': max(0, vehicle_count),
                        'congestion_level': congestion,
                        'hour': hour,
                        'minute': minute,
                        'day_of_week': current_date.weekday(),
                        'is_weekend': is_weekend,
                        'is_olympic_event': is_olympic_event_day,
                        'is_rush_hour': 1 if (7 <= hour <= 9) or (17 <= hour <= 19) else 0
                    })
        
        if day % 5 == 0:
            print(f"  Generated day {day}/30")
    
    df = pd.DataFrame(data)
    print(f"\nGenerated {len(df)} traffic records")
    return df


def calculate_base_traffic(hour, intersection, is_weekend, is_olympic_event_day):
    """
    Calculate realistic base traffic based on time and location
    """
    
    # Olympic corridor intersections (B1, C1) have more traffic
    is_olympic_corridor = intersection in ['B1', 'C1']
    
    # Time-based traffic patterns
    if 7 <= hour <= 9:  # Morning rush
        base_congestion = 0.75 if is_olympic_corridor else 0.65
        base_vehicles = 65 if is_olympic_corridor else 50
    elif 10 <= hour <= 16:  # Daytime
        base_congestion = 0.45
        base_vehicles = 35
    elif 17 <= hour <= 19:  # Evening rush
        base_congestion = 0.80 if is_olympic_corridor else 0.70
        base_vehicles = 70 if is_olympic_corridor else 55
    elif 20 <= hour <= 22:  # Evening
        base_congestion = 0.35
        base_vehicles = 25
    else:  # Night/early morning
        base_congestion = 0.15
        base_vehicles = 10
    
    # Weekend adjustment
    if is_weekend:
        base_congestion *= 0.6
        base_vehicles = int(base_vehicles * 0.6)
    
    # Olympic event adjustment (increase traffic to venues)
    if is_olympic_event_day and is_olympic_corridor:
        # Heavy traffic 2 hours before typical event times
        if 12 <= hour <= 14 or 17 <= hour <= 20:
            base_congestion = min(0.95, base_congestion * 1.4)
            base_vehicles = int(base_vehicles * 1.5)
    
    return base_congestion, base_vehicles


def add_derived_features(df):
    """
    Add features that will help the model learn patterns
    """
    print("\nAdding derived features...")
    
    # Time-based features
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    
    # Intersection type (Olympic corridor vs other)
    df['is_olympic_corridor'] = df['intersection_id'].isin(['B1', 'C1']).astype(int)
    
    # Previous time period traffic (simulate historical pattern)
    # For each intersection, use previous hour's average
    df = df.sort_values(['intersection_id', 'timestamp'])
    df['prev_hour_vehicles'] = df.groupby('intersection_id')['vehicle_count'].shift(12)  # 12 * 5min = 1 hour
    df['prev_hour_vehicles'] = df['prev_hour_vehicles'].fillna(df['vehicle_count'])
    
    return df


def create_train_test_split(df):
    """
    Split data: first 24 days for training, last 6 days for testing
    This mimics real scenario: train on past, predict future
    """
    print("\nCreating train/test split...")
    
    # Sort by time
    df = df.sort_values('timestamp')
    
    # Time-based split (80/20)
    split_idx = int(len(df) * 0.8)
    train_df = df[:split_idx]
    test_df = df[split_idx:]
    
    print(f"Training data: {train_df['timestamp'].min()} to {train_df['timestamp'].max()}")
    print(f"Testing data: {test_df['timestamp'].min()} to {test_df['timestamp'].max()}")
    print(f"Train size: {len(train_df):,} records")
    print(f"Test size: {len(test_df):,} records")
    
    return train_df, test_df


def main():
    print("=" * 60)
    print("FairLane Traffic Data Generator")
    print("=" * 60)
    
    # Generate data
    df = generate_traffic_data()
    
    # Add features
    df = add_derived_features(df)
    
    # Save full dataset
    df.to_csv('historical_traffic.csv', index=False)
    print(f"\n✓ Saved: historical_traffic.csv ({len(df):,} rows)")
    
    # Create train/test split
    train_df, test_df = create_train_test_split(df)
    
    train_df.to_csv('train_data.csv', index=False)
    test_df.to_csv('test_data.csv', index=False)
    print(f"✓ Saved: train_data.csv ({len(train_df):,} rows)")
    print(f"✓ Saved: test_data.csv ({len(test_df):,} rows)")
    
    # Show sample
    print("\n" + "=" * 60)
    print("Sample data (first 5 rows):")
    print("=" * 60)
    print(train_df[['timestamp', 'intersection_id', 'vehicle_count', 
                    'congestion_level', 'is_rush_hour']].head())
    
    print("\n" + "=" * 60)
    print("Data generation complete! Ready for model training.")
    print("=" * 60)


if __name__ == "__main__":
    main()