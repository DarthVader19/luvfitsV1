import '../styles/OutfitDisplay.css';

function normalizeTags(tags) {
  if (Array.isArray(tags)) return tags;
  if (typeof tags === 'string') {
    return tags.split(',').map((t) => t.trim()).filter(Boolean);
  }
  return [];
}

function OutfitDisplay({ outfit, loading, error }) {
  const hasOutfitItems = Boolean(
    outfit?.top || outfit?.bottom || outfit?.accessory || outfit?.shoe || outfit?.shoes
  );

  if (loading) {
    return (
      <div className="outfit-container">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Finding your perfect outfit...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="outfit-container">
        <div className="error-message">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!hasOutfitItems) {
    return (
      <div className="outfit-container">
        <div className="empty-state">
          <p>Start by searching for a vibe to see outfits.</p>
        </div>
      </div>
    );
  }

  const items = [
    { key: 'top', label: 'Top' },
    { key: 'bottom', label: 'Bottom' },
    { key: 'accessory', label: 'Accessory' },
    { key: 'shoe', label: 'Shoe' },
  ];

  return (
    <div className="outfit-container">
      <div className="outfit-header">
        <h2>Your Outfit</h2>
        {typeof outfit.compatibility_score === 'number' && (
          <div className="compatibility-score">
            <span>Match Score: {(outfit.compatibility_score * 100).toFixed(0)}%</span>
            <div className="score-bar">
              <div
                className="score-fill"
                style={{ width: `${outfit.compatibility_score * 100}%` }}
              ></div>
            </div>
          </div>
        )}
      </div>

      <div className="outfit-grid">
        {items.map(({ key, label }) => {
          const item = outfit[key] || (key === 'shoe' ? outfit.shoes : null);
          const tags = normalizeTags(item?.tags);

          return (
            <div key={key} className="outfit-item">
              <div className="item-label">{label}</div>

              {item ? (
                <div className="item-content">
                  {item.image_url && (
                    <div className="item-image-wrapper">
                      <img
                        src={item.image_url}
                        alt={item.name || label}
                        className="item-image"
                        onError={(e) => {
                          e.target.src = `https://via.placeholder.com/300x300?text=${label}`;
                        }}
                      />
                    </div>
                  )}

                  <div className="item-details">
                    <h3 className="item-name">{item.name}</h3>

                    <div className="item-meta">
                      <span className="price">${Number(item.price || 0).toFixed(2)}</span>
                      {item.color && <span className="color">{item.color}</span>}
                      <span className="site">{item.site}</span>
                    </div>

                    {tags.length > 0 && (
                      <div className="item-tags">
                        {tags.map((tag) => (
                          <span key={tag} className="tag">{tag}</span>
                        ))}
                      </div>
                    )}

                    {item.product_url && (
                      <a
                        href={item.product_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="item-link"
                      >
                        View on {item.site}
                      </a>
                    )}
                  </div>
                </div>
              ) : (
                <div className="item-empty">
                  <p>No item available</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default OutfitDisplay;
