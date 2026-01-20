const CACHE_NAME = 'rba-cache-v2';
const assets = [
    '/',
    '/offline/',
    '/static/css/bootstrap.min.css',
    '/static/css/all.min.css',
    '/static/css/style.css',
    '/static/js/bootstrap.bundle.min.js',
    '/static/js/connection_check.js',
    '/static/js/db_manager.js',
    'https://unpkg.com/dexie/dist/dexie.js' // On cache aussi la bibliothèque
];

// 1. Installation : On met en cache les fichiers de base
self.addEventListener('install', evt => {
    evt.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('Mise en cache des fichiers statiques');
            return cache.addAll(assets);
        })
    );
});

// 2. Activation : On nettoie les vieux caches si on change de version
self.addEventListener('activate', evt => {
    evt.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(keys
                .filter(key => key !== CACHE_NAME)
                .map(key => caches.delete(key))
            );
        })
    );
});

// 3. Stratégie réseau : Réseau d'abord, sinon Cache, sinon page Offline
self.addEventListener('fetch', evt => {
    evt.respondWith(
        fetch(evt.request).catch(() => {
            return caches.match(evt.request).then(response => {
                // Si on a la page en cache, on la donne, sinon page offline
                return response || caches.match('/offline/');
            });
        })
    );
});