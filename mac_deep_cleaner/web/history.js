/* Trash recovery is part of storage cleanup, independent of optional features. */
const HistoryUI = (() => {
  let records = [], loading = false, restoring = false, error = '', request = 0;
  const text = value => esc(I18n.t(value));
  function render() {
    if (detailKind !== 'history') return;
    $('detailDialog').innerHTML = `<div class="drawer-head"><h2>${text('Cleanup history')}</h2>${button('', 'close-detail', {style:'ghost icon-only',symbol:'x',aria:I18n.t('Close')})}</div>
      <div class="drawer-body cleanup-history"><p>${text('Up to 1,000 recent Trash moves. Restore is available while the recorded item is unchanged and its original location is free. Permanent deletion and command-based cleanup cannot be undone.')}</p>
      ${loading ? scanIndicator('Working…', {feature:'clean',key:'history'}) : ''}
      ${error ? `<div class="error-banner" role="alert">${esc(error)}</div>` : ''}
      ${records.map(record => `<article class="history-row"><div><h3 data-no-translate>${esc(record.original.split('/').pop())}</h3><p class="path" data-no-translate>${esc(record.original)}</p><small>${esc(new Date(record.created*1000).toLocaleString(I18n.locale()))} · ${text(record.status === 'moved' && !record.available ? 'Trash entry unavailable' : ({moved:'Moved to Trash',restored:'Restored',interrupted:'Interrupted operation'}[record.status] || record.status))}${record.conflict ? ' · '+text('Original location occupied') : ''}</small></div>${button(I18n.t('Restore'), 'history-restore', {data:{id:record.id},disabled:loading || restoring || !!S.busy || S.scanning || !record.available || record.conflict})}</article>`).join('')}
      ${!loading && !error && !records.length ? `<p>${text('No recorded cleanup yet.')}</p>` : ''}</div>`;
    LoaderUI.sync($('detailDialog'));
  }
  async function open() {
    closeDetail();
    detailKind = 'history';
    const current = ++request;
    loading = true; error = ''; records = [];
    render(); Overlays.open($('detailDialog'));
    try {
      const data = await api('/api/history');
      if (current === request) records = data.history;
    } catch (e) { if (current === request) error = e.message; }
    finally { if (current === request) { loading = false; render(); } }
  }
  async function restore(id) {
    if (restoring || !canSelect() || !records.some(r => r.id === id && r.available && !r.conflict)) return;
    restoring = true; error = ''; render(); updateActivityStatus();
    try {
      await api('/api/history/restore', {id});
      records = (await api('/api/history')).history;
      await load();
      toast(I18n.t('Restored'));
    } catch (e) { error = e.message; }
    finally { restoring = false; render(); updateActivityStatus(); }
  }
  return {open, restore, isRunning:() => restoring};
})();
