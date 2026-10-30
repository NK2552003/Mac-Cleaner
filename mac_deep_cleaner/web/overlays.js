"use strict";

// Keep dialogs in the top layer until their exit finishes. This preserves focus
// trapping, backdrop hit testing, and stacked confirmations during animation.
const Overlays = (() => {
  const closing = new WeakMap();
  function open(dialog) {
    closing.get(dialog)?.cancel();
    dialog.classList.remove("is-closing");
    if (!dialog.open) {
      dialog.showModal();
      dialog.scrollTop = 0;
    }
  }
  function close(dialog) {
    if (!dialog.open) return Promise.resolve();
    if (closing.has(dialog)) return closing.get(dialog).promise;
    let resolve, timer;
    const promise = new Promise(done => { resolve = done; });
    const cleanup = () => {
      clearTimeout(timer);
      dialog.removeEventListener("animationend", ended);
      closing.delete(dialog);
      dialog.classList.remove("is-closing");
    };
    const finish = () => { cleanup(); dialog.close(); resolve(); };
    const ended = event => {
      if (event.target === dialog && (event.animationName === "overlay-out" || event.animationName === "drawer-out")) finish();
    };
    closing.set(dialog, { promise, cancel() { cleanup(); resolve(); } });
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) finish();
    else {
      dialog.addEventListener("animationend", ended);
      dialog.classList.add("is-closing");
      timer = setTimeout(finish, 260);
    }
    return promise;
  }
  function bind(dialog, dismiss) {
    let beganOutside = false;
    const outside = event => {
      const b = dialog.getBoundingClientRect();
      return event.target === dialog && (event.clientX < b.left || event.clientX > b.right || event.clientY < b.top || event.clientY > b.bottom);
    };
    dialog.addEventListener("pointerdown", event => { beganOutside = outside(event); });
    dialog.addEventListener("click", event => {
      if (beganOutside && outside(event)) dismiss();
      beganOutside = false;
    });
    dialog.addEventListener("cancel", event => { event.preventDefault(); dismiss(); });
  }
  return { open, close, bind };
})();
