/**
 * Image Editor — Cropper.js + JPEG quality control.
 * Usage:
 *   const blob = await window.openImageEditor(file);
 *   const blob = await window.openImageEditor(urlString);
 */
(function() {
  'use strict';

  const MODAL_HTML = `
    <div class="img-editor-overlay" id="imgEditorOverlay">
      <div class="img-editor-modal">
        <div class="img-editor-header">
          <span class="img-editor-title">Редактор изображения</span>
          <button class="img-editor-close" id="imgEditorClose">&times;</button>
        </div>
        <div class="img-editor-body">
          <div class="img-editor-canvas">
            <img id="imgEditorImage">
          </div>
          <div class="img-editor-panel">
            <div>
              <div class="img-editor-section-title">Соотношение сторон</div>
              <div class="img-editor-ratios" id="imgEditorRatios">
                <button class="btn btn--ghost btn--sm img-ratio-btn" data-ratio="NaN">Свободно</button>
                <button class="btn btn--ghost btn--sm img-ratio-btn" data-ratio="1">1:1</button>
                <button class="btn btn--ghost btn--sm img-ratio-btn" data-ratio="1.333">4:3</button>
                <button class="btn btn--ghost btn--sm img-ratio-btn" data-ratio="0.75">3:4</button>
                <button class="btn btn--ghost btn--sm img-ratio-btn" data-ratio="1.777">16:9</button>
                <button class="btn btn--ghost btn--sm img-ratio-btn" data-ratio="0.5625">9:16</button>
                <button class="btn btn--ghost btn--sm img-ratio-btn" data-ratio="1.5">3:2</button>
                <button class="btn btn--ghost btn--sm img-ratio-btn" data-ratio="0.666">2:3</button>
                <button class="btn btn--ghost btn--sm img-ratio-btn" data-ratio="2.333">21:9</button>
              </div>
            </div>
            <div>
              <div class="img-editor-section-title">
                Качество JPEG: <strong id="imgEditorQualityVal">100</strong>%
              </div>
              <input type="range" id="imgEditorQuality" min="10" max="100" value="100" step="5" class="img-editor-range">
            </div>
            <div>
              <div class="img-editor-section-title">Информация</div>
              <div class="img-editor-info" id="imgEditorInfo">
                <div>Разрешение: <strong id="imgEditorOrigRes">—</strong></div>
                <div>Вес до: <strong id="imgEditorWeightBefore">—</strong></div>
                <div style="margin-top: 6px;">Область кропа: <strong id="imgEditorCropSize">—</strong></div>
                <div>Результат: <strong id="imgEditorResultSize">—</strong></div>
                <div>Вес после: <strong id="imgEditorFileSize">—</strong></div>
              </div>
            </div>
            <div>
              <div class="img-editor-section-title">Подсказка</div>
              <div class="img-editor-info">
                Shift + перетаскивание угла — изменение размера с сохранением пропорций
              </div>
            </div>
          </div>
        </div>
        <div class="img-editor-footer">
          <button class="btn btn--ghost" id="imgEditorDownload">Скачать</button>
          <button class="btn btn--ghost" id="imgEditorCancel">Отмена</button>
          <button class="btn btn--primary" id="imgEditorApply">Применить</button>
        </div>
      </div>
    </div>
  `;

  const CROP_OPTS = { maxWidth: 1920, imageSmoothingEnabled: true, imageSmoothingQuality: 'high' };

  let modalEl = null;
  let cropper = null;
  let currentResolve = null;
  let currentReject = null;
  let updateTimer = null;

  function getQuality() {
    return parseInt(document.getElementById('imgEditorQuality').value, 10) / 100;
  }

  function formatSize(bytes) {
    const kb = bytes / 1024;
    return kb > 1024 ? (kb / 1024).toFixed(1) + ' MB' : Math.round(kb) + ' KB';
  }

  function ensureModal() {
    if (modalEl) return;
    document.body.insertAdjacentHTML('beforeend', MODAL_HTML);
    modalEl = document.getElementById('imgEditorOverlay');

    document.getElementById('imgEditorClose').addEventListener('click', cancel);
    document.getElementById('imgEditorCancel').addEventListener('click', cancel);
    modalEl.addEventListener('click', function(e) { if (e.target === modalEl) cancel(); });

    document.getElementById('imgEditorQuality').addEventListener('input', function() {
      document.getElementById('imgEditorQualityVal').textContent = this.value;
      scheduleUpdate();
    });

    document.getElementById('imgEditorRatios').addEventListener('click', function(e) {
      const btn = e.target.closest('.img-ratio-btn');
      if (!btn || !cropper) return;
      cropper.setAspectRatio(parseFloat(btn.dataset.ratio));
      this.querySelectorAll('.img-ratio-btn').forEach(function(b) {
        b.classList.remove('btn--primary');
        b.classList.add('btn--ghost');
      });
      btn.classList.add('btn--primary');
      btn.classList.remove('btn--ghost');
    });

    document.getElementById('imgEditorApply').addEventListener('click', apply);
    document.getElementById('imgEditorDownload').addEventListener('click', download);
  }

  function download() {
    if (!cropper) return;
    const canvas = cropper.getCroppedCanvas(CROP_OPTS);
    canvas.toBlob(function(blob) {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'image_' + Date.now() + '.jpg';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 'image/jpeg', getQuality());
  }

  function scheduleUpdate() {
    clearTimeout(updateTimer);
    updateTimer = setTimeout(updateInfo, 250);
  }

  function updateInfo() {
    if (!cropper) return;
    const data = cropper.getData(true);
    document.getElementById('imgEditorCropSize').textContent =
      Math.round(data.width) + ' x ' + Math.round(data.height) + ' px';

    const canvas = cropper.getCroppedCanvas(CROP_OPTS);
    document.getElementById('imgEditorResultSize').textContent =
      canvas.width + ' x ' + canvas.height + ' px';

    canvas.toBlob(function(blob) {
      if (!blob) return;
      document.getElementById('imgEditorFileSize').textContent = '~ ' + formatSize(blob.size);
    }, 'image/jpeg', getQuality());
  }

  function cancel() {
    const rej = currentReject;
    cleanup();
    if (rej) rej(new Error('cancelled'));
  }

  function apply() {
    if (!cropper || !currentResolve) return;
    const res = currentResolve;
    const canvas = cropper.getCroppedCanvas(CROP_OPTS);
    canvas.toBlob(function(blob) { cleanup(); res(blob); }, 'image/jpeg', getQuality());
  }

  function cleanup() {
    clearTimeout(updateTimer);
    if (cropper) { cropper.destroy(); cropper = null; }
    if (modalEl) {
      modalEl.style.display = 'none';
      modalEl.querySelectorAll('.img-ratio-btn').forEach(function(b) {
        b.classList.remove('btn--primary');
        b.classList.add('btn--ghost');
      });
    }
    currentResolve = null;
    currentReject = null;
  }

  function initEditor(imgSrc, fileSizeBytes) {
    ensureModal();
    const img = document.getElementById('imgEditorImage');
    img.src = imgSrc;
    modalEl.style.display = 'flex';

    document.getElementById('imgEditorQuality').value = 100;
    document.getElementById('imgEditorQualityVal').textContent = '100';
    document.getElementById('imgEditorOrigRes').textContent = '—';
    document.getElementById('imgEditorWeightBefore').textContent =
      fileSizeBytes > 0 ? formatSize(fileSizeBytes) : '—';
    document.getElementById('imgEditorCropSize').textContent = '—';
    document.getElementById('imgEditorResultSize').textContent = '—';
    document.getElementById('imgEditorFileSize').textContent = '—';

    img.onload = function() {
      if (cropper) cropper.destroy();
      document.getElementById('imgEditorOrigRes').textContent =
        img.naturalWidth + ' x ' + img.naturalHeight + ' px';
      cropper = new Cropper(img, {
        viewMode: 1, autoCropArea: 1, responsive: true,
        background: false, guides: true, highlight: true,
        cropend: scheduleUpdate, crop: scheduleUpdate,
        ready: function() { setTimeout(updateInfo, 200); },
      });
    };
  }

  window.openImageEditor = function(source) {
    return new Promise(function(resolve, reject) {
      currentResolve = resolve;
      currentReject = reject;
      if (typeof source === 'string') {
        fetch(source).then(function(r) { return r.blob(); }).then(function(blob) {
          initEditor(URL.createObjectURL(blob), blob.size);
        }).catch(function() { initEditor(source, 0); });
      } else {
        const reader = new FileReader();
        reader.onload = function(e) { initEditor(e.target.result, source.size); };
        reader.readAsDataURL(source);
      }
    });
  };
})();
