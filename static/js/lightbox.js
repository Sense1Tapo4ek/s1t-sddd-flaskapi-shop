(function() {
  'use strict';
  let lb = null;

  function ensure() {
    if (lb) return;
    lb = document.createElement('div');
    lb.className = 'lightbox';
    lb.setAttribute('role', 'dialog');
    lb.setAttribute('aria-modal', 'true');
    lb.setAttribute('aria-label', 'Просмотр изображения');
    lb.innerHTML = '<button class="lightbox__close" aria-label="Закрыть">&times;</button>' +
                   '<img src="" alt="Увеличенное изображение">';
    lb.addEventListener('click', function(e) {
      if (e.target === lb || e.target.classList.contains('lightbox__close')) close();
    });
    document.body.appendChild(lb);
  }

  function close() {
    if (lb) lb.classList.remove('lightbox--active');
  }

  window.openLightbox = function(src) {
    ensure();
    lb.querySelector('img').src = src;
    lb.classList.add('lightbox--active');
  };

  window.closeLightbox = close;

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') close();
  });
})();
