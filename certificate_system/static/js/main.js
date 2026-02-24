document.addEventListener('DOMContentLoaded', () => {
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach((alert) => {
    setTimeout(() => {
      const closeBtn = alert.querySelector('.btn-close');
      if (closeBtn) {
        closeBtn.click();
      }
    }, 5000);
  });

  const portalState = new WeakMap();
  let activePortaled = null;

  const shouldPortalDropdownMenu = (menuEl) => {
    if (!menuEl) return false;
    if (menuEl.closest('.table-responsive')) return true;

    let node = menuEl.parentElement;
    while (node && node !== document.body && node !== document.documentElement) {
      const style = window.getComputedStyle(node);
      const overflowX = style.overflowX;
      const overflowY = style.overflowY;
      if ([overflowX, overflowY].some((v) => ['auto', 'scroll', 'hidden', 'clip'].includes(v))) {
        return true;
      }
      node = node.parentElement;
    }
    return false;
  };

  const positionPortaledMenu = (toggleEl, menuEl) => {
    if (!toggleEl || !menuEl) return;

    const toggleRect = toggleEl.getBoundingClientRect();
    const menuRect = menuEl.getBoundingClientRect();

    let top = toggleRect.bottom;
    let left = toggleRect.right - menuRect.width;

    const padding = 8;
    const viewportW = window.innerWidth;
    const viewportH = window.innerHeight;

    if (left < padding) left = padding;
    if (left + menuRect.width > viewportW - padding) {
      left = Math.max(padding, viewportW - padding - menuRect.width);
    }

    if (top + menuRect.height > viewportH - padding) {
      const openUpTop = toggleRect.top - menuRect.height;
      if (openUpTop >= padding) top = openUpTop;
    }

    menuEl.style.position = 'fixed';
    menuEl.style.top = `${Math.round(top)}px`;
    menuEl.style.left = `${Math.round(left)}px`;
  };

  const handleViewportChange = () => {
    if (!activePortaled) return;
    positionPortaledMenu(activePortaled.toggleEl, activePortaled.menuEl);
  };

  window.addEventListener('scroll', handleViewportChange, true);
  window.addEventListener('resize', handleViewportChange);

  document.addEventListener('shown.bs.dropdown', (event) => {
    const toggleEl = event.target;
    const dropdownEl = toggleEl?.closest?.('.dropdown');
    const menuEl = dropdownEl?.querySelector?.('.dropdown-menu');
    if (!menuEl) return;

    if (!shouldPortalDropdownMenu(menuEl)) return;

    if (!portalState.has(menuEl)) {
      portalState.set(menuEl, {
        parent: menuEl.parentElement,
        nextSibling: menuEl.nextSibling,
      });
    }

    if (menuEl.parentElement !== document.body) {
      document.body.appendChild(menuEl);
    }
    menuEl.classList.add('dropdown-menu-portal');

    positionPortaledMenu(toggleEl, menuEl);
    activePortaled = { toggleEl, menuEl };
  });

  document.addEventListener('hidden.bs.dropdown', (event) => {
    const toggleEl = event.target;
    const dropdownEl = toggleEl?.closest?.('.dropdown');
    const menuEl = dropdownEl?.querySelector?.('.dropdown-menu') || activePortaled?.menuEl;
    if (!menuEl) return;

    const state = portalState.get(menuEl);
    if (!state) return;

    if (menuEl.parentElement === document.body && state.parent) {
      if (state.nextSibling && state.nextSibling.parentNode === state.parent) {
        state.parent.insertBefore(menuEl, state.nextSibling);
      } else {
        state.parent.appendChild(menuEl);
      }
    }

    menuEl.classList.remove('dropdown-menu-portal');
    menuEl.style.position = '';
    menuEl.style.top = '';
    menuEl.style.left = '';

    if (activePortaled?.menuEl === menuEl) activePortaled = null;
  });
});
