// Cookie-based API client (httpOnly JWT is sent automatically by the browser)
const api = {
  async request(method, url, body = null) {
    const opts = { method, credentials: 'same-origin' };
    if (body instanceof FormData) {
      opts.body = body;
    } else if (body !== null) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
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
