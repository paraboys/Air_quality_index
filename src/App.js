import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
// If you have custom CSS for Leaflet or your app, import it here:
// import './App.css';

// Fix for default Leaflet icon issues, essential for markers to show up
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon-2x.png',
    iconUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
});

// Define the base URL for your Flask backend
const BACKEND_URL = 'http://localhost:5000'; // Ensure this matches your Flask server's address

// Simplified AQI categories and colors for display and frontend-side calculations (for grid data)
// These ranges should ideally be consistent with your backend's AQI category functions.
const AQI_CATEGORIES = {
    'Good': { color: '#00e400', range: '0-40 (NO2), 0-12.0 (PM2.5), 0-54 (PM10), etc.' },
    'Moderate': { color: '#ffff00', range: '41-80 (NO2), 12.1-35.4 (PM2.5), 55-154 (PM10), etc.' },
    'Unhealthy for Sensitive Groups': { color: '#ff7e00', range: '81-120 (NO2), 35.5-55.4 (PM2.5), 155-254 (PM10), etc.' },
    'Unhealthy': { color: '#ff0000', range: '121-180 (NO2), 55.5-150.4 (PM2.5), 255-354 (PM10), etc.' },
    'Very Unhealthy': { color: '#8f3f97', range: '181-280 (NO2), 150.5-250.4 (PM2.5), 355-424 (PM10), etc.' },
    'Hazardous': { color: '#7e0023', range: '281-500+ (NO2), 250.5+ (PM2.5), 425+ (PM10), etc.' },
};

// Helper to get color based on AQI category string
function getAqiCategoryColor(category) {
    return AQI_CATEGORIES[category] ? AQI_CATEGORIES[category].color : '#6b7280'; // Default grey for unknown
}

// Frontend helper to get category for individual pollutant display/popup for grid points.
// IMPORTANT: This logic should ideally mirror your backend's `get_aqi_category_XXX` functions.
const getAqiCategoryForPollutant = (concentration, pollutantType) => {
    switch (pollutantType) {
        case 'NO2': // µg/m³
            if (concentration <= 40) return 'Good';
            if (concentration <= 80) return 'Moderate';
            if (concentration <= 120) return 'Unhealthy for Sensitive Groups';
            if (concentration <= 180) return 'Unhealthy';
            if (concentration <= 280) return 'Very Unhealthy';
            return 'Hazardous';
        case 'PM2.5': // µg/m³
            if (concentration <= 12.0) return 'Good';
            if (concentration <= 35.4) return 'Moderate';
            if (concentration <= 55.4) return 'Unhealthy for Sensitive Groups';
            if (concentration <= 150.4) return 'Unhealthy';
            if (concentration <= 250.4) return 'Very Unhealthy';
            return 'Hazardous';
        case 'PM10': // µg/m³
            if (concentration <= 54) return 'Good';
            if (concentration <= 154) return 'Moderate';
            if (concentration <= 254) return 'Unhealthy for Sensitive Groups';
            if (concentration <= 354) return 'Unhealthy';
            if (concentration <= 424) return 'Very Unhealthy';
            return 'Hazardous';
        case 'O3': // µg/m³
            if (concentration <= 100) return 'Good';
            if (concentration <= 160) return 'Moderate';
            if (concentration <= 200) return 'Unhealthy for Sensitive Groups';
            if (concentration <= 240) return 'Unhealthy';
            if (concentration <= 400) return 'Very Unhealthy';
            return 'Hazardous';
        case 'SO2': // µg/m³
            if (concentration <= 75) return 'Good';
            if (concentration <= 180) return 'Moderate';
            if (concentration <= 300) return 'Unhealthy for Sensitive Groups';
            if (concentration <= 600) return 'Unhealthy';
            if (concentration <= 800) return 'Very Unhealthy';
            return 'Hazardous';
        case 'CO': // mg/m³ - Note: Ensure consistency with backend's CO unit conversion.
            if (concentration <= 4.4) return 'Good';
            if (concentration <= 9.4) return 'Moderate';
            if (concentration <= 12.4) return 'Unhealthy for Sensitive Groups';
            if (concentration <= 15.4) return 'Unhealthy';
            if (concentration <= 30.4) return 'Very Unhealthy';
            return 'Hazardous';
        default:
            return 'Unknown';
    }
};

