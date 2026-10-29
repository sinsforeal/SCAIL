package net.scail.talkapp;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

/** The whole UI is the hub's own web client in a WebView; this app exists
 *  for the notification service beside it, which replaces web push. */
public class MainActivity extends Activity {
    // the service reads this to skip notifying while he is looking at the app
    static volatile boolean visible = false;
    private WebView web;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                        != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(
                    new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 1);
        }
        startForegroundService(new Intent(this, NotifyService.class));

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // the client keeps its key here
        s.setMediaPlaybackRequiresUserGesture(true);
        // Everything on the hub's own host stays in here; anything else is
        // somebody else's page and belongs in his browser. A plain
        // WebViewClient loads every link in place, so tapping a scenery
        // thumbnail opened x.com inside the app with no address bar and no
        // way back but the back key.
        final String own = Uri.parse(BuildConfig.BASE_URL).getHost();
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                String host = u.getHost();
                if (host == null || own == null || host.equalsIgnoreCase(own)) return false;
                try {
                    Intent i = new Intent(Intent.ACTION_VIEW, u);
                    i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(i);
                    return true;
                } catch (Exception e) {
                    return false;   // no browser for it: let the WebView try
                }
            }
        });
        // the page asks this for the installed version and compares it with
        // the hub's /ver, so "update app" appears in its own menu
        web.addJavascriptInterface(new Native(), "talkappNative");
        // a WebView does not download anything itself
        web.setDownloadListener((url, ua, cd, mime, len) -> save(url, mime));
        // ?key= once; the page stores it and strips it from the URL itself
        web.loadUrl(BuildConfig.BASE_URL + "/?key=" + BuildConfig.TOKEN);
        setContentView(web);
    }

    /** A file the page asked to save. One of the hub's own media files -- a
     *  voice note he wants to keep -- goes to the system download manager and
     *  lands in the phone's public Downloads directory under the name the
     *  page put in the link (the character and the minute she said it), so he
     *  can find it in any file manager. Everything else, the APK link
     *  included, still goes to the system browser, which downloads it and
     *  offers the install. */
    private void save(String url, String mime) {
        Uri u = Uri.parse(url);
        String own = Uri.parse(BuildConfig.BASE_URL).getHost();
        String host = u.getHost(), path = u.getPath() == null ? "" : u.getPath();
        if (host == null || own == null || !host.equalsIgnoreCase(own)
                || !path.startsWith("/media/")) {
            try {
                Intent i = new Intent(Intent.ACTION_VIEW, u);
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(i);
            } catch (Exception e) {
                Toast.makeText(this, "nothing on this phone opens that", Toast.LENGTH_SHORT).show();
            }
            return;
        }
        String name = u.getQueryParameter("dl");
        if (name == null || name.isEmpty()) name = u.getLastPathSegment();
        if (name == null || name.isEmpty()) name = "talkapp.ogg";
        name = name.replaceAll("[^A-Za-z0-9._-]", "_");
        try {
            DownloadManager.Request r = new DownloadManager.Request(u);
            if (mime != null && !mime.isEmpty()) r.setMimeType(mime);
            r.setTitle(name);
            r.setDescription("TALKAPP");
            r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
            getSystemService(DownloadManager.class).enqueue(r);
            Toast.makeText(this, "saving to Downloads/" + name, Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            Toast.makeText(this, "could not save it: " + e, Toast.LENGTH_LONG).show();
        }
    }

    @Override protected void onResume() {
        super.onResume();
        visible = true;
        NotifyService.clearMessageNotifications(this);
    }

    @Override protected void onPause() {
        super.onPause();
        visible = false;
    }

    public static class Native {
        @JavascriptInterface public int version() { return BuildConfig.VERSION_CODE; }
        @JavascriptInterface public String versionName() { return BuildConfig.VERSION_NAME; }
    }

    @Override public void onBackPressed() {
        // the page manages its own history (root sentinel included); walk it
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
