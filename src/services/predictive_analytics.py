# src/services/predictive_analytics.py
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import asyncio
from src.services.database import get_db
from src.database import crud
from src.services.monitoring import logger

class PredictiveAnalyticsService:
    """Machine learning models for predictive analytics"""
    
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.training_lock = asyncio.Lock()
        
        # Model paths
        self.model_paths = {
            "equipment_failure": "models/equipment_failure.pkl",
            "energy_forecast": "models/energy_forecast.pkl",
            "course_demand": "models/course_demand.pkl",
            "support_volume": "models/support_volume.pkl"
        }
    
    async def train_equipment_failure_model(self):
        """Train model to predict equipment failure"""
        async with get_db() as db:
            # Get historical equipment data
            equipment_data = await crud.get_equipment_historical_data(db, days=365)
            
            if len(equipment_data) < 100:
                logger.warning("Insufficient data for equipment failure model")
                return
            
            # Prepare features
            df = pd.DataFrame(equipment_data)
            
            features = [
                'days_since_maintenance',
                'usage_count_30d',
                'usage_count_7d',
                'avg_daily_usage',
                'equipment_age_days',
                'maintenance_count',
                'lab_id'
            ]
            
            X = df[features].values
            y = df['failed_within_7d'].values
            
            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Train model
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )
            
            model.fit(X_train, y_train)
            
            # Evaluate
            accuracy = model.score(X_test, y_test)
            logger.info(f"Equipment failure model accuracy: {accuracy:.2f}")
            
            # Save model
            self.models['equipment_failure'] = model
            self.scalers['equipment_failure'] = scaler
            
            joblib.dump(model, self.model_paths['equipment_failure'])
            joblib.dump(scaler, self.model_paths['equipment_failure'].replace('.pkl', '_scaler.pkl'))
    
    async def predict_equipment_failure(self, equipment_id: int) -> Dict[str, Any]:
        """Predict probability of equipment failure"""
        if 'equipment_failure' not in self.models:
            try:
                self.models['equipment_failure'] = joblib.load(self.model_paths['equipment_failure'])
                self.scalers['equipment_failure'] = joblib.load(
                    self.model_paths['equipment_failure'].replace('.pkl', '_scaler.pkl')
                )
            except:
                return {"probability": 0.5, "confidence": "low", "needs_training": True}
        
        async with get_db() as db:
            equipment = await crud.get_equipment_with_stats(db, equipment_id)
            
            if not equipment:
                return None
            
            # Prepare features
            features = np.array([[
                equipment.days_since_maintenance,
                equipment.usage_count_30d,
                equipment.usage_count_7d,
                equipment.avg_daily_usage,
                equipment.age_days,
                equipment.maintenance_count,
                equipment.lab_id
            ]])
            
            # Scale features
            features_scaled = self.scalers['equipment_failure'].transform(features)
            
            # Predict
            probability = self.models['equipment_failure'].predict_proba(features_scaled)[0, 1]
            
            # Determine confidence
            if probability > 0.8 or probability < 0.2:
                confidence = "high"
            elif probability > 0.6 or probability < 0.4:
                confidence = "medium"
            else:
                confidence = "low"
            
            return {
                "equipment_id": equipment_id,
                "failure_probability": float(probability),
                "confidence": confidence,
                "recommendation": self._get_failure_recommendation(probability),
                "maintenance_in_days": self._estimate_maintenance_days(probability)
            }
    
    def _get_failure_recommendation(self, probability: float) -> str:
        """Get recommendation based on failure probability"""
        if probability > 0.8:
            return "Immediate maintenance required - high risk of failure"
        elif probability > 0.6:
            return "Schedule maintenance within 7 days"
        elif probability > 0.4:
            return "Monitor closely, consider maintenance in 30 days"
        else:
            return "Equipment operating normally"
    
    def _estimate_maintenance_days(self, probability: float) -> int:
        """Estimate days until maintenance needed"""
        if probability > 0.8:
            return 1
        elif probability > 0.6:
            return 7
        elif probability > 0.4:
            return 30
        else:
            return 90
    
    async def train_energy_forecast_model(self):
        """Train model to forecast energy consumption"""
        async with get_db() as db:
            energy_data = await crud.get_energy_historical_data(db, days=365)
            
            if len(energy_data) < 1000:
                logger.warning("Insufficient data for energy forecast model")
                return
            
            df = pd.DataFrame(energy_data)
            
            # Create time-based features
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.dayofweek
            df['month'] = pd.to_datetime(df['timestamp']).dt.month
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
            
            features = ['hour', 'day_of_week', 'month', 'is_weekend', 'temperature', 'occupancy']
            X = df[features].values
            y = df['consumption'].values
            
            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Train model
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=15,
                random_state=42
            )
            
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )
            
            model.fit(X_train, y_train)
            
            # Evaluate
            score = model.score(X_test, y_test)
            logger.info(f"Energy forecast model R² score: {score:.2f}")
            
            # Save model
            self.models['energy_forecast'] = model
            self.scalers['energy_forecast'] = scaler
            
            joblib.dump(model, self.model_paths['energy_forecast'])
            joblib.dump(scaler, self.model_paths['energy_forecast'].replace('.pkl', '_scaler.pkl'))
    
    async def forecast_energy_consumption(self, days: int = 7) -> List[Dict]:
        """Forecast energy consumption for next N days"""
        if 'energy_forecast' not in self.models:
            try:
                self.models['energy_forecast'] = joblib.load(self.model_paths['energy_forecast'])
                self.scalers['energy_forecast'] = joblib.load(
                    self.model_paths['energy_forecast'].replace('.pkl', '_scaler.pkl')
                )
            except:
                return []
        
        forecasts = []
        now = datetime.utcnow()
        
        for i in range(days * 24):  # Hourly forecasts
            timestamp = now + timedelta(hours=i)
            
            # Create features
            features = np.array([[
                timestamp.hour,
                timestamp.weekday(),
                timestamp.month,
                1 if timestamp.weekday() in [5, 6] else 0,
                20,  # Average temperature (would come from weather API)
                50   # Average occupancy (would come from schedule)
            ]])
            
            # Scale features
            features_scaled = self.scalers['energy_forecast'].transform(features)
            
            # Predict
            consumption = self.models['energy_forecast'].predict(features_scaled)[0]
            
            forecasts.append({
                "timestamp": timestamp.isoformat(),
                "predicted_consumption": float(consumption),
                "confidence_interval": self._get_confidence_interval(consumption)
            })
        
        return forecasts
    
    def _get_confidence_interval(self, consumption: float) -> Dict:
        """Get confidence interval for prediction"""
        # Simplified - would come from model uncertainty
        return {
            "lower": consumption * 0.9,
            "upper": consumption * 1.1
        }
    
    async def train_support_volume_model(self):
        """Train model to predict support ticket volume"""
        async with get_db() as db:
            ticket_data = await crud.get_ticket_historical_data(db, days=365)
            
            if len(ticket_data) < 100:
                logger.warning("Insufficient data for support volume model")
                return
            
            df = pd.DataFrame(ticket_data)
            
            # Create features
            df['hour'] = pd.to_datetime(df['created_at']).dt.hour
            df['day_of_week'] = pd.to_datetime(df['created_at']).dt.dayofweek
            df['month'] = pd.to_datetime(df['created_at']).dt.month
            df['is_exam_period'] = self._is_exam_period(df['created_at'])
            
            features = ['hour', 'day_of_week', 'month', 'is_exam_period']
            X = df[features].values
            y = df['ticket_count'].values
            
            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Train model
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
            model.fit(X_scaled, y)
            
            # Save model
            self.models['support_volume'] = model
            self.scalers['support_volume'] = scaler
            
            joblib.dump(model, self.model_paths['support_volume'])
            joblib.dump(scaler, self.model_paths['support_volume'].replace('.pkl', '_scaler.pkl'))
    
    def _is_exam_period(self, dates) -> np.array:
        """Determine if dates are during exam periods"""
        # Simplified - would use academic calendar
        exam_periods = [
            (12, 1, 15),  # Dec 1-15
            (5, 1, 15)     # May 1-15
        ]
        
        result = []
        for date in dates:
            is_exam = False
            for month, start_day, end_day in exam_periods:
                if date.month == month and start_day <= date.day <= end_day:
                    is_exam = True
                    break
            result.append(1 if is_exam else 0)
        
        return np.array(result)