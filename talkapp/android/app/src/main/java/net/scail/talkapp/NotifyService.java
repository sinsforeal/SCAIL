package net.scail.talkapp;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/** A foreground service holding one WebSocket to the hub over Tailscale.
 *  When she sends, the hub broadcasts on this socket and the notification is
 *  posted locally -- no Mozilla, no FCM, no push service. This is the
 *  ntfy/Conversations model: the delay web push had (6 minutes through
 *  autopush) becomes the socket's round trip. */
public class NotifyService extends Service {
    private static final String CH_MSG = "messages";
    private static final String CH_SVC = "service";
    private static final int SVC_ID = 1;

    private OkHttpClient http;
    private WebSocket ws;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private int backoffSeconds = 2;
    private boolean started = false;
    private final Map<String, String> names = new HashMap<>();
    // One reply is one to three bubbles and each arrives as its own socket
    // event. Posting per event pinged the phone three times for one thing to
    // say. Inside burstMs of the last alert from the same character the
    // notification is REBUILT with every line of the burst in it and
    // setOnlyAlertOnce, so the tray updates in silence. The window comes from
    // the hub (talkapp.notify_burst_seconds) so it is not baked into the APK.
    private int burstMs = 45000;
    private final Map<String, Long> lastAlert = new HashMap<>();
    private final Map<String, ArrayList<String>> burstLines = new HashMap<>();

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(
                CH_SVC, "Connection", NotificationManager.IMPORTANCE_MIN));
        NotificationChannel msg = new NotificationChannel(
                CH_MSG, "Messages", NotificationManager.IMPORTANCE_HIGH);
        msg.enableVibration(true);
        nm.createNotificationChannel(msg);
        // protocol-level pings keep the socket honest through Doze; a missed
        // pong surfaces as onFailure and the backoff reconnects
        http = new OkHttpClient.Builder()
                .pingInterval(25, TimeUnit.SECONDS)
                .build();
    }

    @Override public int onStartCommand(Intent i, int flags, int startId) {
        Notification n = svcNotification("connected to the hub");
        if (Build.VERSION.SDK_INT >= 34)
            startForeground(SVC_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        else
            startForeground(SVC_ID, n);
        if (!started) {
            started = true;
            fetchNames();
            connect();
        }
        return START_STICKY;
    }

    private Notification svcNotification(String text) {
        return new Notification.Builder(this, CH_SVC)
                .setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle("TALKAPP")
                .setContentText(text)
                .setContentIntent(openApp())
                .setOngoing(true)
                .build();
    }

    private PendingIntent openApp() {
        return PendingIntent.getActivity(this, 0,
                new Intent(this, MainActivity.class)
                        .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private void fetchNames() {
        Request r = new Request.Builder()
                .url(BuildConfig.BASE_URL + "/chars?key=" + BuildConfig.TOKEN).build();
        http.newCall(r).enqueue(new Callback() {
            @Override public void onFailure(Call c, IOException e) {}
            @Override public void onResponse(Call c, Response resp) throws IOException {
                try (Response rr = resp) {
                    JSONObject payload = new JSONObject(rr.body().string());
                    burstMs = payload.optInt("notify_burst_seconds", 45) * 1000;
                    JSONArray chars = payload.getJSONArray("chars");
                    for (int i = 0; i < chars.length(); i++) {
                        JSONObject ch = chars.getJSONObject(i);
                        names.put(ch.getString("id"), ch.getString("name"));
                    }
                } catch (Exception ignored) {}
            }
        });
    }

    private void connect() {
        Request r = new Request.Builder()
                .url(BuildConfig.BASE_URL.replaceFirst("^http", "ws")
                        + "/ws?key=" + BuildConfig.TOKEN).build();
        ws = http.newWebSocket(r, new WebSocketListener() {
            @Override public void onOpen(WebSocket w, Response resp) {
                backoffSeconds = 2;
                // no re-post on an ordinary reconnect: the user swiped the
                // "connected" notification away and every Doze cycle was
                // bringing it back. Only a real outage is worth a line.
                if (outageShown) {
                    outageShown = false;
                    update(svcNotification("connected to the hub"));
                }
            }
            @Override public void onMessage(WebSocket w, String text) {
                handleEvent(text);
            }
            @Override public void onFailure(WebSocket w, Throwable t, Response resp) {
                scheduleReconnect();
            }
            @Override public void onClosed(WebSocket w, int code, String reason) {
                scheduleReconnect();
            }
        });
    }

    private boolean outageShown = false;

    private void scheduleReconnect() {
        // say something only once the backoff says this is not a blip
        if (!outageShown && backoffSeconds >= 32) {
            outageShown = true;
            update(svcNotification("reconnecting..."));
        }
        handler.removeCallbacksAndMessages(null);
        handler.postDelayed(this::connect, backoffSeconds * 1000L);
        backoffSeconds = Math.min(backoffSeconds * 2, 60);
    }

    private void handleEvent(String text) {
        try {
            JSONObject ev = new JSONObject(text);
            if ("notify_test".equals(ev.optString("type"))) {
                Notification n = new Notification.Builder(this, CH_MSG)
                        .setSmallIcon(android.R.drawable.stat_notify_chat)
                        .setContentTitle("TALKAPP")
                        .setContentText("test - this arrived over the socket, not web push")
                        .setContentIntent(openApp())
                        .setAutoCancel(true)
                        .build();
                getSystemService(NotificationManager.class).notify(999, n);
                return;
            }
            if (!"message".equals(ev.optString("type"))) return;
            JSONObject m = ev.getJSONObject("msg");
            if (!"her".equals(m.optString("role"))) return;   // his own sends echo back
            String cid = ev.optString("char", "");
            if (MainActivity.visible) {
                // he is already looking, so no notification -- and the burst
                // ends here, or the next thing she says after he closes the
                // app would be folded into it and arrive without a sound
                lastAlert.remove(cid);
                burstLines.remove(cid);
                return;
            }
            String who = names.containsKey(cid) ? names.get(cid) : cid;
            String body = "voice".equals(m.optString("kind"))
                    ? "🎤 voice note" : m.optString("text", "");
            // is this a new thing to say, or the next bubble of one?
            long now = System.currentTimeMillis();
            Long last = lastAlert.get(cid);
            boolean sameBurst = last != null && (now - last) < burstMs;
            ArrayList<String> lines = burstLines.get(cid);
            if (!sameBurst || lines == null) {
                lines = new ArrayList<>();
                burstLines.put(cid, lines);
                lastAlert.put(cid, now);      // the burst is timed from its FIRST bubble
            }
            lines.add(body);
            while (lines.size() > 6) lines.remove(0);

            Notification.Builder b = new Notification.Builder(this, CH_MSG)
                    .setSmallIcon(android.R.drawable.stat_notify_chat)
                    .setContentTitle(who)
                    .setContentIntent(openApp())
                    .setAutoCancel(true)
                    // the ping belongs to the burst, not to each bubble in it
                    .setOnlyAlertOnce(sameBurst);
            if (lines.size() > 1) {
                Notification.InboxStyle style = new Notification.InboxStyle();
                for (String l : lines) style.addLine(l.length() > 120 ? l.substring(0, 120) : l);
                style.setSummaryText(lines.size() + " messages");
                b.setStyle(style).setContentText(lines.get(lines.size() - 1));
            } else {
                b.setContentText(body.length() > 120 ? body.substring(0, 120) : body);
            }
            // one notification slot per character, ids clear of SVC_ID
            getSystemService(NotificationManager.class)
                    .notify(1000 + Math.abs(cid.hashCode() % 1000), b.build());
        } catch (Exception ignored) {}
    }

    private void update(Notification n) {
        getSystemService(NotificationManager.class).notify(SVC_ID, n);
    }

    static void clearMessageNotifications(Context ctx) {
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        for (int id = 1000; id < 2000; id++) nm.cancel(id);
    }

    @Override public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (ws != null) ws.close(1000, "service stopped");
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent i) { return null; }
}
