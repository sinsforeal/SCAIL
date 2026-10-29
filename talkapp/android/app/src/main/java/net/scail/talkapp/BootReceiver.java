package net.scail.talkapp;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context ctx, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
        try {
            ctx.startForegroundService(new Intent(ctx, NotifyService.class));
        } catch (Exception e) {
            // newer Androids restrict dataSync services from boot; the
            // service then starts on his first open of the app instead
        }
    }
}
