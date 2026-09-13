(target) => {
  function path(el) {
    if (!el || el.nodeType !== 1) return '';
    if (el === document.documentElement) return 'html';
    const root = el.getRootNode();
    const prefix = root.host ? path(root.host) + ' >>> ' : '';
    if (el.id && root.querySelectorAll('#' + CSS.escape(el.id)).length === 1)
      return prefix + '#' + CSS.escape(el.id);
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && node !== document.documentElement) {
      if (node.id && root.querySelectorAll('#' + CSS.escape(node.id)).length === 1) {
        parts.unshift('#' + CSS.escape(node.id)); break;
      }
      let sel = node.tagName.toLowerCase();
      const parent = node.parentElement;
      const siblings = [...(parent || root).children].filter(c => c.tagName === node.tagName);
      if (siblings.length > 1) sel += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
      parts.unshift(sel); node = parent;
    }
    return prefix + parts.join(' > ');
  }
  const all = root => [...root.querySelectorAll('*')].flatMap(el => [el, ...(el.shadowRoot ? all(el.shadowRoot) : [])]);
  const visible = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const styling = el => {
    const s = getComputedStyle(el);
    return Object.fromEntries(['outline-style','outline-width','outline-color','outline-offset','box-shadow','border-color','border-width','background-color','color'].map(k=>[k,s.getPropertyValue(k)]));
  };
  const receipt = el => {
    if (!el || !visible(el)) return null;
    const r = el.getBoundingClientRect();
    const points = [];
    for (const x of [.2, .5, .8]) for (const y of [.2, .5, .8]) {
      const px = r.left + r.width*x, py = r.top + r.height*y;
      let hit = document.elementFromPoint(px, py);
      while (hit && hit.shadowRoot && hit.shadowRoot.elementFromPoint) {
        const child = hit.shadowRoot.elementFromPoint(px, py);
        if (!child || child === hit) break;
        hit = child;
      }
      let ancestor = hit;
      while (ancestor && ancestor !== el) ancestor = ancestor.parentElement || ancestor.getRootNode().host;
      points.push({x:px, y:py, hit:path(hit), exposed:ancestor === el});
    }
    return {selector:path(el), tag:el.tagName.toLowerCase(), role:el.getAttribute('role'),
      bbox:[r.x,r.y,r.width,r.height], focus_visible:el.matches(':focus-visible'),
      editable:el.isContentEditable || (!el.disabled && !el.readOnly &&
        (el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' &&
          ['text','search','tel','url','email','password','number'].includes(el.type)))),
      styles:styling(el),
      exposed_samples:points.filter(p=>p.exposed).length, samples:points};
  };
  let active = document.activeElement;
  while (active && active.shadowRoot && active.shadowRoot.activeElement) active = active.shadowRoot.activeElement;
  const elements = all(document);
  return {url:location.href, target:receipt(target), focus:receipt(active), viewport:[innerWidth,innerHeight], scroll:[scrollX,scrollY],
    focus_styles:Object.fromEntries(elements.filter(el=>visible(el) && !el.disabled && el.tabIndex>=0).map(el=>[path(el),styling(el)])),
    dialogs:elements.filter(el=>el.matches('dialog[open],[role=dialog][aria-modal=true],[role=alertdialog][aria-modal=true]') && visible(el)).map(receipt),
    focusable:elements.filter(el=>visible(el) && !el.disabled && !el.closest('[inert]') && el.tabIndex >= 0).map(el=>path(el))};
}
