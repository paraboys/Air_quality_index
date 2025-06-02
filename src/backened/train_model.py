import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Input
from tensorflow.keras.optimizers import Adam
import warnings
import joblib # To save/load scaler
import tensorflow as tf # For saving Keras model
import os # Import os module to check for file existence

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

print("--- Starting AI Model Training for Multiple Pollutants ---")

MODEL_PATH = 'air_quality_model_multi.h5' # Changed model name to reflect multiple outputs
SCALER_PATH = 'scaler_multi.pkl' # Changed scaler name

# 1) Generate Synthetic Data with More Features and Variation
print("1) Generating synthetic data for NO2, PM2.5, PM10, O3, SO2, CO...")
np.random.seed(42) # for reproducibility

num_samples = 150000 # Increased samples for multiple pollutants
data = {
    'latitude': np.random.uniform(-90, 90, num_samples),
    'longitude': np.random.uniform(-180, 180, num_samples),
    'hour_of_day': np.random.randint(0, 24, num_samples), # 0-23 hours
    'day_of_week': np.random.randint(0, 7, num_samples),  # 0=Monday, 6=Sunday
}
df = pd.DataFrame(data)

# Simulate concentrations for multiple pollutants with varying patterns
# NO2 (Nitrogen Dioxide) - High near traffic, urban areas, daily cycle
no2_values = np.random.normal(30, 10, num_samples) # Base NO2
dist_sq_delhi = (df['latitude'] - 28.7)**2 + (df['longitude'] - 77.2)**2
no2_values += 150 * np.exp(-dist_sq_delhi / 50) + 50 * np.sin(df['hour_of_day'] * np.pi / 12) + 30 * np.cos(df['day_of_week'] * np.pi / 3.5)
dist_sq_la = (df['latitude'] - 34.05)**2 + (df['longitude'] - (-118.25))**2
no2_values += 80 * np.exp(-dist_sq_la / 70) + 30 * np.sin(df['hour_of_day'] * np.pi / 12)
dist_sq_ocean = (df['latitude'] - (-30))**2 + (df['longitude'] - (-100))**2
no2_values -= 100 * np.exp(-dist_sq_ocean / 30)
dist_sq_north = (df['latitude'] - 60)**2 + (df['longitude'] - 10)**2
no2_values -= 70 * np.exp(-dist_sq_north / 40)
df['no2_concentration'] = no2_values.clip(0, 500) # µg/m³

# PM2.5 (Particulate Matter 2.5) - Urban/industrial areas, heating seasons
pm25_values = np.random.normal(20, 8, num_samples)
pm25_values += 120 * np.exp(-dist_sq_delhi / 40) + 40 * np.sin(df['hour_of_day'] * np.pi / 10) # Higher in hotspot 1
pm25_values += 60 * np.exp(-dist_sq_la / 60) # Moderate in hotspot 2
df['pm25_concentration'] = pm25_values.clip(0, 300) # µg/m³

# PM10 (Particulate Matter 10) - Similar to PM2.5 but also dust/construction
pm10_values = np.random.normal(30, 12, num_samples)
pm10_values += 150 * np.exp(-dist_sq_delhi / 55) + 60 * np.sin(df['hour_of_day'] * np.pi / 10)
pm10_values += 80 * np.exp(-dist_sq_la / 75)
df['pm10_concentration'] = pm10_values.clip(0, 500) # µg/m³

# O3 (Ozone) - Higher in rural/suburban areas, peaks in afternoon
o3_values = np.random.normal(50, 15, num_samples)
# Hotspot 3: O3 high in sunny, less polluted areas, e.g., Mediterranean like Athens
dist_sq_athens = (df['latitude'] - 37.98) ** 2 + (df['longitude'] - 23.73) ** 2
o3_values += 70 * np.exp(-dist_sq_athens / 60) + 50 * np.sin((df['hour_of_day'] - 14) * np.pi / 12).clip(0, None) # Afternoon peak
o3_values -= 30 * np.exp(-dist_sq_delhi / 30) # Lower in heavy pollution centers
df['o3_concentration'] = o3_values.clip(0, 200) # µg/m³

# SO2 (Sulfur Dioxide) - Industrial areas, power plants
so2_values = np.random.normal(10, 5, num_samples)
# Hotspot 4: Industrial area (e.g., Ruhr area, Germany)
dist_sq_ruhr = (df['latitude'] - 51.45) ** 2 + (df['longitude'] - 7.01) ** 2
so2_values += 100 * np.exp(-dist_sq_ruhr / 30)
df['so2_concentration'] = so2_values.clip(0, 200) # µg/m³

# CO (Carbon Monoxide) - Traffic, incomplete combustion
co_values = np.random.normal(1.0, 0.5, num_samples)
co_values += 4 * np.exp(-dist_sq_delhi / 50) + 2 * np.sin(df['hour_of_day'] * np.pi / 12) # High near traffic centers
co_values += 2 * np.exp(-dist_sq_la / 70)
df['co_concentration'] = co_values.clip(0, 20) # mg/m³

