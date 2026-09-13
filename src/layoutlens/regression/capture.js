() => {
  function elements(root) {
    const out = [];
    for (const el of root.querySelectorAll('*')) {
      out.push(el);
      if (el.shadowRoot) out.push(...elements(el.shadowRoot));
    }
    return out;
  }
  function path(el) {
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
  const all = elements(document);
  const ids = new Map(all.map((el, i) => [el, String(i)]));
  const rect = r => [r.x + scrollX, r.y + scrollY, r.width, r.height];
  const nodes = all.map(el => {
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    const styles = Object.fromEntries([...cs].map(p => [p, cs.getPropertyValue(p)]));
    const textNodes = [...el.childNodes].filter(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
    const textRects = textNodes.flatMap(n => {
      const range = document.createRange(); range.selectNodeContents(n);
      return [...range.getClientRects()].map(rect);
    });
    let ancestor = el, visible = r.width > 0 && r.height > 0;
    while (ancestor) {
      const style = getComputedStyle(ancestor);
      if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' || Number(style.opacity) === 0) visible = false;
      ancestor = ancestor.parentElement || ancestor.getRootNode().host;
    }
    const parent = el.parentElement || el.getRootNode().host;
    const focusable = !el.disabled && !el.closest('[inert]') && el.matches('a[href],button,input,select,textarea,[tabindex],summary,[contenteditable=true]');
    return {key: ids.get(el), selector: path(el), parent: parent ? ids.get(parent) : null,
      tag: el.tagName.toLowerCase(), attributes: Object.fromEntries([...el.attributes].map(a => [a.name, a.value])),
      bbox: rect(r), styles, text: textNodes.map(n => n.textContent).join('').trim(), visible,
      focusable: visible && focusable, interactive: focusable || el.hasAttribute('onclick'),
      control_state: el.matches('input,textarea,select') ? {
        value: el.type === 'password' ? '[redacted]' : el.value,
        checked: el.checked, selected_index: el.selectedIndex, disabled: el.disabled,
        read_only: el.readOnly
      } : {},
      focused: el === (el.getRootNode().activeElement || document.activeElement), text_rects: textRects};
  });
  return {nodes, dom: document.documentElement.outerHTML,
    geometry: {width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight,
      viewport_width: innerWidth, viewport_height: innerHeight},
    loading: {fonts: [...document.fonts].map(f => ({family: f.family, status: f.status, weight: f.weight, style: f.style})),
      images: [...document.images].map(i => ({src: i.currentSrc, complete: i.complete, width: i.naturalWidth})),
      assets: performance.getEntriesByType('resource').map(r => ({name: r.name, type: r.initiatorType, size: r.decodedBodySize, status: r.responseStatus})),
      ready_state: document.readyState},
    environment: {viewport: [innerWidth, innerHeight], dpr: devicePixelRatio, user_agent: navigator.userAgent,
      platform: navigator.platform, locale: navigator.language, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      color_scheme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' :
        matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'no-preference',
      reduced_motion: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'reduce' : 'no-preference',
      has_touch: navigator.maxTouchPoints > 0,
      scroll: [scrollX, scrollY]},
    gaps: all.filter(el => el.matches('iframe,canvas,video')).map(el => 'opaque content: ' + path(el))};
}
