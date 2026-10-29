/* TALKAPP service worker: push notifications + PWA installability. */
self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(clients.claim()));

self.addEventListener("push", e => {
  let d = {};
  try { d = e.data.json(); } catch (err) {}
  e.waitUntil(self.registration.showNotification(d.title || "TALKAPP", {
    body: d.body || "",
    icon: "/app/icon192.png",
    badge: "/app/icon192.png",
    // per-character tag + renotify: one shared tag silently REPLACED the
    // previous notification -- no ping, no vibration -- so the second
    // message of a burst looked like it was never delivered
    tag: "talkapp-" + (d.char || ""),
    renotify: true,
  }));
});

self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(clients.matchAll({type: "window", includeUncontrolled: true}).then(list => {
    for (const c of list) if ("focus" in c) return c.focus();
    return clients.openWindow("/");
  }));
});
