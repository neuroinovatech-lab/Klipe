/* Git updates are explicit and never save or reload an open project. */
(() => {
  let state = {};
  let timer;
  const status = () => document.getElementById('klipe-update-status');
  function show(data) {
    state = data;
    const busy = ['checking', 'updating'].includes(data.phase);
    status().textContent = data.message || '';
    document.getElementById('klipe-update-version').textContent = data.current
      ? data.current.slice(0, 8) + (data.latest !== data.current ? ' → ' + data.latest.slice(0, 8) : '') : '';
    document.getElementById('klipe-update-check').disabled = busy || data.phase === 'updated';
    document.getElementById('klipe-update-apply').disabled = data.phase !== 'available';
    clearTimeout(timer);
    if (busy) timer = setTimeout(load, 1000);
  }
  async function load() {
    document.getElementById('klipe-update-check').disabled = true;
    try {
      const response = await fetch('/api/updates');
      if (!response.ok) throw new Error('Reinicie o Klipe para ativar o atualizador.');
      show(await response.json());
    } catch (error) {
      status().textContent = error.message;
      document.getElementById('klipe-update-check').disabled = false;
    }
  }
  async function run(action) {
    try {
      if (!state.token) {
        await load();
        if (!state.token) throw new Error('Reinicie o Klipe para ativar o atualizador.');
      }
      if (action === 'apply') {
        const sync = NLE.liveSync;
        if (sync.saving || sync.fingerprint() !== sync.savedFingerprint) {
          throw new Error('Salve o projeto antes de atualizar.');
        }
        if (!confirm('Salvou todos os projetos nas outras janelas? Atualizar o Klipe agora? Depois, feche e abra o aplicativo.')) return;
      }
      const response = await fetch('/api/updates/' + action, {method: 'POST', headers: {
        'X-Klipe-Update': state.token, 'X-Klipe-Version': state.latest || '',
      }});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Nao foi possivel atualizar.');
      await load();
    } catch (error) { status().textContent = error.message; }
  }
  window.KlipeUpdates = {load, run};
})();
