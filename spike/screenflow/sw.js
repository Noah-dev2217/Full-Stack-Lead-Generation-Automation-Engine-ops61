self.addEventListener('install', (event) => {
    // Force the waiting service worker to become the active service worker.
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    // Tell the active service worker to take control of the page immediately.
    event.waitUntil(clients.claim());
});

self.addEventListener('notificationclick', function(event) {
    // Close the notification
    event.notification.close();

    // Focus the ScreenFlow window/tab if it's open
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if ('focus' in client) {
                    return client.focus();
                }
            }
            // If we couldn't find a window to focus, open a new one
            if (clients.openWindow) {
                return clients.openWindow('/');
            }
        })
    );
});
