#!/usr/bin/env python3
"""
Analyze why AI isn't taking action
"""

import pandas as pd

# Load prediction history
df = pd.read_csv('prediction_history.csv')

print("=" * 60)
print("AI PREDICTION ANALYSIS")
print("=" * 60)

# Summary statistics
print("\nPrediction Statistics:")
print(f"Total predictions: {len(df):,}")
print(f"Min prediction: {df['prediction'].min():.4f}")
print(f"Max prediction: {df['prediction'].max():.4f}")
print(f"Mean prediction: {df['prediction'].mean():.4f}")
print(f"Median prediction: {df['prediction'].median():.4f}")

# Check thresholds
severe_threshold = 0.80
heavy_threshold = 0.65

severe_count = (df['prediction'] >= severe_threshold).sum()
heavy_count = (df['prediction'] >= heavy_threshold).sum()

print(f"\nThreshold Analysis:")
print(f"Predictions >= 0.80 (SEVERE): {severe_count} ({100*severe_count/len(df):.1f}%)")
print(f"Predictions >= 0.65 (HEAVY): {heavy_count} ({100*heavy_count/len(df):.1f}%)")

# By intersection
print("\nPredictions by Intersection:")
intersection_stats = df.groupby('intersection')['prediction'].agg(['count', 'mean', 'max'])
print(intersection_stats)

# By congestion level
print("\nPredictions by Level:")
level_counts = df['level'].value_counts()
print(level_counts)

print("\n" + "=" * 60)