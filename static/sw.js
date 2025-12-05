// ATUALIZADO: v6.0 para forçar o celular a baixar o novo ícone
const CACHE_NAME = 'esfas-app-v6.0';

const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/manifest.json',
  '/static/img/brasaoappcel.png', // <--- NOVO ÍCONE AQUI
  '/static/img/brasao.png',       // Mantive o brasão normal caso seja usado dentro do site
  '/offline.html'
];

self.addEventListener('install', event => {
  self.skipWaiting(); // Força o novo Service Worker a assumir imediatamente
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .catch(() => {
        return caches.match(event.request);
      })
  );
});

self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});