// ATUALIZADO: Mudei para v4.0 para forçar o celular a recriar o cache
const CACHE_NAME = 'esfas-app-v4.0';

const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/img/brasao.png',
  '/offline.html'
];

// Instalação do Service Worker
self.addEventListener('install', event => {
  // NOVO: Força este Service Worker a assumir o controle IMEDIATAMENTE
  // Isso impede que o navegador fique "preso" na versão antiga
  self.skipWaiting();

  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
});

// Estratégia: Network First (Rede Primeiro)
// Tenta pegar da rede (garante atualização). Se falhar (sem net), pega do cache.
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .catch(() => {
        return caches.match(event.request);
      })
  );
});

// Ativação e limpeza de caches antigos
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            // Apaga qualquer cache que não seja a v4.0
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});