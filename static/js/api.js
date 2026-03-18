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
    const r = await fetch(url, opts);
    if (r.status === 401) { window.location = '/admin/login'; return {}; }
    return r.json().catch(() => ({}));
  },
  get(url)        { return this.request('GET',    url); },
  post(url, body) { return this.request('POST',   url, body); },
  put(url, body)  { return this.request('PUT',    url, body); },
  patch(url, body){ return this.request('PATCH',  url, body); },
  del(url)        { return this.request('DELETE', url); },
};
