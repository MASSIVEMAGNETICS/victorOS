package ai.ethica.victoros;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.os.Build;

final class VictorForegroundNotifications {
    static final String CHANNEL="victor_senses";
    private VictorForegroundNotifications(){}

    static void ensure(Context c){
        if(Build.VERSION.SDK_INT>=26){
            NotificationManager n=(NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE);
            NotificationChannel ch=new NotificationChannel(CHANNEL,"Victor sensory organs",NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("Visible notification while Victor is using screen, camera, or microphone sensors.");
            n.createNotificationChannel(ch);
        }
    }

    static Notification notification(Context c,String title,String text){
        ensure(c);
        Notification.Builder b=Build.VERSION.SDK_INT>=26?new Notification.Builder(c,CHANNEL):new Notification.Builder(c);
        return b.setContentTitle(title).setContentText(text).setSmallIcon(android.R.drawable.ic_menu_view).setOngoing(true).build();
    }

    static void start(Service s,int id,String title,String text,int type){
        Notification n=notification(s,title,text);
        if(Build.VERSION.SDK_INT>=29)s.startForeground(id,n,type); else s.startForeground(id,n);
    }
}
