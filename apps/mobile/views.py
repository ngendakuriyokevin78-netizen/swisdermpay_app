"""Vues Interface Téléphone PWA (ajout seul, HTML léger pour mobile)."""
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.generic import TemplateView


class MobileAppView(TemplateView):
    template_name = 'mobile/app.html'


class MerchantQRView(TemplateView):
    """Page vendeur : affiche gros QR à faire scanner."""
    template_name = 'mobile/merchant_qr.html'


class ManifestView(View):
    """Manifest PWA à URL fixe /m/manifest.webmanifest (évite hash static)."""

    def get(self, request):
        data = {
            "name": "Swisderm Pay — Cash Tel",
            "short_name": "Swisderm Pay",
            "description": "Mobile Money Burundi : transferts, QR, retraits. Lumitel recommandé.",
            "start_url": "/m/",
            "scope": "/m/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#0b1023",
            "theme_color": "#0b1023",
            "lang": "fr",
            "icons": [
                {"src": "/m/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/m/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            ],
        }
        resp = JsonResponse(data)
        resp['Cache-Control'] = 'no-store'
        return resp


class ServiceWorkerView(View):
    """Service Worker à URL fixe /m/sw.js (scope /m/)."""

    def get(self, request):
        js = (
            "var CACHE='cashtel-v33';var CORE=['/m/'];"
            "self.addEventListener('install',function(e){e.waitUntil(caches.open(CACHE).then(function(c){return c.addAll(CORE);}).then(function(){return self.skipWaiting();}));});"
            "self.addEventListener('activate',function(e){e.waitUntil(caches.keys().then(function(ks){return Promise.all(ks.map(function(k){if(k!==CACHE){return caches.delete(k);} }));}).then(function(){return self.clients.claim();}));});"
            "self.addEventListener('fetch',function(e){var u=e.request.url;if(u.indexOf('/api/')!==-1||u.indexOf('/admin/')!==-1){return;}e.respondWith(fetch(e.request).then(function(r){try{var c=r.clone();caches.open(CACHE).then(function(cache){cache.put(e.request,c);});}catch(_){}return r;}).catch(function(){return caches.match(e.request).then(function(h){return h||caches.match('/m/');});}));});"
        )
        resp = HttpResponse(js, content_type='application/javascript')
        resp['Cache-Control'] = 'no-store'
        return resp


class AppIconView(View):
    """Icône PWA à URL fixe (évite hash static)."""

    def get(self, request, size=192):
        from django.contrib.staticfiles import finders
        from django.http import FileResponse
        import os
        size = 512 if str(size) == '512' else 192
        path = finders.find(f'mobile/icons/icon-{size}.png')
        if path and os.path.exists(path):
            return FileResponse(open(path, 'rb'), content_type='image/png')
        return HttpResponse(status=404)
