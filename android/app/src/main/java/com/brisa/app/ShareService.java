package com.brisa.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.content.pm.ServiceInfo;

public final class ShareService extends Service {
    public static final String STOP = "com.brisa.app.STOP";
    private PowerManager.WakeLock wakeLock;

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26) manager.createNotificationChannel(new NotificationChannel("sharing", "Compartir archivos", NotificationManager.IMPORTANCE_LOW));
    }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && STOP.equals(intent.getAction())) { stopSelf(); return START_NOT_STICKY; }
        PendingIntent open = PendingIntent.getActivity(this, 1, new Intent(this, MainActivity.class), PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop = PendingIntent.getService(this, 2, new Intent(this, ShareService.class).setAction(STOP), PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, "sharing") : new Notification.Builder(this);
        Notification notification = builder.setSmallIcon(R.drawable.ic_launcher).setContentTitle("Brisa está compartiendo")
            .setContentText("Tus archivos están disponibles en tu red local.")
            .setContentIntent(open).setOngoing(true).addAction(new Notification.Action.Builder(null, "Detener", stop).build()).build();
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(41, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
            else startForeground(41, notification);
            if (wakeLock == null) {
                wakeLock = ((PowerManager) getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "brisa:sharing");
                wakeLock.acquire(6 * 60 * 60 * 1000L);
            }
            BrisaRuntime.sharing(true);
        } catch (Exception error) {
            stopSelf();
        }
        return START_NOT_STICKY;
    }
    @Override public void onTimeout(int startId, int foregroundServiceType) { stopSelf(); }
    @Override public void onDestroy() {
        try { BrisaRuntime.sharing(false); } catch (Exception ignored) { }
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        stopForeground(true);
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
