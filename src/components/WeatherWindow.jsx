import React, { useState, useEffect } from 'react';
import { Cloud, Sun, CloudRain, CloudSnow, Wind, X, Search } from 'lucide-react';

export default function WeatherWindow({ position, onClose, onDrag }) {
  const [weather, setWeather] = useState({
    city: '',
    temp: 0,
    condition: 'Clear',
    humidity: 0,
    wind: 0,
    forecast: []
  });
  const [searchCity, setSearchCity] = useState('');

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('weather_data', (data) => {
      setWeather(data);
    });
    
    return () => socket.off('weather_data');
  }, []);

  const handleSearch = () => {
    if (searchCity.trim()) {
      window.socket.emit('get_weather', { city: searchCity });
    }
  };

  const getWeatherIcon = (condition) => {
    const lower = condition.toLowerCase();
    if (lower.includes('rain')) return <CloudRain size={32} />;
    if (lower.includes('cloud')) return <Cloud size={32} />;
    if (lower.includes('snow')) return <CloudSnow size={32} />;
    if (lower.includes('wind')) return <Wind size={32} />;
    return <Sun size={32} />;
  };

  return (
    <div 
      className="window weather-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '400px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Cloud size={16} />
          <span>Weather</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="weather-search">
          <input
            type="text"
            placeholder="Enter city name..."
            value={searchCity}
            onChange={(e) => setSearchCity(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button onClick={handleSearch}>
            <Search size={16} />
          </button>
        </div>

        {weather.city && (
          <div className="weather-current">
            <div className="weather-main">
              <div className="weather-icon">
                {getWeatherIcon(weather.condition)}
              </div>
              <div className="weather-temp">
                <span className="temp-value">{Math.round(weather.temp)}°</span>
                <span className="temp-unit">C</span>
              </div>
            </div>
            <div className="weather-details">
              <h3>{weather.city}</h3>
              <p>{weather.condition}</p>
            </div>
          </div>
        )}

        <div className="weather-stats">
          <div className="stat-item">
            <span>Humidity</span>
            <span>{weather.humidity}%</span>
          </div>
          <div className="stat-item">
            <span>Wind</span>
            <span>{weather.wind} km/h</span>
          </div>
        </div>

        {weather.forecast.length > 0 && (
          <div className="weather-forecast">
            <h4>Forecast</h4>
            {weather.forecast.map((day, i) => (
              <div key={i} className="forecast-day">
                <span>{day.day}</span>
                <span>{day.condition}</span>
                <span>{day.temp}°</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
