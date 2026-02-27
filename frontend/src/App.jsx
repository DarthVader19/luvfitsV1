import { useState, useEffect } from 'react';
import SearchBar from './components/SearchBar';
import OutfitDisplay from './components/OutfitDisplay';
import AvailableOutfits from './components/AvailableOutfits';
import './App.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  const [page, setPage] = useState('search');
  const [outfit, setOutfit] = useState(null);
  const [availableOutfits, setAvailableOutfits] = useState([]);
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
      if (data.status === 'success') {
        setStats(data.statistics);
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const fetchOutfitDetail = async (outfitId) => {
    const response = await fetch(`${API_BASE_URL}/outfits/${outfitId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch outfit details (${response.status})`);
    }

    const data = await response.json();
    if (data.status !== 'success') {
      throw new Error(data.detail || 'Failed to load outfit details');
    }

    return {
      ...data.outfit,
      top: data.products?.top ?? null,
      bottom: data.products?.bottom ?? null,
      shoe: data.products?.shoes ?? data.products?.shoe ?? null,
      accessory: data.products?.accessory ?? null,
    };
  };

  const handleOpenOutfit = async (outfitId) => {
    if (!outfitId) return;

    setLoading(true);
    setError(null);

    try {
      const detail = await fetchOutfitDetail(outfitId);
      setOutfit(detail);
      setPage('search');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadAvailableOutfits = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/outfits?limit=50`);
      if (!response.ok) {
        throw new Error(`Failed to fetch outfits (${response.status})`);
      }
      const data = await response.json();
      if (data.status !== 'success') {
        throw new Error(data.detail || 'Failed to fetch available outfits');
      }
      setAvailableOutfits(data.outfits || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (query) => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setOutfit(null);

    try {
      const response = await fetch(`${API_BASE_URL}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit: 10, include_vibes: true }),
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();

      if (data.status !== 'success') {
        throw new Error(data.detail || 'Failed to search outfits');
      }

      const firstOutfit = data.results?.[0];
      if (!firstOutfit?.id) {
        setError(`No outfits found for "${query}"`);
        return;
      }

      const detail = await fetchOutfitDetail(firstOutfit.id);
      setOutfit(detail);
    } catch (err) {
      setError(
        err.message === 'Failed to fetch'
          ? `Cannot connect to backend. Make sure it's running on ${API_BASE_URL}`
          : err.message
      );
      console.error('Error searching outfits:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (page === 'available') {
      loadAvailableOutfits();
    }
  }, [page]);

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-content">
          <h1>✨ Luvfits</h1>
          <p className="subtitle">Discover outfits that match your vibe</p>
        </div>
      </header>

      <main className="app-main">
        <div className="page-tabs">
          <button
            className={`page-tab ${page === 'search' ? 'active' : ''}`}
            onClick={() => setPage('search')}
          >
            Search Outfit
          </button>
          <button
            className={`page-tab ${page === 'available' ? 'active' : ''}`}
            onClick={() => setPage('available')}
          >
            Available Outfits
          </button>
        </div>

        {page === 'search' ? (
          <>
            <SearchBar onSearch={handleSearch} loading={loading} />
            <OutfitDisplay outfit={outfit} loading={loading} error={error} />
          </>
        ) : (
          <AvailableOutfits
            outfits={availableOutfits}
            loading={loading}
            error={error}
            onOpenOutfit={handleOpenOutfit}
            onRefresh={loadAvailableOutfits}
          />
        )}
      </main>

      {stats && (
        <footer className="app-footer">
          <div className="stats">
            <div className="stat-item">
              <span className="stat-value">{stats.total_products}</span>
              <span className="stat-label">Products</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{Object.keys(stats.by_site || {}).length}</span>
              <span className="stat-label">Retailers</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.total_outfits || 0}</span>
              <span className="stat-label">Outfits</span>
            </div>
          </div>
        </footer>
      )}
    </div>
  );
}

export default App;