// Frontend helper to determine the worst overall AQI category from multiple pollutants.
// This is primarily used for coloring the *grid markers* as the backend only returns raw pollutant data for grid points.
// For single-point queries, the backend's `overallAqiCategory` and `overallAqiColor` are used directly.
const getOverallAqiCategoryFromPollutants = (pollutantData) => {
    const aqiSeverity = {
        'Good': 1, 'Moderate': 2, 'Unhealthy for Sensitive Groups': 3,
        'Unhealthy': 4, 'Very Unhealthy': 5, 'Hazardous': 6
    };

    let worstCategory = 'Good';
    let worstSeverity = 0;

    const categories = [
        getAqiCategoryForPollutant(pollutantData.no2, 'NO2'),
        getAqiCategoryForPollutant(pollutantData.pm25, 'PM2.5'),
        getAqiCategoryForPollutant(pollutantData.pm10, 'PM10'),
        getAqiCategoryForPollutant(pollutantData.o3, 'O3'),
        getAqiCategoryForPollutant(pollutantData.so2, 'SO2'),
        getAqiCategoryForPollutant(pollutantData.co, 'CO'),
    ];

    for (const cat of categories) {
        const severity = aqiSeverity[cat] || 0;
        if (severity > worstSeverity) {
            worstSeverity = severity;
            worstCategory = cat;
        }
    }
    return { category: worstCategory, color: getAqiCategoryColor(worstCategory) };
};

// Component to handle map clicks and trigger data fetching
function MapClickHandler({ setSelectedLocation, setSelectedPrediction, setOverallAqiCategory, setOverallAqiColor, setLoading, setHealthAdvice, setLocationNameFromClick, setGlobalMessage }) {
    const map = useMapEvents({
        click: async (e) => {
            setLoading(true);
            setGlobalMessage(''); // Clear any previous global messages
            setSelectedLocation({ lat: e.latlng.lat, lng: e.latlng.lng });
            const locationDisplayName = `Lat: ${e.latlng.lat.toFixed(2)}, Lng: ${e.latlng.lng.toFixed(2)}`;
            setLocationNameFromClick(locationDisplayName);
            setSelectedPrediction(null); // Clear previous prediction
            setHealthAdvice("Generating AI insight..."); // Clear and set loading state for insight

            try {
                // 1. Fetch single point AQI data (which includes overall AQI category/color from backend)
                const response = await fetch(`${BACKEND_URL}/predict_single_point`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ latitude: e.latlng.lat, longitude: e.latlng.lng })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                setSelectedPrediction(data);

                // Use the overall AQI from the backend response directly for the main display
                setOverallAqiCategory(data.overallAqiCategory || 'Unknown');
                setOverallAqiColor(data.overallAqiColor || '#6b7280');

                // 2. Fetch health advice using the overall category and data source from the AQI data
                const healthAdviceResponse = await fetch(`${BACKEND_URL}/get_health_advice`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        aqi_category: data.overallAqiCategory, // Use backend's category
                        location_name: locationDisplayName,
                        data_source: data.source, // Pass the data source (Google API or AI Model)
                        latitude: e.latlng.lat,
                        longitude: e.latlng.lng
                    })
                });

                if (!healthAdviceResponse.ok) {
                    const errorData = await healthAdviceResponse.json();
                    // Set health advice error message but don't stop AQI data display
                    setHealthAdvice(errorData.health_advice || `Failed to retrieve health advice. Status: ${healthAdviceResponse.status}`);
                    console.error("Error fetching health advice:", errorData.health_advice || `HTTP error! status: ${healthAdviceResponse.status}`);
                } else {
                    const healthAdviceData = await healthAdviceResponse.json();
                    setHealthAdvice(healthAdviceData.health_advice);
                }

            } catch (error) {
                console.error("Error fetching single point prediction or health advice:", error);
                setSelectedPrediction({ error: error.message || "Failed to load data." });
                setHealthAdvice("Could not retrieve AI insight due to an error.");
                setOverallAqiCategory('Unknown');
                setOverallAqiColor('#ccc');
                setGlobalMessage(`Error: ${error.message}`);
            } finally {
                setLoading(false);
            }
        },
    });
    return null;
}


