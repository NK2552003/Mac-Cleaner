/* One vector mascot, feature-specific details, and a clock that survives redraws. */
const LoaderUI = (() => {
  const clocks = new Map();
  const features = {
    clean: ['Storage cleanup', 'clean'],
    apps: ['Applications', 'apps'],
    big: ['Large files', 'file'],
    dups: ['Duplicates', 'dup'],
    optimize: ['Optimize your Mac', 'nav_optimize'],
    disks: ['Disks & volumes', 'nav_disks'],
    homebrew: ['Homebrew', 'nav_homebrew'],
    ghosts: ['Ghost Files', 'ghost'],
    care: ['Care center', 'nav_care'],
    'care-media': ['Similar media', 'photo'],
    'care-startup': ['Startup items', 'apps'],
    'care-slimming': ['App slimming', 'file'],
    settings: ['Settings', 'nav_settings'],
  };
  function visual(symbol) {
    const mark = P[symbol] || P.clean;
    return `<svg class="loader-visual" viewBox="0 0 120 120" aria-hidden="true" focusable="false">
      <circle class="loader-halo" cx="60" cy="60" r="50"/>
      <circle class="loader-orbit-guide" cx="60" cy="60" r="49"/>
      <g class="loader-motion loader-orbit">
        <path class="loader-orbit-arc" d="M60 11a49 49 0 0 1 49 49"/>
        <circle class="loader-orbit-dot" cx="109" cy="60" r="2.6"/>
        <g class="loader-traveler" transform="translate(3 51) scale(.72)" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${mark}</g>
      </g>
      <g class="loader-motion loader-spark loader-spark-one"><path d="M23 24v7m-3.5-3.5h7"/></g>
      <g class="loader-motion loader-spark loader-spark-two"><path d="M91 29v5m-2.5-2.5h5"/></g>
      <ellipse class="loader-shadow" cx="60" cy="103" rx="23" ry="3"/>
      <g class="loader-motion loader-mascot">
        <path class="loader-fur" d="M39 49c-3-13-2-30 3-33 5 3 8 16 8 27m20 0c0-11 3-24 8-27 5 3 6 20 3 33"/>
        <path class="loader-ear" d="M42 43c-1-7-1-15 1-19 3 5 4 11 4 18m26 0c0-7 1-13 4-18 2 4 2 12 1 19"/>
        <path class="loader-fur" d="M27 73c0-23 13-34 33-34s33 11 33 34c0 22-12 30-33 30S27 95 27 73Z"/>
        <ellipse class="loader-belly" cx="60" cy="81" rx="24" ry="21"/>
        <g class="loader-eyes"><ellipse cx="46" cy="59" rx="5.2" ry="6"/><ellipse cx="74" cy="59" rx="5.2" ry="6"/></g>
        <g class="loader-ink"><circle cx="47" cy="59" r="2.6"/><circle cx="73" cy="59" r="2.6"/><ellipse cx="60" cy="59" rx="3.2" ry="1.8"/></g>
        <g class="loader-eye-light"><circle cx="47.8" cy="58" r=".8"/><circle cx="73.8" cy="58" r=".8"/></g>
        <g class="loader-whiskers"><path d="m22 63 12 1m-13 4 13-1m52-3 12-1m-12 4 13 1"/></g>
        <g class="loader-belly-marks"><path d="m47 76 3-3 3 3m4-3 3-3 3 3m4 3 3-3 3 3m-31 8 3-3 3 3m4-1 3-3 3 3m4 0 3-3 3 3m4 1 3-3 3 3"/></g>
        <g class="loader-motion loader-leaf"><path class="loader-leaf-fill" d="M59 39c-13-15 0-25 14-16-1 10-7 14-14 16Z"/><path class="loader-leaf-vein" d="M56 43c6-5 5-12 11-20"/></g>
      </g>
      <g class="loader-feature-badge"><circle cx="94" cy="94" r="13"/><g transform="translate(85 85) scale(.75)" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${mark}</g></g>
    </svg>`;
  }
  function render(message, {feature = 'clean', actions = '', percent = null, key = '', embedded = false} = {}) {
    if (!features[feature]) feature = 'clean';
    const [label, symbol] = features[feature];
    const value = typeof percent === 'number' && Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : null;
    return `<div class="scan-indicator brand-loader${embedded ? ' is-embedded' : ''}" data-feature="${feature}" data-loader-key="${esc(key || feature)}" role="status" aria-atomic="true">
      ${visual(symbol)}
      <div class="loader-copy"><span class="loader-label">${esc(I18n.t(label))}</span><p class="loader-message">${esc(I18n.t(message || 'Scanning in progress'))}</p></div>
      ${value === null ? '' : `<span class="loader-value" data-no-translate>${Math.round(value)}%</span>`}
      ${actions ? `<div class="loader-actions">${actions}</div>` : ''}
    </div>`;
  }
  function sync(root = document) {
    const now = document.timeline?.currentTime;
    if (typeof now !== 'number') return;
    for (const loader of root.querySelectorAll('.brand-loader')) {
      const key = loader.dataset.loaderKey;
      if (!clocks.has(key)) clocks.set(key, now);
      // Replacing DOM during polling must not restart the animation at frame zero.
      const animations = loader.querySelector('.loader-visual')?.getAnimations({subtree:true}) || [];
      for (const animation of animations) animation.startTime = clocks.get(key);
    }
    while (clocks.size > 64) clocks.delete(clocks.keys().next().value);
  }
  return {render, sync};
})();
