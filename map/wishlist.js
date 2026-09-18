/* Personal, browser-local ranking. Never writes the public visited/planned record. */
(function () {
  'use strict';
  const KEY = 'novaire.flaneur.wishlist.v1';
  function move(items, from, to) {
    const result = [...items];
    if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || from >= result.length || to < 0 || to >= result.length) return result;
    result.splice(to, 0, result.splice(from, 1)[0]);
    return result;
  }
  function restore(raw, defaults, valid) {
    if (!raw) return { codes: [...defaults], locked: true };
    const saved = JSON.parse(raw);
    if (saved.version !== 1 || !Array.isArray(saved.codes) || saved.codes.length > valid.size || typeof saved.locked !== 'boolean' || new Set(saved.codes).size !== saved.codes.length || saved.codes.some(code => !valid.has(code))) throw Error('Invalid saved ranking');
    return { codes: [...saved.codes], locked: saved.locked };
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports = { move, restore, KEY }; return; }
  const list = document.querySelector('#wishlist-list');
  if (!list) return;
  const defaults = [...list.children].map(row => row.dataset.code);
  const lockButton = document.querySelector('#wishlist-lock');
  const addForm = document.querySelector('#wishlist-add');
  const newCountry = document.querySelector('#wishlist-new');
  const message = document.querySelector('#wishlist-message');
  const title = document.querySelector('#wishlist-title');
  const note = document.querySelector('#wishlist-note');
  let catalog = [], names = new Map(), state;
  const say = text => { message.textContent = text; };
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  function persist(next) {
    try {
      localStorage.setItem(KEY, JSON.stringify({ version: 1, ...next }));
      state = next;
      return true;
    } catch (_) {
      say('Could not save. Allow browser storage, then try again. Your last saved ranking is unchanged.');
      return false;
    }
  }
  function commit(codes, announcement) {
    if (state.locked) return;
    if (persist({ codes, locked: false })) { render(); say(announcement); }
    else render();
  }
  function countryFor(value) {
    const key = value.trim().toLocaleLowerCase();
    return catalog.find(country => country.name.toLocaleLowerCase() === key || country.iso2.toLowerCase() === key);
  }
  function selectedCountry(value, exceptCode) {
    const country = countryFor(value);
    if (!country) { say('Choose a country from the suggestions, or enter its two-letter code.'); return null; }
    if (state.codes.includes(country.iso2) && country.iso2 !== exceptCode) { say(`${country.name} is already in your ranking.`); return null; }
    return country;
  }
  function reorder(code, target) {
    const from = state.codes.indexOf(code);
    if (state.locked || from < 0 || !Number.isInteger(target) || target < 0 || target >= state.codes.length) return;
    commit(move(state.codes, from, target), `${names.get(code)} moved to ${target + 1}.`);
    list.querySelector(`[data-code="${code}"] .wish-country`)?.focus();
  }
  function render() {
    const fragment = document.createDocumentFragment();
    title.textContent = state.codes.length ? `Top ${state.codes.length} countries to visit` : 'Countries to visit';
    lockButton.textContent = state.locked ? 'Edit ranking' : 'Save & Lock';
    lockButton.setAttribute('aria-label', state.locked ? 'Unlock country ranking' : 'Save and lock country ranking');
    addForm.hidden = state.locked;
    note.textContent = state.locked ? 'Locked · Saved in this browser' : 'Change a rank or country cell, or use the arrows. Edits save in this browser.';
    state.codes.forEach((code, index) => {
      const row = element('li');
      row.dataset.code = code;
      if (state.locked) {
        row.append(element('span', 'wish-rank', String(index + 1).padStart(2, '0')), element('span', 'wish-country', names.get(code)));
      } else {
        const rank = element('input', 'wish-rank');
        rank.type = 'number'; rank.min = '1'; rank.max = String(state.codes.length); rank.value = index + 1;
        rank.setAttribute('aria-label', `Rank for ${names.get(code)}`);
        rank.addEventListener('change', () => {
          const position = Number(rank.value);
          if (!Number.isInteger(position) || position < 1 || position > state.codes.length) { rank.value = index + 1; say(`Enter a rank from 1 to ${state.codes.length}.`); return; }
          reorder(code, position - 1);
        });
        const country = element('input', 'wish-country');
        country.value = names.get(code); country.maxLength = 80; country.setAttribute('list', 'wishlist-options');
        country.setAttribute('aria-label', `Country at rank ${index + 1}`);
        country.addEventListener('change', () => {
          const replacement = selectedCountry(country.value, code);
          if (!replacement) { country.value = names.get(code); return; }
          commit(state.codes.map(item => item === code ? replacement.iso2 : item), 'Country updated.');
        });
        country.addEventListener('keydown', event => {
          if (event.altKey && ['ArrowUp', 'ArrowDown'].includes(event.key)) { event.preventDefault(); reorder(code, index + (event.key === 'ArrowUp' ? -1 : 1)); }
          if (event.key === 'Enter') { event.preventDefault(); country.blur(); }
        });
        const actions = element('span', 'wish-actions');
        for (const [label, action, disabled, run] of [
          ['↑', 'up', index === 0, () => reorder(code, index - 1)],
          ['↓', 'down', index === state.codes.length - 1, () => reorder(code, index + 1)],
          ['×', 'remove', false, () => commit(state.codes.filter(item => item !== code), `${names.get(code)} removed.`)]
        ]) {
          const button = element('button', '', label);
          button.type = 'button'; button.dataset.action = action; button.disabled = disabled;
          button.setAttribute('aria-label', action === 'remove' ? `Remove ${names.get(code)}` : `Move ${names.get(code)} ${action}`);
          button.addEventListener('click', run); actions.append(button);
        }
        row.append(rank, country, actions);
      }
      fragment.append(row);
    });
    list.replaceChildren(fragment);
  }
  lockButton.addEventListener('click', () => {
    if (!state.locked && newCountry.value.trim()) { say('Add the new country or clear its cell before locking.'); newCountry.focus(); return; }
    const next = { codes: [...state.codes], locked: !state.locked };
    if (persist(next)) { render(); say(next.locked ? 'Saved and locked. Your order will be here when you return.' : 'Ranking unlocked.'); }
  });
  addForm.addEventListener('submit', event => {
    event.preventDefault();
    if (state.locked) return;
    const country = selectedCountry(newCountry.value);
    if (!country) return;
    if (persist({ codes: [...state.codes, country.iso2], locked: false })) {
      newCountry.value = ''; render(); say(`${country.name} added at the bottom.`); newCountry.focus();
    }
  });
  fetch('/map/countries.json').then(response => { if (!response.ok) throw Error(response.status); return response.json(); }).then(data => {
    catalog = data; names = new Map(data.map(country => [country.iso2, country.name]));
    try { state = restore(localStorage.getItem(KEY), defaults, new Set(names.keys())); }
    catch (_) { state = { codes: [...defaults], locked: true }; say('Saved ranking could not be read. Showing the original list; editing will save a fresh copy.'); }
    document.querySelector('#wishlist-options').replaceChildren(...catalog.map(country => {
      const option = document.createElement('option'); option.value = country.name; return option;
    }));
    render(); lockButton.disabled = false;
  }).catch(() => say('Country editor could not load. Reload to try again.'));
})();
