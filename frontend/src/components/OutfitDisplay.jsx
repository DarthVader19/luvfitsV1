import '../styles/OutfitDisplay.css';

function OutfitDisplay({ outfit, loading, error }) {
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
          <p>❌ {error}</p>
        </div>
      </div>
    );
  }

  if (!outfit || Object.values(outfit).every(v => v === null)) {
    return (
      <div className="outfit-container">
        <div className="empty-state">
          <p>🔍 Start by searching for a vibe to see outfits</p>
        </div>
      </div>
    );
  }

  const items = [
    { key: 'top', label: 'Top', category: 'Tops' },
    { key: 'bottom', label: 'Bottom', category: 'Bottoms' },
    { key: 'accessory', label: 'Accessory', category: 'Accessories' },
    { key: 'shoe', label: 'Shoe', category: 'Shoes' },
  ];

  return (
    <div className="outfit-container">
      <div className="outfit-header">
        <h2>✨ Your Perfect Outfit</h2>
        {outfit.compatibility_score && (
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
        {items.map(({ key, label, category }) => {
          const item = outfit[key];
          return (
            <div key={key} className="outfit-item">
              <div className="item-label">{label}</div>
              
              {item ? (
                <div className="item-content">
                  {item.image_url && (
                    <div className="item-image-wrapper">
                      <img 
                        src={item.image_url} 
                        alt={item.name}
                        className="item-image"
                        onError={(e) => {
                          e.target.src = 'https://via.placeholder.com/300x300?text=' + label;
                        }}
                      />
                    </div>
                  )}
                  
                  <div className="item-details">
                    <h3 className="item-name">{item.name}</h3>
                    
                    <div className="item-meta">
                      <span className="price">${item.price?.toFixed(2) || 'N/A'}</span>
                      {item.color && <span className="color">{item.color}</span>}
                      <span className="site">{item.site}</span>
                    </div>
                    
                    {item.tags && (
                      <div className="item-tags">
                        {item.tags.split(',').map((tag) => (
                          <span key={tag.trim()} className="tag">{tag.trim()}</span>
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
                        View on {item.site} →
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

      {Object.values(outfit).some(v => v !== null) && (
        <div className="outfit-actions">
          <button className="action-button save">💾 Save Outfit</button>
          <button className="action-button share">📤 Share</button>
        </div>
      )}
    </div>
  );
}

export default OutfitDisplay;