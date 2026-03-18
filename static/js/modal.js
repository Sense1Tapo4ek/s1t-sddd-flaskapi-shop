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

  const close = () => {
    overlay.classList.remove('modal-overlay--active');
    document.removeEventListener('keydown', onEsc);
  };
  const onEsc = (e) => { if (e.key === 'Escape') close(); };

  btnCancel.addEventListener('click', close);
  btnConfirm.addEventListener('click', () => { if (onConfirm) onConfirm(); close(); });
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); }, { once: true });
  document.addEventListener('keydown', onEsc);

  overlay.classList.add('modal-overlay--active');
};
