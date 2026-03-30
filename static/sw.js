// This is a basic Service Worker. 
// Its only job right now is to satisfy Chrome/Safari's requirement 
// so they show the "Add to Home Screen" install prompt!

self.addEventListener('install', (event) => {
    console.log('EEP Portal Service Worker Installed');
});

self.addEventListener('fetch', (event) => {
    // For now, we just pass all requests through normally.
    // Later (Phase 13), we can add offline caching here!
    event.respondWith(fetch(event.request));
});