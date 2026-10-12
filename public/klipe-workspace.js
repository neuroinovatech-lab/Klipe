/* Classic workspace controls; preferences never modify project data. */
(function () {
  'use strict';
  const KEY = 'klipe.workspace.v1';
  function normalize(value) {
    return {mode: value && value.mode === 'review' ? 'review' : 'edit', enabled: false};
  }
  function reviewHeight(height) {
    return Math.min(Math.max(180, height - 270), Math.max(180, height * 0.78));
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {normalize, reviewHeight};
  if (typeof document === 'undefined') return;

  const $ = id => document.getElementById(id);
  const toolbar = document.querySelector('.toolbar.topbar-cc');
  if (!toolbar || !$('main-area')) return;
  let stored;
  try { stored = JSON.parse(localStorage.getItem(KEY)); } catch (_) { /* Storage is optional. */ }
  let prefs = normalize(stored);
  let editHeight = null, resizeFrame = 0;
  function remember() {
    try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (_) { /* Storage is optional. */ }
  }
  function resize() {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => {
      if (typeof NLE !== 'undefined' && NLE.renderer) NLE.resizeTimeline();
    });
  }
  function button(label, action, icon) {
    const el = document.createElement('button');
    el.type = 'button'; el.title = label; el.setAttribute('aria-label', label);
    if (icon) {
      el.className = 'kw-icon';
      const img = document.createElement('img');
      img.src = '/vendor/lucide/' + icon + '.svg'; img.alt = ''; img.width = img.height = 16;
      el.append(img);
    } else el.textContent = label;
    el.addEventListener('click', async () => {
      try { await action(); }
      catch (error) { if (typeof NLE !== 'undefined') NLE.showToast(error.message, true); }
    });
    return el;
  }
  const bar = document.createElement('div'); bar.id = 'kw-classic-bar';
  const modes = document.createElement('div'); modes.className = 'kw-modes';
  modes.setAttribute('role', 'group'); modes.setAttribute('aria-label', 'Espa\u00e7o de trabalho');
  const edit = button('Edi\u00e7\u00e3o', () => setMode('edit'));
  const review = button('Revis\u00e3o', () => setMode('review'));
  edit.id = 'kw-classic-edit'; review.id = 'kw-classic-review';
  const full = button('Preview em tela cheia', fullscreen, 'maximize');
  modes.append(edit, review); bar.append(modes, full); toolbar.after(bar);

  function apply() {
    const reviewing = prefs.mode === 'review';
    edit.setAttribute('aria-pressed', String(!reviewing));
    review.setAttribute('aria-pressed', String(reviewing));
    document.body.classList.toggle('kw-classic-review', reviewing);
    if (reviewing) {
      if (editHeight === null) editHeight = $('main-area').style.height;
      $('main-area').style.height = reviewHeight(innerHeight) + 'px';
    } else if (editHeight !== null) {
      $('main-area').style.height = editHeight; editHeight = null;
    }
    resize();
  }
  function setMode(mode) { prefs = normalize({mode}); apply(); remember(); }
  async function fullscreen() {
    if (document.fullscreenElement) await document.exitFullscreen();
    else if ($('preview-column').requestFullscreen) await $('preview-column').requestFullscreen();
    else throw new Error('Tela cheia indisponivel nesta janela. Use o modo Revisao.');
  }
  document.addEventListener('fullscreenchange', () => {
    const active = document.fullscreenElement === $('preview-column');
    full.querySelector('img').src = '/vendor/lucide/' + (active ? 'minimize' : 'maximize') + '.svg';
    full.title = active ? 'Sair da tela cheia' : 'Preview em tela cheia';
    full.setAttribute('aria-label', full.title); resize();
  });
  // Retire saved desktop preferences and old links without reloading the editor.
  const url = new URL(location.href);
  if (url.searchParams.has('workspace')) {
    url.searchParams.delete('workspace'); history.replaceState(history.state, '', url);
  }
  window.addEventListener('resize', apply);
  window.KlipeWorkspace = {reset: () => setMode('edit'), getState: () => ({...prefs})};
  remember(); apply();
})();