function App() {
    // Dynamically inject Tailwind CSS and Inter font for self-contained immersive.
    // In a regular Create React App or Vite project, you would typically link these
    // in your public/index.html or import them directly.
    useEffect(() => {
        const tailwindScript = document.createElement('script');
        tailwindScript.src = 'https://cdn.tailwindcss.com';
        document.head.appendChild(tailwindScript);

        const interFontLink = document.createElement('link');
        interFontLink.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap';
        interFontLink.rel = 'stylesheet';
        document.head.appendChild(interFontLink);

        // Cleanup function for useEffect
        return () => {
            document.head.removeChild(tailwindScript);
            document.head.removeChild(interFontLink);
        };
    }, []); // Empty dependency array means this runs once on mount

    const [gridData, setGridData] = useState([]);
    const [selectedLocation, setSelectedLocation] = useState(null); // {lat, lng} of clicked/searched location
    const [locationName, setLocationName] = useState('your selected location'); // Name of clicked/searched location
    const [selectedPrediction, setSelectedPrediction] = useState(null); // Detailed pollutant data from single point query
    const [loading, setLoading] = useState(false);
    const [healthAdvice, setHealthAdvice] = useState("Click anywhere on the map or use the search bar to get air quality data and AI-generated insight!");
    const [overallAqiCategory, setOverallAqiCategory] = useState('N/A');
    const [overallAqiColor, setOverallAqiColor] = useState('#6b7280'); // Default grey for overall category header
    const [globalMessage, setGlobalMessage] = useState(''); // For general messages/errors (replaces alert)

    const [searchTerm, setSearchTerm] = useState(''); // State for search input
    const mapRef = useRef(null); // Ref to access the Leaflet map instance

    // Function to fetch and display air quality data for given coordinates
    const fetchAndDisplayAirQuality = async (lat, lng, name = `Lat: ${lat.toFixed(2)}, Lng: ${lng.toFixed(2)}`) => {
        setLoading(true);
        setGlobalMessage(''); // Clear any previous global messages
        setSelectedLocation({ lat, lng });
        setLocationName(name); // Update location name for display
        setSelectedPrediction(null); // Clear previous prediction
        setHealthAdvice("Generating AI insight...");

        // Pan map to the selected location
        if (mapRef.current) {
            mapRef.current.setView([lat, lng], 10); // Adjust zoom level as needed
        }

        try {
            // 1. Fetch single point AQI data (which includes overall AQI category/color from backend)
            const response = await fetch(`${BACKEND_URL}/predict_single_point`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ latitude: lat, longitude: lng })
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            setSelectedPrediction(data);

            // Use the overall AQI from the backend response directly for the main display
            setOverallAqiCategory(data.overallAqiCategory || 'Unknown');
            setOverallAqiColor(data.overallAqiColor || '#6b7280');

            // 2. Fetch health advice
            const healthAdviceResponse = await fetch(`${BACKEND_URL}/get_health_advice`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    aqi_category: data.overallAqiCategory, // Use backend's category
                    location_name: name, // Use the proper location name
                    data_source: data.source,
                    latitude: lat,
                    longitude: lng
                })
            });
            if (!healthAdviceResponse.ok) {
                const errorData = await healthAdviceResponse.json();
                setHealthAdvice(errorData.health_advice || `Failed to retrieve health advice. Status: ${healthAdviceResponse.status}`);
                console.error("Error fetching health advice:", errorData.health_advice || `HTTP error! status: ${healthAdviceResponse.status}`);
            } else {
                const healthAdviceData = await healthAdviceResponse.json();
                setHealthAdvice(healthAdviceData.health_advice);
            }

        } catch (error) {
            console.error("Error fetching single point prediction or health advice:", error);
            setSelectedPrediction({ error: error.message || "Failed to load data or advice." });
            setHealthAdvice("Could not retrieve AI insight due to an error.");
            setOverallAqiCategory('Unknown');
            setOverallAqiColor('#6b7280');
            setGlobalMessage(`Error: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };


    // Handle search input change
    const handleSearchChange = (event) => {
        setSearchTerm(event.target.value);
    };

    // Handle search submission
    const handleSearchSubmit = async (event) => {
        event.preventDefault(); // Prevent default form submission
        setGlobalMessage(''); // Clear previous messages

        if (!searchTerm.trim()) {
            setGlobalMessage('Please enter a location to search.');
            return;
        }

        setLoading(true);
        setSelectedPrediction(null); // Clear previous prediction
        setHealthAdvice("Searching for location and fetching data...");

        try {
            // Geocoding using Nominatim (OpenStreetMap)
            // IMPORTANT: Replace 'your_email@example.com' with a real, unique contact for your application.
            // This is required by OpenStreetMap's Nominatim usage policy.
            const nominatimResponse = await fetch(
                `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(searchTerm)}&format=json&limit=1`,
                {
                    headers: {
                        'User-Agent': 'AirQualityApp/1.0 (your_email@example.com)' // *** REPLACE THIS WITH YOUR EMAIL/APP ID ***
                    }
                }
            );

            if (!nominatimResponse.ok) {
                throw new Error(`Geocoding error! status: ${nominatimResponse.status}`);
            }
            const geoData = await nominatimResponse.json();

            if (geoData && geoData.length > 0) {
                const { lat, lon, display_name } = geoData[0];
                console.log(`Found location: ${display_name}, Lat: ${lat}, Lng: ${lon}`);
                await fetchAndDisplayAirQuality(parseFloat(lat), parseFloat(lon), display_name);
            } else {
                setGlobalMessage('Location not found. Please try a different search term.');
                setLoading(false);
                setHealthAdvice("Location not found.");
                setOverallAqiCategory('N/A');
                setOverallAqiColor('#6b7280');
            }
        } catch (error) {
            console.error("Error during geocoding or data fetch:", error);
            setGlobalMessage(`Failed to search for location: ${error.message}`);
            setLoading(false);
            setHealthAdvice("Error during location search or data retrieval.");
            setOverallAqiCategory('N/A');
            setOverallAqiColor('#6b7280');
        }
    };


    // Initial fetch of grid data (for background markers)
    useEffect(() => {
        const fetchGridData = async () => {
            try {
                const response = await fetch(`${BACKEND_URL}/predict_grid_data`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ resolution: 5 }) // Request 5-degree resolution data
                });
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                setGridData(data.grid_data);
            } catch (error) {
                console.error("Error fetching initial grid data:", error);
                setGlobalMessage(`Error loading initial grid data: ${error.message}. Grid markers might not appear.`);
            }
        };

        fetchGridData();
    }, []); // Empty dependency array means this runs once on mount

    // Function to format UTC timestamp
    const formatUtcDate = (utcString) => {
        if (!utcString) return 'N/A';
        try {
            const date = new Date(utcString);
            return date.toLocaleString(); // Formats to local date/time string
        } catch (e) {
            console.error("Error formatting date:", e);
            return utcString; // Return original if parsing fails
        }
    };

    // Helper to render pollutant details for the main display
    const renderPollutant = (name, value, pollutantType, unit = 'µg/m³') => {
        // Use frontend logic for category color, as the main display needs individual pollutant categories
        const category = getAqiCategoryForPollutant(value, pollutantType);
        const color = getAqiCategoryColor(category);
        return (
            <li className="flex justify-between items-center py-1">
                <span className="font-semibold text-gray-700">{name.toUpperCase()}:</span>
                <span className="text-gray-900">
                    {value !== undefined && value !== null ? value.toFixed(2) : 'N/A'} {unit}
                    (<span style={{ color: color }} className="font-medium">{category}</span>)
                </span>
            </li>
        );
    };


    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-100 to-indigo-200 p-4 sm:p-8 font-sans flex flex-col lg:flex-row gap-8">
            {/* Main content column (Map and Search) */}
            <div className="flex-1 bg-white rounded-xl shadow-xl p-6 sm:p-8 border border-indigo-200 flex flex-col">
                <h1 className="text-4xl sm:text-5xl font-extrabold text-center text-indigo-800 mb-6 drop-shadow-lg">
                    Global Air Quality Predictor
                </h1>
                <p className="text-center text-gray-600 mb-6">
                    Click anywhere on the map or use the search bar to get live air quality data (if available) or AI prediction for a specific location, and AI-generated health insight.
                </p>

                <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3 mb-6">
                    <input
                        type="text"
                        placeholder="Search for a city or area..."
                        value={searchTerm}
                        onChange={handleSearchChange}
                        className="flex-1 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition duration-200 shadow-sm"
                    />
                    <button
                        type="submit"
                        disabled={loading}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-lg shadow-md transition duration-300 ease-in-out transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                    >
                        {loading ? (
                            <svg className="animate-spin h-5 w-5 mr-3 text-white" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        ) : (
                            'Search'
                        )}
                    </button>
                </form>

                {globalMessage && (
                    <p className="text-red-600 bg-red-100 p-3 rounded-lg border border-red-200 mb-4 text-center">{globalMessage}</p>
                )}

                <div className="flex-grow w-full rounded-xl overflow-hidden shadow-lg border border-gray-300">
                    <MapContainer
                        center={[26.4499, 80.3319]} // Centered on Kanpur, India initially
                        zoom={6} // Initial zoom level
                        minZoom={2} // Minimum zoom level
                        maxBounds={[[ -90, -180 ], [ 90, 180 ]]} // Restrict map panning
                        maxBoundsViscosity={1.0} // Prevent dragging outside bounds
                        style={{ height: '100%', minHeight: '400px', width: '100%' }} // Ensure map takes available height
                        whenCreated={mapInstance => { mapRef.current = mapInstance; }} // Get map instance
                    >
                        <TileLayer
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        />
                        <MapClickHandler
                            setSelectedLocation={setSelectedLocation}
                            setSelectedPrediction={setSelectedPrediction}
                            setOverallAqiCategory={setOverallAqiCategory}
                            setOverallAqiColor={setOverallAqiColor}
                            setLoading={setLoading}
                            setHealthAdvice={setHealthAdvice}
                            setLocationNameFromClick={setLocationName}
                            setGlobalMessage={setGlobalMessage}
                        />

                        {/* Grid data markers (from AI model prediction) */}
                        {gridData.map((point, index) => {
                            const pollutantConcentrations = {
                                no2: point.no2, pm25: point.pm25, pm10: point.pm10,
                                o3: point.o3, so2: point.so2, co: point.co,
                            };
                            // Calculate overall AQI for grid markers on the frontend
                            const overallAqi = getOverallAqiCategoryFromPollutants(pollutantConcentrations);
                            const markerColor = overallAqi.color;

                            return (
                                <Marker
                                    key={index}
                                    position={[point.lat, point.lng]}
                                    icon={L.divIcon({
                                        className: 'custom-div-icon', // Custom class for potential external CSS if needed
                                        html: `<div style="background-color: ${markerColor}; width: 10px; height: 10px; border-radius: 50%; border: 1px solid rgba(0,0,0,0.3); box-shadow: 0 0 2px rgba(0,0,0,0.5);"></div>`,
                                        iconSize: [12, 12], // Slightly larger for visibility
                                        iconAnchor: [6, 6] // Center the icon
                                    })}
                                >
                                    <Popup>
                                        <div className="font-sans text-sm">
                                            <strong className="text-gray-800">Location:</strong> Lat: {point.lat.toFixed(2)}, Lng: {point.lng.toFixed(2)}
                                            <br/>
                                            <strong className="text-gray-800">Overall AQI:</strong> <span style={{ color: overallAqi.color }} className="font-semibold">{overallAqi.category}</span>
                                            <br/>
                                            <small className="text-gray-600">(AI-predicted grid value)</small>
                                        </div>
                                    </Popup>
                                </Marker>
                            );
                        })}

                        {/* Marker for selected/searched location (main point) */}
                        {selectedLocation && (
                            <Marker position={[selectedLocation.lat, selectedLocation.lng]}>
                                <Popup>
                                    <div className="font-sans text-sm">
                                        <strong className="text-gray-800">Selected Location:</strong>
                                        <br/>
                                        {locationName}
                                    </div>
                                </Popup>
                            </Marker>
                        )}
                    </MapContainer>
                </div>
            </div>

            {/* Side panel for details and health advice */}
            <div className="lg:w-1/3 bg-white rounded-xl shadow-xl p-6 sm:p-8 border border-indigo-200 flex flex-col">
                <h2 className="text-2xl font-bold text-indigo-700 mb-6 border-b pb-3">
                    Details for <span className="text-purple-700">{locationName}</span>
                </h2>

                {loading && (
                    <div className="flex items-center justify-center py-10">
                        <svg className="animate-spin h-8 w-8 text-indigo-600" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <p className="ml-3 text-gray-700">Loading data and AI insight...</p>
                    </div>
                )}

                {selectedLocation && selectedPrediction && !loading && (
                    <div className="mb-6">
                        {selectedPrediction.error ? (
                            <p className="text-red-600 bg-red-100 p-3 rounded-lg border border-red-200 mb-4">{selectedPrediction.error}</p>
                        ) : (
                            <>
                                <p className="text-sm text-gray-600 mb-2">Source: <span className="font-semibold">{selectedPrediction.source}</span></p>
                                {selectedPrediction.date_utc && (
                                    <p className="text-sm text-gray-600 mb-4">Last Updated (UTC): <span className="font-semibold">{formatUtcDate(selectedPrediction.date_utc)}</span></p>
                                )}

                                <div
                                    className="p-3 rounded-lg text-white font-bold text-center text-lg shadow-md mb-4"
                                    style={{ backgroundColor: overallAqiColor }}
                                >
                                    Overall AQI Category: {overallAqiCategory}
                                </div>

                                <h3 className="text-xl font-bold text-gray-800 mb-3 border-b pb-2">Pollutant Concentrations:</h3>
                                <ul className="space-y-2 mb-6">
                                    {renderPollutant('NO2', selectedPrediction.no2, 'NO2')}
                                    {renderPollutant('PM2.5', selectedPrediction.pm25, 'PM2.5')}
                                    {renderPollutant('PM10', selectedPrediction.pm10, 'PM10')}
                                    {renderPollutant('O3', selectedPrediction.o3, 'O3')}
                                    {renderPollutant('SO2', selectedPrediction.so2, 'SO2')}
                                    {renderPollutant('CO', selectedPrediction.co, 'CO', 'mg/m³')} {/* Specify unit for CO */}
                                </ul>
                            </>
                        )}
                    </div>
                )}

                {!selectedLocation && !loading && (
                    <p className="text-gray-700 text-center py-10">Click on the map or search for a location to see details here.</p>
                )}

                <h3 className="text-xl font-bold text-blue-800 mb-3 border-b pb-2">AI-Generated Health Advice:</h3>
                <p className="text-gray-800 mb-6 flex-grow">{healthAdvice}</p>

                {/* AQI Category Legend */}
                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                    <h3 className="text-lg font-bold text-gray-800 mb-3">AQI Categories ($\mu g/m^3$ for most, $mg/m^3$ for CO)</h3>
                    {Object.entries(AQI_CATEGORIES).map(([category, details]) => (
                        <div key={category} className="flex items-center mb-1 text-sm text-gray-700">
                            <span className="w-4 h-4 rounded-full mr-2 shadow-sm" style={{ backgroundColor: details.color }}></span>
                            <span><span className="font-semibold">{category}</span>: {details.range}</span>
                        </div>
                    ))}
                    <p className="text-xs text-gray-500 mt-3">
                        <small>Note: These are simplified ranges. Official AQI is more complex.</small>
                        <br/>
                        <small>Geocoding powered by <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">OpenStreetMap</a>.</small>
                    </p>
                </div>
            </div>
        </div>
    );
}

export default App;