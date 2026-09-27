(() => {
  'use strict';

  const AUTH_URL = '/api/health-auth';
  const RECORD_URL = '/api/health-record';
  let privateRecord = null;

  function emit(name, detail) {
    window.dispatchEvent(new CustomEvent(name, detail === undefined ? undefined : { detail }));
  }

  function create(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function addList(parent, heading, value) {
    if (value === undefined) return;
    const section = create('section', 'health-private__section');
    section.append(create('h3', '', heading));
    if (Array.isArray(value)) {
      const list = create('ul');
      value.forEach(item => list.append(create('li', '', item)));
      section.append(list);
    } else {
      section.append(create('p', '', value));
    }
    parent.append(section);
  }

  function mount() {
    if (document.querySelector('[data-health-private]')) return;
    const panel = create('section', 'health-private');
    panel.dataset.healthPrivate = '';
    panel.setAttribute('aria-labelledby', 'health-private-title');
    const title = create('h2', 'health-private__title', 'Private health record');
    title.id = 'health-private-title';
    const status = create('p', 'health-private__status', 'Unlock with your Signal PIN. Nothing is stored in this browser.');
    status.setAttribute('role', 'status');
    const form = create('form', 'health-private__form');
    const label = create('label', '', 'Signal PIN');
    label.htmlFor = 'health-private-pin';
    const pin = create('input');
    Object.assign(pin, { id: 'health-private-pin', name: 'pin', type: 'password', inputMode: 'numeric', maxLength: 5, pattern: '\\d{5}', autocomplete: 'current-password', required: true });
    const unlock = create('button', '', 'Unlock');
    unlock.type = 'submit';
    form.append(label, pin, unlock);
    const content = create('div', 'health-private__content');
    content.hidden = true;
    const logout = create('button', 'health-private__logout', 'Lock record');
    logout.type = 'button';
    logout.hidden = true;
    panel.append(title, status, form, content, logout);

    const slot = document.querySelector('[data-health-private-slot]');
    const stage = document.querySelector('[data-health-stage], .health-stage, .atlas-stage');
    if (slot) slot.append(panel);
    else if (stage && stage.parentNode) stage.insertAdjacentElement('afterend', panel);
    else (document.querySelector('main') || document.body).append(panel);

    function clearRecord(message = 'Record locked.') {
      privateRecord = null;
      content.replaceChildren();
      content.hidden = true;
      logout.hidden = true;
      form.hidden = false;
      pin.value = '';
      status.textContent = message;
      emit('health:record-cleared');
    }

    function render(record) {
      privateRecord = record;
      content.replaceChildren();
      content.append(create('h3', 'health-private__record-label', record.label));
      addList(content, 'Summary', record.summary);
      addList(content, 'Reported findings', record.reportedFindings);
      addList(content, 'Care plan', record.carePlan);
      addList(content, 'Source date', record.sourceDate);
      addList(content, 'Certainty', record.certainty);
      if (record.bodyLikeness) {
        const likeness = record.bodyLikeness;
        addList(content, 'Body likeness model', [likeness.physique, likeness.anatomicalLeftClavicle]);
        addList(content, 'Likeness provenance', likeness.provenance);
        addList(content, 'Modeling status', likeness.modelingCertainty);
      }
      content.hidden = false;
      form.hidden = true;
      logout.hidden = false;
      status.textContent = 'Private record unlocked for this session.';
      emit('health:record-ready', record);
    }

    async function loadRecord() {
      const response = await fetch(RECORD_URL, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
      if (response.status === 401) { clearRecord('Session expired. Unlock again.'); return; }
      if (!response.ok) throw new Error('Record unavailable');
      const payload = await response.json();
      render(payload.record);
    }

    form.addEventListener('submit', async event => {
      event.preventDefault();
      unlock.disabled = true;
      status.textContent = 'Unlocking…';
      try {
        const response = await fetch(AUTH_URL, {
          method: 'POST', credentials: 'same-origin', cache: 'no-store',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ pin: pin.value })
        });
        pin.value = '';
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.error || 'Unable to unlock');
        }
        await loadRecord();
      } catch (error) {
        clearRecord(error.message || 'Unable to unlock');
      } finally { unlock.disabled = false; }
    });

    logout.addEventListener('click', async () => {
      try { await fetch(AUTH_URL, { method: 'DELETE', credentials: 'same-origin', cache: 'no-store' }); }
      finally { clearRecord(); }
    });

    window.addEventListener('health:focus-record', () => {
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (!privateRecord) pin.focus({ preventScroll: true });
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
  else mount();
})();
