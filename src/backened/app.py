import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests # Used for making HTTP requests to OpenAQ API
import google.generativeai as genai # For Gemini API
from dotenv import load_dotenv # Used to load environment variables from a .env file
import datetime # For handling timestamps

# Load environment variables from .env file (if you have one)
load_dotenv()

app = Flask(__name__)
CORS(app) # Enable CORS for all routes, allowing your React frontend to connect

# --- API Key Configuration ---
# IMPORTANT: It's best practice to load API keys from environment variables
# For local development, set them in your terminal before running app.py, e.g.:
# For Linux/macOS: export OPENAQ_API_KEY="YOUR_OPENAQ_API_KEY"
#                 export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
# For Windows (CMD): set OPENAQ_API_KEY="YOUR_OPENAQ_API_KEY"
#                   set GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
# For Windows (PowerShell): $env:OPENAQ_API_KEY="YOUR_OPENAQ_API_KEY"
#                           $env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
# Or, ensure your .env file in the same directory contains:
# OPENAQ_API_KEY="YOUR_OPENAQ_API_KEY"
# GEMINI_API_KEY="YOUR_GEMINI_API_KEY"

OPENAQ_API_KEY = os.getenv('OPENAQ_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Initialize clients
model = None # For Gemini

if not OPENAQ_API_KEY or OPENAQ_API_KEY == "YOUR_OPENAQ_API_KEY":
    print("CRITICAL ERROR: OPENAQ_API_KEY environment variable is not set or is using the placeholder.")
    print("Please sign up at openaq.org for a free key and set it: export OPENAQ_API_KEY='YOUR_KEY'")
else:
    print("OpenAQ API Key found. Attempting to use OpenAQ API.")

if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
    print("CRITICAL ERROR: GEMINI_API_KEY environment variable is not set or is using the placeholder.")
    print("Please set it: export GEMINI_API_KEY='YOUR_ACTUAL_KEY'")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        print("Google Gemini API client initialized.")
    except Exception as e:
        print(f"ERROR: Failed to initialize Google Gemini API client. Check your GEMINI_API_KEY. Error: {e}")


# --- AQI Category Mapping (consistent with frontend) ---
AQI_CATEGORIES = {
    'Good': {'color': '#00e400', 'severity': 1},
    'Moderate': {'color': '#ffff00', 'severity': 2},
    'Unhealthy for Sensitive Groups': {'color': '#ff7e00', 'severity': 3},
    'Unhealthy': {'color': '#ff0000', 'severity': 4},
    'Very Unhealthy': {'color': '#8f3f97', 'severity': 5},
    'Hazardous': {'color': '#7e0023', 'severity': 6},
    'Unknown': {'color': '#6b7280', 'severity': 0}
}

def get_aqi_category_color(category):
    return AQI_CATEGORIES.get(category, {}).get('color', '#6b7280')

# Define AQI category functions based on common standards (e.g., US EPA) for common pollutants
# These are approximate and might need adjustment based on specific regional standards.
# Units from OpenAQ can vary, but generally PM2.5/PM10 are ug/m^3, CO mg/m^3, others ug/m^3 or ppb.
# We'll assume ug/m^3 for all except CO (mg/m^3) for these functions.

def get_aqi_category_no2(concentration_ugm3): # NO2 in ug/m^3
    if concentration_ugm3 is None: return 'Unknown'
    if concentration_ugm3 <= 80: return 'Good'
    if concentration_ugm3 <= 160: return 'Moderate'
    if concentration_ugm3 <= 240: return 'Unhealthy for Sensitive Groups'
    if concentration_ugm3 <= 320: return 'Unhealthy'
    if concentration_ugm3 <= 400: return 'Very Unhealthy'
    return 'Hazardous'

def get_aqi_category_pm25(concentration_ugm3): # PM2.5 in ug/m^3
    if concentration_ugm3 is None: return 'Unknown'
    if concentration_ugm3 <= 12.0: return 'Good'
    if concentration_ugm3 <= 35.4: return 'Moderate'
    if concentration_ugm3 <= 55.4: return 'Unhealthy for Sensitive Groups'
    if concentration_ugm3 <= 150.4: return 'Unhealthy'
    if concentration_ugm3 <= 250.4: return 'Very Unhealthy'
    return 'Hazardous'

def get_aqi_category_pm10(concentration_ugm3): # PM10 in ug/m^3
    if concentration_ugm3 is None: return 'Unknown'
    if concentration_ugm3 <= 54: return 'Good'
    if concentration_ugm3 <= 154: return 'Moderate'
    if concentration_ugm3 <= 254: return 'Unhealthy for Sensitive Groups'
    if concentration_ugm3 <= 354: return 'Unhealthy'
    if concentration_ugm3 <= 424: return 'Very Unhealthy'
    return 'Hazardous'

def get_aqi_category_o3(concentration_ugm3): # O3 in ug/m^3
    if concentration_ugm3 is None: return 'Unknown'
    if concentration_ugm3 <= 100: return 'Good'
    if concentration_ugm3 <= 160: return 'Moderate'
    if concentration_ugm3 <= 200: return 'Unhealthy for Sensitive Groups'
    if concentration_ugm3 <= 240: return 'Unhealthy'
    if concentration_ugm3 <= 400: return 'Very Unhealthy'
    return 'Hazardous'

def get_aqi_category_so2(concentration_ugm3): # SO2 in ug/m^3
    if concentration_ugm3 is None: return 'Unknown'
    if concentration_ugm3 <= 75: return 'Good'
    if concentration_ugm3 <= 180: return 'Moderate'
    if concentration_ugm3 <= 300: return 'Unhealthy for Sensitive Groups'
    if concentration_ugm3 <= 600: return 'Unhealthy'
    if concentration_ugm3 <= 800: return 'Very Unhealthy'
    return 'Hazardous'

def get_aqi_category_co(concentration_mgm3): # CO in mg/m^3
    if concentration_mgm3 is None: return 'Unknown'
    if concentration_mgm3 <= 4.4: return 'Good'
    if concentration_mgm3 <= 9.4: return 'Moderate'
    if concentration_mgm3 <= 12.4: return 'Unhealthy for Sensitive Groups'
    if concentration_mgm3 <= 15.4: return 'Unhealthy'
    if concentration_mgm3 <= 30.4: return 'Very Unhealthy'
    return 'Hazardous'

def get_overall_aqi_category(pollutant_data):
    """
    Determines the overall AQI category based on the worst pollutant.
    """
    if not pollutant_data:
        return {'category': 'Unknown', 'color': AQI_CATEGORIES['Unknown']['color']}

    worst_category = 'Good'
    worst_severity = 0

    categories_with_details = [
        (get_aqi_category_no2(pollutant_data.get('no2')), 'NO2'),
        (get_aqi_category_pm25(pollutant_data.get('pm25')), 'PM2.5'),
        (get_aqi_category_pm10(pollutant_data.get('pm10')), 'PM10'),
        (get_aqi_category_o3(pollutant_data.get('o3')), 'O3'),
        (get_aqi_category_so2(pollutant_data.get('so2')), 'SO2'),
        (get_aqi_category_co(pollutant_data.get('co')), 'CO'),
    ]

    for cat, pollutant_type in categories_with_details:
        severity = AQI_CATEGORIES.get(cat, {}).get('severity', 0)
        if severity > worst_severity:
            worst_severity = severity
            worst_category = cat

    return {
        'category': worst_category,
        'color': AQI_CATEGORIES.get(worst_category, {}).get('color', AQI_CATEGORIES['Unknown']['color'])
    }

def convert_concentration(value, unit, parameter):
    """
    Converts OpenAQ units to a standard (ug/m^3 or mg/m^3 for CO) for AQI calculation.
    OpenAQ can return various units (e.g., "ppb", "ppm", "ug/m3", "mg/m3").
    This is a simplified conversion, actual conversions depend on temperature/pressure.
    Assuming standard conditions for these conversions (approx. 25C, 1 atm).
    """
    if value is None:
        return None

    if unit in ['ug/m3', 'µg/m³']:
        return value
    elif unit == 'mg/m3' and parameter != 'co': # Only CO stays mg/m3
        return value * 1000 # mg/m3 to ug/m3
    elif unit == 'ppm':
        if parameter == 'co': # CO: 1 ppm = ~1.145 mg/m^3
            return value * 1.145
        elif parameter == 'o3': # O3: 1 ppm = ~1960 ug/m^3
            return value * 1960
        elif parameter == 'so2': # SO2: 1 ppm = ~2620 ug/m^3
            return value * 2620
        elif parameter == 'no2': # NO2: 1 ppm = ~1880 ug/m^3
            return value * 1880
        return None # Unhandled ppm for other pollutants
    elif unit == 'ppb':
        if parameter == 'o3': # O3: 1 ppb = ~1.96 ug/m^3
            return value * 1.96
        elif parameter == 'so2': # SO2: 1 ppb = ~2.62 ug/m^3
            return value * 2.62
        elif parameter == 'no2': # NO2: 1 ppb = ~1.88 ug/m^3
            return value * 1.88
        return None # Unhandled ppb for other pollutants
    elif unit == 'ng/m3': # Nanograms to micrograms
        return value / 1000
    return None # Unhandled unit


def get_mock_prediction(latitude, longitude):
    """
    Provides mock data for demonstration or fallback if APIs fail.
    In a real scenario, this would involve a trained ML model.
    """
    import random
    mock_data = {
        'no2': random.uniform(20, 100),
        'pm25': random.uniform(5, 50),
        'pm10': random.uniform(10, 100),
        'o3': random.uniform(30, 80),
        'so2': random.uniform(10, 60),
        'co': random.uniform(0.5, 5.0),
        'source': 'AI Model Prediction (Mock Data)',
        'date_utc': None # AI model might not have a specific 'last updated' time like live data
    }
    return mock_data

@app.route('/predict_single_point', methods=['POST'])
def predict_single_point():
    data = request.get_json()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    country = data.get('country_code', 'IN') # Assuming India as default if not specified

    if not all([latitude, longitude]):
        return jsonify({"error": "Missing latitude or longitude"}), 400

    aqi_data = {}
    source = "AI Model Prediction (Mock Data)" # Default to AI model mock
    date_utc = None
    overall_aqi_category = 'Unknown'
    overall_aqi_color = AQI_CATEGORIES['Unknown']['color']

    if OPENAQ_API_KEY: # Only try to use OpenAQ API if key is available
        try:
            # OpenAQ v3 API endpoint for latest measurements by coordinates
            # Requires a radius parameter and limit.
            openaq_url = "https://api.openaq.org/v3/locations" # This endpoint lists locations
            # To get *latest measurements* near a point, we typically use the /latest endpoint or locations with data=true
            # Let's try to get locations near the point with latest data
            headers = {'X-API-Key': OPENAQ_API_KEY}
            params = {
                'coordinates': f"{latitude},{longitude}",
                'radius': 10000, # 10 km radius
                'limit': 10, # Get up to 10 nearest stations
                'data': 'true', # Request locations with data
                'order_by': 'distance' # Order by distance to the point
            }
            response = requests.get(openaq_url, headers=headers, params=params, timeout=10)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            openaq_data = response.json()

            if openaq_data and 'results' in openaq_data and openaq_data['results']:
                # Iterate through results to find the most recent/relevant data
                found_live_data = False
                for location in openaq_data['results']:
                    if 'measurements' in location and location['measurements']:
                        for measurement in location['measurements']:
                            parameter = measurement.get('parameter', '').lower()
                            value = measurement.get('value')
                            unit = measurement.get('unit')
                            last_updated = measurement.get('last_updated')

                            converted_value = convert_concentration(value, unit, parameter)
                            if converted_value is not None:
                                # Prioritize common pollutants
                                if parameter == 'pm25': aqi_data['pm25'] = converted_value
                                elif parameter == 'pm10': aqi_data['pm10'] = converted_value
                                elif parameter == 'no2': aqi_data['no2'] = converted_value
                                elif parameter == 'o3': aqi_data['o3'] = converted_value
                                elif parameter == 'so2': aqi_data['so2'] = converted_value
                                elif parameter == 'co': aqi_data['co'] = converted_value

                            if last_updated:
                                # Use the latest timestamp found
                                if not date_utc or last_updated > date_utc:
                                    date_utc = last_updated
                        found_live_data = True
                    if found_live_data: # Once we have some data, break
                        break

                if found_live_data:
                    source = "Live (OpenAQ API)"
                    # Calculate overall AQI based on fetched data
                    temp_overall_result = get_overall_aqi_category(aqi_data)
                    overall_aqi_category = temp_overall_result['category']
                    overall_aqi_color = temp_overall_result['color']
                else:
                    print(f"DEBUG: No relevant measurements found from OpenAQ for Lat: {latitude}, Lng: {longitude}")


        except requests.exceptions.HTTPError as e:
            print(f"OpenAQ API HTTP Error for single point ({latitude}, {longitude}): {e.response.status_code} - {e.response.text}")
            source = f"AI Model Prediction (OpenAQ API HTTP Error: {e.response.status_code})"
        except requests.exceptions.ConnectionError as e:
            print(f"Network/Connection Error to OpenAQ API for single point ({latitude}, {longitude}): {e}")
            source = f"AI Model Prediction (OpenAQ Network Error)"
        except requests.exceptions.Timeout:
            print(f"OpenAQ API request timed out for single point ({latitude}, {longitude}).")
            source = "AI Model Prediction (OpenAQ Timeout)"
        except Exception as e:
            print(f"An unexpected error occurred during OpenAQ API call for single point ({latitude}, {longitude}): {e}")
            source = f"AI Model Prediction (Unexpected OpenAQ Error: {e})"
    else:
        source = "AI Model Prediction (OpenAQ API Key Missing)"

    # If no data from OpenAQ or an error occurred, fall back to mock data
    if not aqi_data or source.startswith("AI Model Prediction"):
        mock_pollutant_data = get_mock_prediction(latitude, longitude)
        aqi_data.update(mock_pollutant_data) # Use mock to fill any missing data
        temp_overall_result = get_overall_aqi_category(aqi_data)
        overall_aqi_category = temp_overall_result['category']
        overall_aqi_color = temp_overall_result['color']
        if not source.startswith("AI Model Prediction"): # Only overwrite if not already an error/mock source
            source = mock_pollutant_data.get('source')
        date_utc = mock_pollutant_data.get('date_utc')


    # Prepare response for frontend
    response_data = {
        'no2': aqi_data.get('no2'),
        'pm25': aqi_data.get('pm25'),
        'pm10': aqi_data.get('pm10'),
        'o3': aqi_data.get('o3'),
        'so2': aqi_data.get('so2'),
        'co': aqi_data.get('co'),
        'source': source,
        'date_utc': date_utc,
        'overallAqiCategory': overall_aqi_category,
        'overallAqiColor': overall_aqi_color
    }

    return jsonify(response_data)


@app.route('/predict_grid_data', methods=['POST'])
def predict_grid_data():
    data = request.get_json()
    resolution = data.get('resolution', 5) # Default resolution, e.g., 5 degrees
    # For grid data, it's generally impractical to query OpenAQ for every single point
    # Instead, we'll continue using the mock data for grid visualization for simplicity.
    # OpenAQ provides a /locations endpoint that can list stations, but retrieving
    # current measurements for all of them and then interpolating to a grid is complex.

    grid_data = []

    # Define a rough bounding box for demonstration
    min_lat, max_lat = -80, 80 # Avoid poles for typical AQI data
    min_lon, max_lon = -170, 170

    try:
        # Continue using mock data for grid visualization as OpenAQ for grid is complex
        for lat in range(min_lat, max_lat + 1, resolution):
            for lon in range(min_lon, max_lon + 1, resolution):
                pollutant_data = get_mock_prediction(lat, lon) # Use mock/AI prediction
                grid_data.append({
                    'lat': lat,
                    'lng': lon,
                    'no2': pollutant_data.get('no2'),
                    'pm25': pollutant_data.get('pm25'),
                    'pm10': pollutant_data.get('pm10'),
                    'o3': pollutant_data.get('o3'),
                    'so2': pollutant_data.get('so2'),
                    'co': pollutant_data.get('co'),
                    # No overall AQI category/color for grid points from backend
                    # Frontend will calculate it for display based on individual pollutants
                })
        return jsonify({"grid_data": grid_data})
    except Exception as e:
        print(f"An unexpected error occurred during grid data generation: {e}")
        return jsonify({
            "error": f"An unexpected error occurred while generating grid data: {e}",
            "grid_data": []
        }), 500


@app.route('/get_health_advice', methods=['POST'])
def get_health_advice():
    if model is None:
        return jsonify({"health_advice": "AI model not initialized. Cannot generate health advice."}), 500

    data = request.get_json()
    aqi_category = data.get('aqi_category')
    location_name = data.get('location_name', 'your selected location')
    data_source = data.get('data_source', 'Air Quality API') # This will be 'Live (OpenAQ API)' or 'AI Model Prediction'
    latitude = data.get('latitude')
    longitude = data.get('longitude')


    if not aqi_category:
        return jsonify({"health_advice": "Missing AQI category for health advice"}), 400

    prompt = f"""
    Based on the air quality category: '{aqi_category}', provide concise and practical health advice.
    The data for this location ({location_name}, Lat: {latitude:.2f}, Lng: {longitude:.2f}) was obtained from: {data_source}.
    Include general recommendations suitable for this category, such as advice on outdoor activities,
    vulnerable groups, and protective measures.
    Keep the advice to 2-3 short paragraphs, focusing on actionable steps.
    """
    try:
        response = model.generate_content(prompt)
        advice = response.text
        return jsonify({"health_advice": advice})
    except Exception as e:
        print(f"Error generating health advice from Gemini: {e}")
        error_message = str(e)
        if "API key" in error_message or "authentication" in error_message:
            error_message = "Gemini API key is incorrect or invalid. Please check your GEMINI_API_KEY."
        return jsonify({"health_advice": f"Failed to generate AI health advice: {error_message}. Please check your API key and try again."}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)