"""JavaScript helpers shared by every in-page detector script."""

# Visibility, shadow-DOM-aware querying and hit-testing, and a stable CSS path
# for reporting. Each detector script is built as prefix + JS_HELPERS + body.
JS_HELPERS = """
  function visible(el) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function queryAll(root, selector) {
    const out = [...root.querySelectorAll(root.host && selector === 'body *' ? '*' : selector)];
    for (const el of root.querySelectorAll('*')) if (el.shadowRoot) out.push(...queryAll(el.shadowRoot, selector));
    return out;
  }
  function deepHit(x, y) {
    let el = document.elementFromPoint(x, y), next;
    while (el && el.shadowRoot && (next = el.shadowRoot.elementFromPoint(x, y)) && next !== el) el = next;
    return el;
  }
  function containsDeep(parent, child) {
    for (let el = child; el; el = el.parentElement || el.getRootNode().host) if (el === parent) return true;
    return false;
  }
  function cssPath(el) {
    if (el === document.documentElement) return 'html';
    const root = el.getRootNode();
    const prefix = root.host ? cssPath(root.host) + ' >>> ' : '';
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
"""
