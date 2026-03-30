window.showConfirmModal = function(options) {
  const {
    title,
    text,
    confirmText = 'Подтвердить',
    cancelText = 'Отмена',
    isDanger = false,
    onConfirm,
  } = options;

  const overlay = document.getElementById('globalModalOverlay');
  document.getElementById('globalModalTitle').textContent = title;
  document.getElementById('globalModalText').textContent = text;

  let btnCancel  = document.getElementById('globalModalCancel');
  let btnConfirm = document.getElementById('globalModalConfirm');

  // Clone to drop old listeners
  const newCancel  = btnCancel.cloneNode(true);
  const newConfirm = btnConfirm.cloneNode(true);
  btnCancel.replaceWith(newCancel);
  btnConfirm.replaceWith(newConfirm);
  btnCancel  = newCancel;
  btnConfirm = newConfirm;

  btnCancel.textContent  = cancelText;
  btnConfirm.textContent = confirmText;
  btnConfirm.className   = isDanger ? 'btn btn--danger' : 'btn btn--primary';
  btnCancel.style.display = cancelText ? 'inline-flex' : 'none';

  var previousFocus = document.activeElement;

  const close = () => {
    overlay.classList.remove('modal-overlay--active');
    document.removeEventListener('keydown', onKeydown);
    if (previousFocus) previousFocus.focus();
  };

  const onKeydown = (e) => {
    if (e.key === 'Escape') { close(); return; }
    if (e.key === 'Tab') {
      var focusable = overlay.querySelectorAll('button:not([style*="display: none"]):not([style*="display:none"])');
      if (focusable.length === 0) return;
      var first = focusable[0];
      var last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
  };

  btnCancel.addEventListener('click', close);
  btnConfirm.addEventListener('click', () => { if (onConfirm) onConfirm(); close(); });
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); }, { once: true });
  document.addEventListener('keydown', onKeydown);

  overlay.classList.add('modal-overlay--active');
  btnConfirm.focus();
};
