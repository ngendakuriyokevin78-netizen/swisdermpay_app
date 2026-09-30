/* Service Worker Cash Tel — cache léger, n'interfère pas avec l'API. */
var CACHE = 'cashtel-v16';
var CORE = ['/m/'];
self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(CORE); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) { return Promise.all(ks.map(function (k) { if (k !== CACHE) { return caches.delete(k); } })); }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  var url = e.request.url;
  // Ne jamais cacher l'API ni l'admin
  if (url.indexOf('/api/') !== -1 || url.indexOf('/admin/') !== -1) { return; }
  // Réseau d'abord (page toujours fraîche), cache en secours hors-ligne
  e.respondWith(
    fetch(e.request).then(function (r) {
      try { var c = r.clone(); caches.open(CACHE).then(function (cache) { cache.put(e.request, c); }); } catch (_) {}
      return r;
    }).catch(function () {
      return caches.match(e.request).then(function (hit) { return hit || caches.match('/m/'); });
    })
  );
});
