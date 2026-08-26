import React, { useState, useEffect } from 'react';
import { Plane, Search, Calendar, Clock, X, ExternalLink } from 'lucide-react';

export default function FlightWindow({ position, onClose, onDrag }) {
  const [flights, setFlights] = useState([]);
  const [searchParams, setSearchParams] = useState({
    origin: '',
    destination: '',
    date: '',
    returnDate: '',
    passengers: 1
  });

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('flight_results', (data) => {
      setFlights(data);
    });
    
    return () => socket.off('flight_results');
  }, []);

  const handleSearch = () => {
    if (searchParams.origin && searchParams.destination && searchParams.date) {
      window.socket.emit('search_flights', searchParams);
    }
  };

  const formatTime = (time) => {
    return time || '--:--';
  };

  const formatDuration = (duration) => {
    return duration || '--';
  };

  return (
    <div 
      className="window flight-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '500px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Plane size={16} />
          <span>Flight Search</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="flight-search-form">
          <div className="form-row">
            <input
              type="text"
              placeholder="From"
              value={searchParams.origin}
              onChange={(e) => setSearchParams({...searchParams, origin: e.target.value})}
            />
            <input
              type="text"
              placeholder="To"
              value={searchParams.destination}
              onChange={(e) => setSearchParams({...searchParams, destination: e.target.value})}
            />
          </div>
          <div className="form-row">
            <input
              type="date"
              value={searchParams.date}
              onChange={(e) => setSearchParams({...searchParams, date: e.target.value})}
            />
            <input
              type="date"
              placeholder="Return (optional)"
              value={searchParams.returnDate}
              onChange={(e) => setSearchParams({...searchParams, returnDate: e.target.value})}
            />
          </div>
          <div className="form-row">
            <input
              type="number"
              min="1"
              max="9"
              placeholder="Passengers"
              value={searchParams.passengers}
              onChange={(e) => setSearchParams({...searchParams, passengers: parseInt(e.target.value) || 1})}
            />
            <button onClick={handleSearch}>
              <Search size={16} />
              Search
            </button>
          </div>
        </div>

        <div className="flight-results">
          {flights.length === 0 ? (
            <p className="no-results">No flights found. Enter search criteria above.</p>
          ) : (
            flights.map((flight, index) => (
              <div key={index} className="flight-card">
                <div className="flight-header">
                  <span className="airline">{flight.airline}</span>
                  <span className="price">{flight.price} {flight.currency}</span>
                </div>
                <div className="flight-route">
                  <div className="flight-time">
                    <Clock size={14} />
                    <span>{formatTime(flight.departure)}</span>
                  </div>
                  <div className="flight-line">
                    <span className="duration">{formatDuration(flight.duration)}</span>
                    <span className="stops">{flight.stops === 0 ? 'Non-stop' : `${flight.stops} stop${flight.stops > 1 ? 's' : ''}`}</span>
                  </div>
                  <div className="flight-time">
                    <Clock size={14} />
                    <span>{formatTime(flight.arrival)}</span>
                  </div>
                </div>
                <div className="flight-footer">
                  <button className="book-btn">
                    <ExternalLink size={14} />
                    Book
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
