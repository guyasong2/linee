const CACHE_NAME = "linee-v5";
const OFFLINE_EN = "/en/offline/";
const OFFLINE_FR = "/fr/offline/";
const CORE_ASSETS = [
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/js/vendor/htmx.min.js",
  "/static/fonts/poppins-400.woff2",
  "/static/fonts/poppins-500.woff2",
  "/static/fonts/poppins-600.woff2",
  "/static/fonts/poppins-700.woff2",
  "/static/img/linee-logo.png",
  "/static/img/icon.svg",
  "/static/img/icon-192.png",
  "/static/manifest.webmanifest",
  "/en/",
  "/fr/",
  OFFLINE_EN,
  OFFLINE_FR,
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.allSettled(CORE_ASSETS.map((asset) => cache.add(asset))),
    ),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) {
          return cached;
        }
        return fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        });
      }),
    );
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => {
        const fallback = url.pathname.startsWith("/fr/") ? OFFLINE_FR : OFFLINE_EN;
        return caches.match(request).then((cached) => cached || caches.match(fallback));
      }),
    );
  }
});
