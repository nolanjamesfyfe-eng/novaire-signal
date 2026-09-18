(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.MapFacts = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  function compactPopulation(value) {
    if (!Number.isFinite(value) || value <= 0) return 'Unavailable';
    if (value >= 1e9) return (value / 1e9).toFixed(1) + 'B';
    if (value >= 1e6) return Math.round(value / 1e6) + 'M';
    if (value >= 1e4) return Math.round(value / 1e3) + 'K';
    return (value / 1e3).toFixed(1).replace(/\.0$/, '') + 'K';
  }
  function compactGDP(value) {
    if (!Number.isFinite(value) || value <= 0) return 'N/A';
    if (value >= 1000) return '$' + (value / 1000).toFixed(1) + 'T';
    if (value >= 1) return '$' + Math.round(value) + 'B';
    return '$' + Math.round(value * 1000) + 'M';
  }
  return { compactPopulation, compactGDP };
});
