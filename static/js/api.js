// Cookie-based API client (httpOnly JWT is sent automatically by the browser)
function getCookie(name) {
  return document.cookie
    .split(';')
    .map(part => part.trim())
    .find(part => part.startsWith(name + '='))
    ?.split('=')
    .slice(1)
    .join('=') || '';
}

function getCsrfToken() {
  return decodeURIComponent(getCookie('csrf_token') || '');
}

const api = {
  async request(method, url, body = null) {
    const opts = { method, credentials: 'same-origin' };
    const unsafe = !['GET', 'HEAD', 'OPTIONS'].includes(String(method).toUpperCase());
    const csrfToken = unsafe ? getCsrfToken() : '';
    if (body instanceof FormData) {
      opts.body = body;
      if (csrfToken) opts.headers = { 'X-CSRF-Token': csrfToken };
    } else if (body !== null) {
      opts.headers = { 'Content-Type': 'application/json' };
      if (csrfToken) opts.headers['X-CSRF-Token'] = csrfToken;
      opts.body = JSON.stringify(body);
    } else if (csrfToken) {
      opts.headers = { 'X-CSRF-Token': csrfToken };
    }
    let r;
    try {
      r = await fetch(url, opts);
    } catch (e) {
      const msg = 'Нет связи с сервером';
      document.body.dispatchEvent(new CustomEvent('showToast', {
        detail: { message: msg, type: 'error' }
      }));
      return { error: msg, _failed: true };
    }
    if (r.status === 401) { window.location = '/admin/login'; return {}; }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const msg = data.message || data.error || 'Ошибка сервера';
      document.body.dispatchEvent(new CustomEvent('showToast', {
        detail: { message: msg, type: 'error' }
      }));
      return { error: msg, _status: r.status, _failed: true };
    }
    return data;
  },
  get(url)        { return this.request('GET',    url); },
  post(url, body) { return this.request('POST',   url, body); },
  put(url, body)  { return this.request('PUT',    url, body); },
  patch(url, body){ return this.request('PATCH',  url, body); },
  del(url, body)  { return this.request('DELETE', url, body); },
};
