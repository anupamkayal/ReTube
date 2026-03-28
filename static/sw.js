const CACHE_NAME = 'vanced-cache-v1';

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = event.request.url;
  const dest = event.request.destination;

  // Never intercept media, video, audio, or blob URLs.
  // Intercepting stream URLs causes DRM / CORS errors on some CDNs.
  if (
    dest === 'video' ||
    dest === 'audio' ||
    url.startsWith('blob:') ||
    url.includes('googlevideo.com') ||
    url.includes('youtube.com/videoplayback') ||
    url.includes('/stream') ||
    url.includes('/api/stream')
  ) {
    return; // Let the browser handle it natively
  }

  // For all other requests, use network-first
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
