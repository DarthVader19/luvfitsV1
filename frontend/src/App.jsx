import { useState, useEffect } from 'react';
import SearchBar from './components/SearchBar';
import OutfitDisplay from './components/OutfitDisplay';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [outfit, setOutfit] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);

  // Fetch statistics on mount
  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/stats`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      if (data.success) {
        setStats(data.statistics);
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const handleSearch = async (query) => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setOutfit(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/outfits?query=${encodeURIComponent(query)}`
      );
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();

      if (data.success) {
        setOutfit(data.outfit);
      } else {
        setError(data.error || 'Failed to find outfit');
      }
    } catch (err) {
      setError(
        err.message === 'Failed to fetch'
          ? "Cannot connect to backend. Make sure it's running on http://localhost:8000"
          : err.message
      );
      console.error('Error searching outfits:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-content">
          <h1>✨ Luvfits</h1>
          <p className="subtitle">Discover outfits that match your vibe</p>
        </div>
      </header>

      <main className="app-main">
        <SearchBar onSearch={handleSearch} loading={loading} />
        <OutfitDisplay outfit={outfit} loading={loading} error={error} />
      </main>

      {stats && (
        <footer className="app-footer">
          <div className="stats">
            <div className="stat-item">
              <span className="stat-value">{stats.total_products}</span>
              <span className="stat-label">Products</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{Object.keys(stats.by_site).length}</span>
              <span className="stat-label">Retailers</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">4</span>
              <span className="stat-label">Categories</span>
            </div>
          </div>
        </footer>
      )}
    </div>
  );
}

export default App;
