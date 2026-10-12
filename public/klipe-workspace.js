/* Workspace preferences stay local; project data and playback are never copied. */
(function () {
  'use strict';
  const KEY = 'klipe.workspace.v1';
  const defaults = {left: 286, right: 302, ratio: 0.62, library: true, properties: true, mode: 'edit'};
  const clamp = (n, min, max) => Math.min(max, Math.max(min, n));
  function normalize(value) {
    const v = value && typeof value === 'object' ? value : {};
    const number = (key, min, max) => typeof v[key] === 'number' && Number.isFinite(v[key])
      ? clamp(v[key], min, max) : defaults[key];
    return {left: number('left', 220, 440), right: number('right', 260, 480),
      ratio: number('ratio', 0.3, 0.8), library: typeof v.library === 'boolean' ? v.library : true,
      properties: typeof v.properties === 'boolean' ? v.properties : true,
      mode: v.mode === 'review' ? 'review' : 'edit'};
  }
  function geometry(value, width, height) {
    const p = normalize(value);
    const library = p.mode === 'edit' && p.library && width >= 900;
    const properties = p.mode === 'edit' && p.properties && width >= 760;
    let left = p.left, right = p.right;
    const budget = Math.max(0, width - 352);
    if (library && properties && left + right > budget) {
      left = Math.max(220, Math.min(left, budget - 260));
      right = Math.max(260, Math.min(right, budget - left));
    } else if (properties) right = Math.min(right, budget);
    const maxHeight = Math.max(180, height - 270);
    return {left, right, library, properties,
      height: clamp(height * (p.mode === 'review' ? 0.78 : p.ratio), 180, maxHeight)};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {normalize, geometry};
  if (typeof document === 'undefined') return;

  const $ = id => document.getElementById(id);
  const toolbar = document.querySelector('.toolbar.topbar-cc');
  if (!toolbar || !$('main-area')) return;
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (_) { /* Private storage may be unavailable. */ }
  let prefs = normalize(stored);
  let enabled = false;
  let override = typeof stored.enabled === 'boolean' ? stored.enabled : null;
  const query = new URLSearchParams(location.search).get('workspace');
  if (query === 'desktop' || query === 'classic') override = query === 'desktop';
  const moved = [];
  let drag = null, resizeFrame = 0, classicHeight = null;
  const original = {
    main: $('main-area').style.height, left: $('media-lib').style.width,
    right: $('properties-panel').style.width, collapsed: $('media-lib').classList.contains('collapsed'),
    propsTitle: document.querySelector('.props-header').textContent,
  };
  function remember() {
    try { localStorage.setItem(KEY, JSON.stringify({...prefs, enabled})); } catch (_) { /* Optional preference storage. */ }
  }
  function resize() {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => {
      if (typeof NLE !== 'undefined' && NLE.renderer) NLE.resizeTimeline();
    });
  }
  function run(action) {
    closeMenus();
    try {
      const result = action();
      if (result && typeof result.catch === 'function') result.catch(report);
    } catch (error) { report(error); }
  }
  function report(error) {
    if (typeof NLE !== 'undefined') NLE.showToast(error.message || 'Nao foi possivel executar o comando.', true);
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
    el.addEventListener('click', () => run(action));
    return el;
  }
  const header = document.createElement('header');
  header.id = 'kw-header'; header.className = 'kw-only';
  header.innerHTML = '<div class="kw-menubar"><a class="kw-brand" href="#" aria-label="Klipe"><img src="/marca/klipe-mark.svg" alt="" width="26" height="26"><strong>Klipe</strong></a><nav class="kw-menus" aria-label="Menu principal"></nav><div class="kw-project"></div></div><div class="kw-commandbar"><div class="kw-actions"></div><div class="kw-modes" role="group" aria-label="Espa\u00e7o de trabalho"></div><div class="kw-export"></div></div>';
  header.querySelector('.kw-brand').addEventListener('click', e => { e.preventDefault(); run(() => NLE.projectManager.openLoad()); });
  toolbar.before(header);
  const returnButton = button('Interface antiga', () => setEnabled(false));
  returnButton.id = 'kw-classic';
  header.querySelector('.kw-menubar').append(returnButton);
  function closeMenus(except) {
    header.querySelectorAll('details[open]').forEach(el => { if (el !== except) el.open = false; });
  }
  function menu(label, entries) {
    const details = document.createElement('details');
    details.className = 'kw-menu';
    const summary = document.createElement('summary'); summary.textContent = label;
    const popup = document.createElement('div'); popup.className = 'kw-popup';
    for (const [name, action] of entries) popup.append(button(name, action));
    details.append(summary, popup); header.querySelector('.kw-menus').append(details);
    details.addEventListener('toggle', () => { if (details.open) closeMenus(details); });
    details.addEventListener('keydown', e => {
      if (e.key === 'Escape') { details.open = false; summary.focus(); e.stopPropagation(); }
      if (!['ArrowDown', 'ArrowUp'].includes(e.key)) return;
      e.preventDefault(); e.stopPropagation(); details.open = true;
      const items = [...popup.querySelectorAll('button')];
      const index = items.indexOf(document.activeElement);
      items[(index + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length].focus();
    });
  }
  menu('Arquivo', [
    ['Novo projeto', () => NLE.projectManager.openNew()],
    ['Abrir projeto', () => NLE.projectManager.openLoad()],
    ['Salvar', () => NLE.save()],
    ['Salvar como...', () => NLE.projectManager.openSave()],
    ['Abrir pasta do projeto', () => NLE.abrirPasta('', 'project')],
    ['Exportar v\u00eddeo', () => NLE.renderPanel.open()],
  ]);
  menu('Editar', [['Desfazer', () => NLE.undo()], ['Refazer', () => NLE.redo()],
    ['Editar pelo texto', () => NLE.texto.abrir()], ['Configura\u00e7\u00f5es', () => NLE.ajustes.abrir()]]);
  menu('Exibir', [['Biblioteca de m\u00eddia', () => togglePanel('library')],
    ['Propriedades', () => togglePanel('properties')], ['Preview em tela cheia', fullscreen],
    ['Restaurar espa\u00e7o de trabalho', reset], ['Alternar tema claro/escuro', () => alternarTemaClaro()],
    ['Interface cl\u00e1ssica', () => setEnabled(false)]]);
  menu('Ferramentas', [['Gravar', () => NLE.gravar.abrir()],
    ['Templates de t\u00edtulo', () => NLE.tpl.abrir()], ['Atalhos', () => NLE.toggleShortcutsHelp()]]);

  const edit = button('Edi\u00e7\u00e3o', () => setMode('edit'));
  const review = button('Revis\u00e3o', () => setMode('review'));
  edit.id = 'kw-edit'; review.id = 'kw-review';
  header.querySelector('.kw-modes').append(edit, review);
  const classicBar = document.createElement('div'); classicBar.id = 'kw-classic-bar';
  const classicModes = document.createElement('div'); classicModes.className = 'kw-modes';
  classicModes.setAttribute('role','group'); classicModes.setAttribute('aria-label','Espa\u00e7o de trabalho');
  const classicEdit = button('Edi\u00e7\u00e3o', () => setMode('edit'));
  const classicReview = button('Revis\u00e3o', () => setMode('review'));
  classicEdit.id='kw-classic-edit'; classicReview.id='kw-classic-review';
  classicModes.append(classicEdit,classicReview);
  classicBar.append(classicModes,button('Preview em tela cheia',fullscreen,'maximize'));
  toolbar.after(classicBar);
  const leftButton = button('Biblioteca de m\u00eddia', () => togglePanel('library'), 'panel-left');
  const rightButton = button('Propriedades', () => togglePanel('properties'), 'panel-right');
  leftButton.id = 'kw-library'; rightButton.id = 'kw-properties';
  header.querySelector('.kw-actions').append(leftButton, rightButton);
  const restore = button('Restaurar espa\u00e7o de trabalho', reset, 'rotate-ccw');
  header.querySelector('.kw-actions').append(restore);
  const monitor = document.createElement('div'); monitor.id = 'kw-monitor'; monitor.className = 'kw-only';
  const monitorName = document.createElement('span'); monitorName.textContent = 'Monitor';
  const fullButton = button('Preview em tela cheia', fullscreen, 'maximize'); fullButton.id = 'kw-fullscreen';
  monitor.append(monitorName, fullButton); $('preview-column').prepend(monitor);
  const mediaSplitter = document.createElement('div'); mediaSplitter.id = 'kw-media-splitter';
  mediaSplitter.className = 'v-splitter kw-only'; $('media-lib').after(mediaSplitter);
  const classicButton = button('Interface nova', () => setEnabled(true)); classicButton.id = 'kw-enable';
  classicButton.classList.add('tb-btn'); toolbar.append(classicButton);

  function move(node, target) {
    if (!node) return;
    const anchor = document.createComment('workspace-original-position'); node.before(anchor);
    moved.push({node, anchor}); target.append(node);
  }
  function moveCommands() {
    const action = code => toolbar.querySelector('[onclick="' + code + '"]');
    const actions = header.querySelector('.kw-actions');
    for (const code of ['NLE.save()', 'NLE.undo()', 'NLE.redo()']) {
      const node = action(code);
      if (node) { node.classList.add('kw-original-command'); move(node, actions); }
    }
    move($('tb-project-title'), header.querySelector('.kw-project'));
    move($('aspect-btn')?.parentElement, monitor);
    monitor.append(fullButton);
    for (const id of ['btn-tema-claro', 'accent-picker', 'theme-toggle-btn']) {
      move($(id), header.querySelector('.kw-export'));
    }
    move(action('NLE.renderPanel.open()'), header.querySelector('.kw-export'));
    move($('render-progress-badge'), header.querySelector('.kw-export'));
  }
  function apply() {
    for (const btn of [edit,classicEdit]) btn.setAttribute('aria-pressed',String(prefs.mode==='edit'));
    for (const btn of [review,classicReview]) btn.setAttribute('aria-pressed',String(prefs.mode==='review'));
    if (!enabled) {
      const reviewing=prefs.mode==='review';
      document.body.classList.toggle('kw-classic-review',reviewing);
      if(reviewing){
        if(classicHeight===null)classicHeight=$('main-area').style.height;
        $('main-area').style.height=geometry({...prefs,mode:'review'},innerWidth,innerHeight).height+'px';
      }else if(classicHeight!==null){$('main-area').style.height=classicHeight;classicHeight=null;}
      resize();return;
    }
    const g = geometry(prefs, innerWidth, innerHeight);
    document.body.classList.toggle('kw-hide-library', !g.library);
    document.body.classList.toggle('kw-hide-properties', !g.properties);
    $('main-area').style.height = g.height + 'px';
    $('media-lib').style.width = g.left + 'px'; $('properties-panel').style.width = g.right + 'px';
    leftButton.setAttribute('aria-pressed', String(g.library)); rightButton.setAttribute('aria-pressed', String(g.properties));
    leftButton.disabled = innerWidth < 900; rightButton.disabled = innerWidth < 760;
    edit.setAttribute('aria-pressed', String(prefs.mode === 'edit')); review.setAttribute('aria-pressed', String(prefs.mode === 'review'));
    for (const [id, value] of [['kw-media-splitter', g.left], ['v-splitter', g.right], ['h-splitter', g.height]]) {
      $(id).setAttribute('aria-valuenow', String(Math.round(value)));
    }
    resize();
  }
  function setEnabled(value, persist = true) {
    if (enabled === value) return;
    finishDrag(); enabled = value;
    document.body.classList.remove('kw-classic-review');
    if(classicHeight!==null){$('main-area').style.height=classicHeight;classicHeight=null;}
    document.body.classList.toggle('desktop-workspace', value);
    if (value) {
      original.main = $('main-area').style.height;
      original.left = $('media-lib').style.width;
      original.right = $('properties-panel').style.width;
      original.collapsed = $('media-lib').classList.contains('collapsed');
      $('media-lib').classList.remove('collapsed'); moveCommands();
      document.querySelector('.props-header').textContent = 'Propriedades';
      apply();
    } else {
      closeMenus();
      while (moved.length) { const {node, anchor} = moved.pop(); anchor.replaceWith(node); }
      $('main-area').style.height = original.main; $('media-lib').style.width = original.left;
      $('properties-panel').style.width = original.right;
      $('media-lib').classList.toggle('collapsed', original.collapsed);
      document.querySelector('.props-header').textContent = original.propsTitle;
      document.body.classList.remove('kw-hide-library', 'kw-hide-properties'); apply();
    }
    // Remove the one-time URL override so reloads respect subsequent choices.
    const url = new URL(location.href); url.searchParams.delete('workspace');
    history.replaceState(history.state, '', url);
    if (persist) { override = value; remember(); }
  }
  function setMode(mode) { prefs.mode = mode; apply(); remember(); }
  function togglePanel(key) {
    if (prefs.mode === 'review') { prefs.mode = 'edit'; prefs[key] = true; }
    else prefs[key] = !prefs[key];
    apply(); remember();
  }
  function reset() { prefs = {...defaults}; apply(); remember(); }
  async function fullscreen() {
    if (document.fullscreenElement) await document.exitFullscreen();
    else if ($('preview-column').requestFullscreen) await $('preview-column').requestFullscreen();
    else throw new Error('Tela cheia indisponivel nesta janela. Use o modo Revisao.');
  }
  document.addEventListener('fullscreenchange', () => {
    const active = document.fullscreenElement === $('preview-column');
    fullButton.querySelector('img').src = '/vendor/lucide/' + (active ? 'minimize' : 'maximize') + '.svg';
    fullButton.title = active ? 'Sair da tela cheia' : 'Preview em tela cheia';
    fullButton.setAttribute('aria-label', fullButton.title); resize();
  });
  document.addEventListener('pointerdown', e => { if (!e.target.closest('.kw-menu')) closeMenus(); });

  function changeSize(kind, amount, initial) {
    if (kind === 'height') {
      prefs.mode = 'edit'; prefs.ratio = clamp((initial + amount) / innerHeight, 0.3, 0.8);
    } else prefs[kind] = clamp(initial + amount, kind === 'left' ? 220 : 260, kind === 'left' ? 440 : 480);
    apply();
  }
  function finishDrag() {
    if (!drag) return;
    const current = drag; drag = null;
    current.overlay.remove(); current.el.classList.remove('dragging');
    if (current.el.hasPointerCapture(current.pointerId)) current.el.releasePointerCapture(current.pointerId);
    remember();
  }
  for (const [id, kind, label] of [['kw-media-splitter', 'left', 'Largura da biblioteca'],
    ['v-splitter', 'right', 'Largura das propriedades'], ['h-splitter', 'height', 'Altura do monitor']]) {
    const el = $(id); el.tabIndex = 0; el.setAttribute('role', 'separator');
    el.setAttribute('aria-label', label);
    el.setAttribute('aria-orientation', kind === 'height' ? 'horizontal' : 'vertical');
    el.addEventListener('mousedown', e => { if (enabled) e.stopImmediatePropagation(); }, true);
    el.addEventListener('pointerdown', e => {
      if (!enabled || e.button !== 0) return;
      e.preventDefault(); e.stopPropagation(); finishDrag();
      const box = (kind === 'left' ? $('media-lib') : kind === 'right' ? $('properties-panel') : $('main-area')).getBoundingClientRect();
      const overlay = document.createElement('div'); overlay.className = 'splitter-drag-overlay';
      overlay.style.cursor = kind === 'height' ? 'ns-resize' : 'ew-resize'; document.body.append(overlay);
      drag = {el, kind, overlay, pointerId: e.pointerId, start: kind === 'height' ? e.clientY : e.clientX,
        size: kind === 'height' ? box.height : box.width};
      el.classList.add('dragging'); el.setPointerCapture(e.pointerId);
    });
    el.addEventListener('pointermove', e => {
      if (!drag || drag.el !== el) return;
      const delta = (kind === 'height' ? e.clientY : e.clientX) - drag.start;
      changeSize(kind, kind === 'right' ? -delta : delta, drag.size);
    });
    for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) el.addEventListener(event, finishDrag);
    el.addEventListener('keydown', e => {
      if (!enabled) return;
      const keys = kind === 'height' ? ['ArrowUp', 'ArrowDown'] : ['ArrowLeft', 'ArrowRight'];
      if (!keys.includes(e.key) && e.key !== 'Home') return;
      e.preventDefault(); e.stopPropagation();
      const size = kind === 'height' ? $('main-area').offsetHeight : (kind === 'left' ? $('media-lib') : $('properties-panel')).offsetWidth;
      if (e.key === 'Home') { if (kind === 'height') prefs.ratio = defaults.ratio; else prefs[kind] = defaults[kind]; apply(); }
      else changeSize(kind, (e.key === keys[1] ? 16 : -16) * (kind === 'right' ? -1 : 1), size);
      remember();
    });
  }
  window.addEventListener('blur', finishDrag);
  window.addEventListener('resize', apply);
  window.addEventListener('pywebviewready', () => { if (override === null) setEnabled(true, false); });
  window.KlipeWorkspace = {setEnabled, reset, getState: () => ({...prefs, enabled})};
  setEnabled(override !== null ? override : document.body.dataset.klipeDesktop === 'true', override !== null);
  apply();
})();
