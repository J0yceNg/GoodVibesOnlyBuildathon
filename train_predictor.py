#!/usr/bin/env python3
"""
Train the traffic congestion prediction model
"""

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import pandas as pd
import matplotlib.pyplot as plt
from data_loader import TrafficDataLoader

def train_model():
    """Train the congestion prediction model"""
    
    print("=" * 60)
    print("FairLane Traffic Prediction Model Training")
    print("=" * 60)
    
    # Load data
    loader = TrafficDataLoader()
    X_train, y_train = loader.get_training_data()
    X_test, y_test = loader.get_test_data()
    
    print(f"\nTraining set: {X_train.shape}")
    print(f"Test set: {X_test.shape}")
    
    # Train model
    print("\nTraining Random Forest model...")
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=15,
        min_samples_split=10,
        random_state=42,
        n_jobs=-1,
        verbose=1
    )
    
    model.fit(X_train, y_train)
    print("✓ Training complete!")
    
    # Evaluate
    print("\nEvaluating model...")
    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)
    
    train_mae = mean_absolute_error(y_train, train_pred)
    test_mae = mean_absolute_error(y_test, test_pred)
    train_r2 = r2_score(y_train, train_pred)
    test_r2 = r2_score(y_test, test_pred)
    
    print("\n" + "=" * 60)
    print("MODEL PERFORMANCE")
    print("=" * 60)
    print(f"Train MAE: {train_mae:.4f}")
    print(f"Test MAE:  {test_mae:.4f}")
    print(f"Train R²:  {train_r2:.4f}")
    print(f"Test R²:   {test_r2:.4f}")
    
    # Feature importance
    print("\n" + "=" * 60)
    print("TOP 5 MOST IMPORTANT FEATURES")
    print("=" * 60)
    feature_importance = pd.DataFrame({
        'feature': X_train.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(feature_importance.head())
    
    # Save model
    print("\nSaving model...")
    joblib.dump(model, 'traffic_predictor_model.pkl')
    print("✓ Saved: traffic_predictor_model.pkl")
    
    # Create visualizations
    create_visualizations(y_test, test_pred, feature_importance)
    
    return model


def create_visualizations(y_true, y_pred, feature_importance):
    """Create performance visualization plots"""
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Plot 1: Actual vs Predicted
    axes[0].scatter(y_true, y_pred, alpha=0.3, s=1)
    axes[0].plot([0, 1], [0, 1], 'r--', lw=2)
    axes[0].set_xlabel('Actual Congestion')
    axes[0].set_ylabel('Predicted Congestion')
    axes[0].set_title('Prediction Accuracy')
    axes[0].grid(True, alpha=0.3)
    
    # Plot 2: Feature Importance
    top_features = feature_importance.head(10)
    axes[1].barh(range(len(top_features)), top_features['importance'])
    axes[1].set_yticks(range(len(top_features)))
    axes[1].set_yticklabels(top_features['feature'])
    axes[1].set_xlabel('Importance')
    axes[1].set_title('Top 10 Feature Importance')
    axes[1].grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    plt.savefig('model_performance.png', dpi=150, bbox_inches='tight')
    print("✓ Saved: model_performance.png")
    plt.close()


if __name__ == "__main__":
    model = train_model()
    
    print("\n" + "=" * 60)
    print("✓ MODEL TRAINING COMPLETE!")
    print("✓ Ready to integrate with SUMO simulation")
    print("=" * 60)