print(f"Generated {len(df)} samples of synthetic multi-pollutant data.")
print(df.head())
print(f"NO2 Min: {df['no2_concentration'].min():.2f}, Max: {df['no2_concentration'].max():.2f}, Mean: {df['no2_concentration'].mean():.2f}")
print(f"PM2.5 Min: {df['pm25_concentration'].min():.2f}, Max: {df['pm25_concentration'].max():.2f}, Mean: {df['pm25_concentration'].mean():.2f}")
print(f"PM10 Min: {df['pm10_concentration'].min():.2f}, Max: {df['pm10_concentration'].max():.2f}, Mean: {df['pm10_concentration'].mean():.2f}")
print(f"O3 Min: {df['o3_concentration'].min():.2f}, Max: {df['o3_concentration'].max():.2f}, Mean: {df['o3_concentration'].mean():.2f}")
print(f"SO2 Min: {df['so2_concentration'].min():.2f}, Max: {df['so2_concentration'].max():.2f}, Mean: {df['so2_concentration'].mean():.2f}")
print(f"CO Min: {df['co_concentration'].min():.2f}, Max: {df['co_concentration'].max():.2f}, Mean: {df['co_concentration'].mean():.2f}")


# 2) Filter and Remove Missing Values (Conceptual for synthetic data)
print("\n2) Filtering and handling missing values (conceptual step for real data)...")
initial_rows = len(df)
df.dropna(inplace=True)
df = df[(df['latitude'] >= -90) & (df['latitude'] <= 90)]
df = df[(df['longitude'] >= -180) & (df['longitude'] <= 180)]
# Ensure all concentration values are non-negative
for col in ['no2_concentration', 'pm25_concentration', 'pm10_concentration',
            'o3_concentration', 'so2_concentration', 'co_concentration']:
    df = df[df[col] >= 0]

if len(df) < initial_rows:
    print(f"Removed {initial_rows - len(df)} rows with missing or invalid values.")
else:
    print("No missing or invalid values found in synthetic data.")

# 3) Extract Features (X) and Target (y)
print("\n3) Extracting features (X) and target (y)...")
X = df[['latitude', 'longitude', 'hour_of_day', 'day_of_week']]
y = df[['no2_concentration', 'pm25_concentration', 'pm10_concentration',
        'o3_concentration', 'so2_concentration', 'co_concentration']] # Multiple targets
print(f"Features (X) shape: {X.shape}")
print(f"Target (y) shape: {y.shape}")

# 4) Split Data into Training (80%) and Testing (20%) Sets
print("\n4) Splitting data into training (80%) and testing (20%) sets...")
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"X_train shape: {X_train.shape}, y_train shape: {y_train.shape}")
print(f"X_test shape: {X_test.shape}, y_test shape: {y_test.shape}")

# 5) Scale Features
print("\n5) Scaling features using StandardScaler...")
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
print("Features scaled successfully.")

# 6) Build and Train a Deep Learning Model (Keras/TensorFlow)
print("\n6) Building and training a Deep Learning model (Keras/TensorFlow)...")
model = Sequential([
    Input(shape=(X_train_scaled.shape[1],)), # Input layer for 4 features
    Dense(256, activation='relu'), # Increased neurons
    Dense(128, activation='relu'),
    Dense(64, activation='relu'),
    Dense(6, activation='linear') # Output layer for 6 pollutants (regression)
])

# For multi-output regression, 'mse' loss is common. MAE for each output if needed.
# For simplicity, we'll use a single MSE loss for all outputs.
model.compile(optimizer=Adam(learning_rate=0.001), loss='mse', metrics=['mae'])
print("Model summary:")
model.summary()

# Train the model
history = model.fit(X_train_scaled, y_train,
                    epochs=150, # Increased epochs for multi-output
                    batch_size=128, # Increased batch size
                    validation_split=0.1,
                    verbose=0)

print("\nModel training complete.")
# Note: MAE here is the average MAE across all outputs
print(f"Final Training MAE: {history.history['mae'][-1]:.2f}")
print(f"Final Validation MAE: {history.history['val_mae'][-1]:.2f}")

# 7) Evaluate the model on the test set
print("\n7) Evaluating the model on the test set...")
loss, mae = model.evaluate(X_test_scaled, y_test, verbose=0)
print(f"Test Loss (MSE): {loss:.2f}")
print(f"Test MAE (Mean Absolute Error, averaged across outputs): {mae:.2f}")

# 8) Save the scaler and model
print("\n8) Saving model and scaler...")
joblib.dump(scaler, SCALER_PATH)
tf.keras.models.save_model(model, MODEL_PATH)
print(f"Model saved to {MODEL_PATH}")
print(f"Scaler saved to {SCALER_PATH}")

print("\n--- AI Model Training for Multiple Pollutants Complete ---")