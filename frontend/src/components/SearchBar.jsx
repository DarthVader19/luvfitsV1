import { useState } from 'react';
import '../styles/SearchBar.css';

function SearchBar({ onSearch, loading }) {
  const [query, setQuery] = useState('');
  const suggestions = ['casual', 'Date Night', '90s', 'party', 'minimalist', 'elegant', 'sporty', 'formal','neutral','vibrant'];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query);
    }
  };

  const handleSuggestion = (suggestion) => {
    setQuery(suggestion);
  };

  return (
    <div className="search-container">
      <form onSubmit={handleSubmit} className="search-form">
        <div className="search-input-wrapper">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find your vibe... (Date Night, casual, 90s...)"
            className="search-input"
            disabled={loading}
          />
          <button 
            type="submit" 
            className="search-button" 
            disabled={loading || !query.trim()}
          >
            {loading ? 'Searching...' : 'Search Outfit'}
          </button>
        </div>
      </form>
      
      <div className="suggestions">
        <p className="suggestions-label">Popular vibes:</p>
        <div className="suggestion-chips">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              className="suggestion-chip"
              onClick={() => handleSuggestion(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default SearchBar;