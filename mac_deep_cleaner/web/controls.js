/* Accessible custom dropdowns. Native selects remain hidden as the data model. */
"use strict";
window.Dropdowns = (() => {
  let opened = null;
  let menu = null;
  let active = 0;
  let query = "";
  let queryTimer;
  const chevron =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg>';
  const check =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4 10-10"/></svg>';
  const model = () => opened && document.getElementById(opened);
  const trigger = (id = opened) => document.getElementById(`${id}Control`);
  const options = () => [...(model()?.options || [])];

  function close(restore = false) {
    const id = opened;
    if (trigger(id)) {
      trigger(id).setAttribute("aria-expanded", "false");
      trigger(id).removeAttribute("aria-activedescendant");
    }
    if (
      typeof menu?.hidePopover === "function" &&
      menu.matches(":popover-open")
    )
      menu.hidePopover();
    menu?.remove();
    menu = null;
    opened = null;
    query = "";
    clearTimeout(queryTimer);
    if (restore) trigger(id)?.focus({ preventScroll: true });
  }

  function position() {
    if (!menu || !trigger()) return;
    const box = trigger().getBoundingClientRect();
    const margin = 12;
    if (box.bottom < margin || box.top > innerHeight - margin) return close();
    const width = Math.min(
      Math.max(box.width, opened === "categoryFilter" ? 270 : 190),
      innerWidth - margin * 2,
    );
    const below = innerHeight - box.bottom - margin - 6;
    const above = box.top - margin - 6;
    const placeAbove =
      below < Math.min(230, menu.scrollHeight) && above > below;
    menu.style.width = `${width}px`;
    menu.style.maxHeight = `${Math.max(60, Math.min(310, placeAbove ? above : below))}px`;
    menu.style.left = `${Math.max(margin, Math.min(box.left, innerWidth - margin - width))}px`;
    const height = menu.getBoundingClientRect().height;
    menu.style.top = `${placeAbove ? Math.max(margin, box.top - height - 6) : box.bottom + 6}px`;
    menu.dataset.direction = placeAbove ? "up" : "down";
  }

  function highlight(index, scroll = true) {
    const choices = options();
    if (!choices.length) return;
    active = (index + choices.length) % choices.length;
    const rows = [...menu.children];
    rows.forEach((row, i) => row.classList.toggle("is-active", i === active));
    trigger()?.setAttribute(
      "aria-activedescendant",
      `${opened}Option${active}`,
    );
    const row = rows[active];
    if (scroll && row) {
      if (row.offsetTop < menu.scrollTop) menu.scrollTop = row.offsetTop;
      else if (
        row.offsetTop + row.offsetHeight >
        menu.scrollTop + menu.clientHeight
      )
        menu.scrollTop = row.offsetTop + row.offsetHeight - menu.clientHeight;
    }
  }

  function populate() {
    const select = model();
    if (!select || !menu) return;
    menu.replaceChildren();
    [...select.options].forEach((option, index) => {
      const row = document.createElement("div");
      row.className = "dropdown-option";
      row.id = `${opened}Option${index}`;
      row.setAttribute("role", "option");
      row.setAttribute("aria-selected", String(option.selected));
      row.setAttribute("aria-disabled", String(option.disabled));
      row.dataset.optionIndex = String(index);
      const label = document.createElement("span");
      label.textContent = option.textContent;
      label.title = option.textContent;
      row.append(label);
      row.insertAdjacentHTML("beforeend", check);
      menu.append(row);
    });
    highlight(Math.min(active, select.options.length - 1), false);
    position();
  }

  function open(id, index) {
    if (opened === id) return close(true);
    close();
    const select = document.getElementById(id);
    if (!select || select.disabled || !select.options.length) return;
    opened = id;
    active = index ?? Math.max(0, select.selectedIndex);
    menu = document.createElement("div");
    menu.id = `${id}List`;
    menu.className = "dropdown-menu";
    menu.setAttribute("role", "listbox");
    menu.setAttribute(
      "aria-label",
      select.getAttribute("aria-label") || "Options",
    );
    if (typeof menu.showPopover === "function")
      menu.setAttribute("popover", "manual");
    document.body.append(menu);
    trigger()?.setAttribute("aria-expanded", "true");
    if (menu.hasAttribute("popover")) menu.showPopover();
    populate();
    highlight(active);
    trigger()?.focus({ preventScroll: true });
  }

  function choose(index) {
    const select = model();
    if (!select?.options[index] || select.options[index].disabled) return;
    const id = opened;
    select.selectedIndex = index;
    close();
    select.dispatchEvent(new Event("change", { bubbles: true }));
    trigger(id)?.focus({ preventScroll: true });
  }

  function enhance(root = document) {
    for (const select of root.querySelectorAll("select:not([data-enhanced])")) {
      select.dataset.enhanced = "true";
      const wrapper = document.createElement("div");
      wrapper.className = `dropdown ${select.className}`;
      select.before(wrapper);
      wrapper.append(select);
      select.hidden = true;
      select.tabIndex = -1;
      select.setAttribute("aria-hidden", "true");
      const control = document.createElement("button");
      control.type = "button";
      control.id = `${select.id}Control`;
      control.className = "dropdown-trigger";
      control.dataset.dropdown = select.id;
      control.setAttribute("role", "combobox");
      control.setAttribute("aria-haspopup", "listbox");
      control.setAttribute("aria-expanded", String(opened === select.id));
      control.setAttribute("aria-controls", `${select.id}List`);
      control.setAttribute(
        "aria-label",
        select.getAttribute("aria-label") || "Options",
      );
      control.disabled = select.disabled;
      const label = document.createElement("span");
      label.textContent = select.selectedOptions[0]?.textContent || "Choose";
      control.append(label);
      control.insertAdjacentHTML("beforeend", chevron);
      wrapper.append(control);
    }
    if (opened) {
      if (!model() || !trigger()) close();
      else populate();
    }
  }

  document.addEventListener("click", (event) => {
    const control = event.target.closest("[data-dropdown]");
    if (control) return open(control.dataset.dropdown);
    const option = event.target.closest("[data-option-index]");
    if (option && menu?.contains(option))
      return choose(Number(option.dataset.optionIndex));
    if (opened && !menu?.contains(event.target)) close();
  });
  document.addEventListener("pointermove", (event) => {
    const option = event.target.closest("[data-option-index]");
    if (option && menu?.contains(option))
      highlight(Number(option.dataset.optionIndex), false);
  });
  document.addEventListener(
    "keydown",
    (event) => {
      const control = event.target.closest("[data-dropdown]");
      if (!control) return;
      const select = document.getElementById(control.dataset.dropdown);
      const isOpen = opened === select.id;
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        let index = isOpen ? active : Math.max(0, select.selectedIndex);
        if (event.key === "Home") index = 0;
        else if (event.key === "End") index = select.options.length - 1;
        else if (isOpen) index += event.key === "ArrowDown" ? 1 : -1;
        if (!isOpen) open(select.id, index);
        else highlight(index);
      } else if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (isOpen) choose(active);
        else open(select.id);
      } else if (event.key === "Escape" && isOpen) {
        event.preventDefault();
        event.stopPropagation();
        close(true);
      } else if (event.key === "Tab") close();
      else if (
        event.key.length === 1 &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey
      ) {
        event.preventDefault();
        if (!isOpen) open(select.id);
        query += event.key.toLocaleLowerCase();
        clearTimeout(queryTimer);
        queryTimer = setTimeout(() => {
          query = "";
        }, 700);
        const choices = options();
        const start = query.length === 1 ? active + 1 : active;
        for (let offset = 0; offset < choices.length; offset++) {
          const index = (start + offset) % choices.length;
          if (
            choices[index].textContent.toLocaleLowerCase().startsWith(query)
          ) {
            highlight(index);
            break;
          }
        }
      }
    },
    true,
  );
  addEventListener("resize", position);
  addEventListener(
    "scroll",
    (event) => {
      if (opened && event.target !== menu) position();
    },
    true,
  );
  return { enhance, close };
})();
