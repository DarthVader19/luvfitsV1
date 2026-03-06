import { useState, useEffect } from 'react';
import SearchBar from './components/SearchBar';
import OutfitDisplay from './components/OutfitDisplay';
import AvailableOutfits from './components/AvailableOutfits';
import Products from './components/Products';
import './App.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  const [page, setPage] = useState('search');
  const [outfit, setOutfit] = useState(null);
  const [searchOutfits, setSearchOutfits] = useState([]);
  const [availableOutfits, setAvailableOutfits] = useState([]);
  const [products, setProducts] = useState([]);
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
      setSearchOutfits([detail]);
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
      const response = await fetch(`${API_BASE_URL}/outfits?limit=100`);
      if (!response.ok) {
        throw new Error(`Failed to fetch outfits (${response.status})`);
      }
      const data = await response.json();
      console.log('Outfits API response:', data);
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

  const loadProducts = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/products?limit=400`);
      if (!response.ok) {
        throw new Error(`Failed to fetch products (${response.status})`);
      }
      const data = await response.json();
      console.log('Products API response:', data);
      if (data.status !== 'success') {
        throw new Error(data.detail || 'Failed to fetch products');
      }
      setProducts(data.results || []);
      console.log(data.count);
      
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
    setSearchOutfits([]);

    try {
      const endpoint = `${API_BASE_URL}/search/similar`;
      console.log(" searching for ",endpoint);
      console.log("search query:", query);
      
      const response = await fetch(endpoint, {
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

      const topMatches = (data.results || []).slice(0, 5);
      if (topMatches.length === 0) {
        setError(`No outfits found for "${query}"`);
        return;
      }

      const details = await Promise.all(
        topMatches
          .filter((result) => result?.id)
          .map((result) => fetchOutfitDetail(result.id))
      );

      if (details.length === 0) {
        setError(`No outfits found for "${query}"`);
        return;
      }

      setSearchOutfits(details);
      setOutfit(details[0]);
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
    } else if (page === 'products') {
      loadProducts();
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
          <button
            className={`page-tab ${page === 'products' ? 'active' : ''}`}
            onClick={() => setPage('products')}
          >
            All Products
          </button>
        </div>

        {page === 'search' ? (
          <>
            <SearchBar onSearch={handleSearch} loading={loading} />
            <div className="search-content">
              {searchOutfits.length > 0
                ? searchOutfits.map((item, index) => (
                  <OutfitDisplay key={item.id || `search-outfit-${index}`} outfit={item} loading={false} error={null} />
                ))
                : <OutfitDisplay outfit={outfit} loading={loading} error={error} />}
            </div>
          </>
        ) : page === 'available' ? (
          <AvailableOutfits
            outfits={availableOutfits}
            loading={loading}
            error={error}
            onOpenOutfit={handleOpenOutfit}
            onRefresh={loadAvailableOutfits}
          />
        ) : (
          <Products products={products} loading={loading} error={error} onRefresh={loadProducts} />
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
