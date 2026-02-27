import '../styles/AvailableOutfits.css';

function AvailableOutfits({ outfits, loading, error, onOpenOutfit, onRefresh }) {
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

      <div className="available-grid">
        {outfits.map((item) => (
          <article key={item.id} className="available-card">
            <h3 className="available-title">Outfit #{(item.id || '').slice(-6)}</h3>
            <p className="available-meta">
              Match: {Math.round((item.compatibility_score || 0) * 100)}%
            </p>
            <p className="available-vibes">
              {(item.vibes || []).length ? item.vibes.join(', ') : 'No vibes tagged'}
            </p>
            <button
              className="open-button"
              onClick={() => onOpenOutfit(item.id)}
              disabled={!item.id || loading}
            >
              View Outfit
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

export default AvailableOutfits;
