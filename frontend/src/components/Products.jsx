import { useState } from 'react';
import '../styles/Products.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const CATEGORIES = ['All', 'Tops', 'Bottoms', 'Shoes', 'Accessories'];
const SITES = ['All', 'amazon', 'h&m', 'nordstrom'];

function Products({ products = [], loading, error, onRefresh }) {
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [selectedSite, setSelectedSite] = useState('All');
  const [localLoading, setLocalLoading] = useState(loading);
  const [localError, setLocalError] = useState(error);

  // Filter products based on selected category and site
  const filteredProducts = products.filter((product) => {
    const matchesCategory = selectedCategory === 'All' || product.category === selectedCategory;
    const matchesSite = selectedSite === 'All' || product.site.toLowerCase() === selectedSite.toLowerCase();
    return matchesCategory && matchesSite;
  });

  const handleRefresh = async () => {
    setLocalLoading(true);
    setLocalError(null);
    try {
      if (onRefresh) {
        await onRefresh();
      }
    } catch (err) {
      setLocalError(err.message);
    } finally {
      setLocalLoading(false);
    }
  };

  return (
    <section className="products-section">
      <div className="products-header">
        <h2>Available Products</h2>
        <button
          className="refresh-button"
          onClick={handleRefresh}
          disabled={localLoading}
        >
          {localLoading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <div className="products-filters">
        <div className="filter-group">
          <label htmlFor="category-filter">Category:</label>
          <select
            id="category-filter"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            disabled={localLoading}
          >
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="site-filter">Site:</label>
          <select
            id="site-filter"
            value={selectedSite}
            onChange={(e) => setSelectedSite(e.target.value)}
            disabled={localLoading}
          >
            {SITES.map((site) => (
              <option key={site} value={site}>
                {site === 'All' ? 'All Stores' : site.charAt(0).toUpperCase() + site.slice(1)}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-info">
          Showing {filteredProducts.length} of {products.length} products
        </div>
      </div>

      {localError && <p className="products-error">{localError}</p>}

      {!localLoading && products.length === 0 && !localError && (
        <p className="products-empty">
          No products available yet. Try refreshing the data from the backend.
        </p>
      )}

      <div className="products-grid">
        {filteredProducts.map((product) => (
          <article key={product.id} className="product-card">
            {product.image_url && (
              <div className="product-image">
                <img
                  src={product.image_url}
                  alt={product.name}
                  onError={(e) => {
                    e.target.src = 'https://via.placeholder.com/200?text=No+Image';
                  }}
                />
              </div>
            )}

            <div className="product-info">
              <h3 className="product-name">{product.name}</h3>

              <p className="product-category">
                {product.category}
                <span className="product-site">{product.site}</span>
              </p>

              {product.price && (
                <p className="product-price">${product.price.toFixed(2)}</p>
              )}

              {product.description && (
                <p className="product-description">{product.description}</p>
              )}

              {product.tags && (
                <div className="product-tags">
                  {(Array.isArray(product.tags)
                    ? product.tags
                    : product.tags.split(',')
                  )
                    .filter((tag) => tag.trim())
                    .slice(0, 3)
                    .map((tag, idx) => (
                      <span key={idx} className="tag">
                        {tag.trim()}
                      </span>
                    ))}
                </div>
              )}

              <a
                href={product.product_url}
                target="_blank"
                rel="noopener noreferrer"
                className="product-link"
              >
                View on Store →
              </a>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default Products;
