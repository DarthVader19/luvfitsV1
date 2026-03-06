import '../styles/AvailableOutfits.css';

function AvailableOutfits({ outfits, loading, error, onOpenOutfit, onRefresh }) {
  // Check if data is actual outfits or products by looking for characteristic fields
  const isOutfitData = outfits.length > 0 && (
    outfits[0].compatibility_score !== undefined || 
    outfits[0].vibes !== undefined ||
    outfits[0].top_id !== undefined
  );
  
  const isProductData = outfits.length > 0 && (
    outfits[0].name !== undefined &&
    outfits[0].product_url !== undefined &&
    outfits[0].price !== undefined
  );

  return (
    <section className="available-outfits">
      <div className="available-header">
        <h2>Available Outfits</h2>
        <button className="refresh-button" onClick={onRefresh} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh List'}
        </button>
      </div>

      {error && <p className="available-error">{error}</p>}

      {!loading && outfits.length === 0 && !error && (
        <p className="available-empty">No outfits available yet. Run refresh from backend first.</p>
      )}

      {isProductData && (
        <p className="available-error">⚠️ Error: Products returned instead of outfits. Check API endpoint.</p>
      )}

      <div className="available-grid">
        {outfits.map((item) => {
          // Handle outfit data
          if (isOutfitData) {
            return (
              <article key={item.id} className="available-card">
                <h3 className="available-title">Outfit #{(item.id || '').slice(-6)}</h3>
                <p className="available-meta">
                  Match: {Math.round((item.compatibility_score || 0) * 100)}%
                </p>
                <p className="available-vibes">
                  {(item.vibes || []).length ? item.vibes.join(', ') : 'No vibes tagged'}
                </p>
                {item.total_price && (
                  <p className="available-price">
                    Total: ${item.total_price.toFixed(2)}
                  </p>
                )}
                <button
                  className="open-button"
                  onClick={() => onOpenOutfit(item.id)}
                  disabled={!item.id || loading}
                >
                  View Outfit
                </button>
              </article>
            );
          }
          
          // Fallback if somehow products are returned
          if (isProductData) {
            return (
              <article key={item.id || item.name} className="available-card">
                <h3 className="available-title">{item.name}</h3>
                <p className="available-meta">${item.price?.toFixed(2) || 'N/A'}</p>
                <p className="available-vibes">{item.site || 'Unknown Store'}</p>
                <a
                  href={item.product_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="item-link"
                >
                  View Product
                </a>
              </article>
            );
          }
          
          return null;
        })}
      </div>
    </section>
  );
}

export default AvailableOutfits;
