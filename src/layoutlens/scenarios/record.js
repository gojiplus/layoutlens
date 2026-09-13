(() => {
  if (window.__layoutlensRecording) return;
  window.__layoutlensRecording = true;
  const pending = new Set();
  const emit = (kind, detail) => {
    const promise = window.__layoutlensEvent({kind, url:location.href, detail});
    pending.add(promise);
    promise.finally(()=>pending.delete(promise));
  };
  window.__layoutlensFlush = () => Promise.all([...pending]);
  for (const kind of ['focusin','focusout','keydown','keyup','click','pointerdown','pointermove','pointerup','pointerover','input','change','submit','dragstart','dragend','dragover','drop']) {
    document.addEventListener(kind, event => {
      const el = event.composedPath()[0];
      emit(kind, {tag:el.tagName || '', id:el.id || '', key:kind.startsWith('key') ?
        (event.key.length === 1 ? '[character]' : event.key) : undefined,
        button:event.button, x:event.clientX, y:event.clientY, input_type:event.inputType});
    }, true);
  }
  for (const kind of ['hashchange','popstate']) window.addEventListener(kind,()=>emit(kind,{}));
  emit('document',{});
})();
