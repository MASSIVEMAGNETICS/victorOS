package ai.ethica.victoros;

import android.app.AppOpsManager;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.os.Build;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/** Android-supported app-context scanner: active/recent usage plus launchable-app inventory. */
public final class VictorAppContextSensor {
    private VictorAppContextSensor(){}

    public static boolean hasUsageAccess(Context c){
        AppOpsManager ops=(AppOpsManager)c.getSystemService(Context.APP_OPS_SERVICE);
        int mode=ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS,android.os.Process.myUid(),c.getPackageName());
        return mode==AppOpsManager.MODE_ALLOWED;
    }

    public static String recentForegroundPackage(Context c){
        if(!hasUsageAccess(c))return "USAGE_ACCESS_REQUIRED";
        UsageStatsManager u=(UsageStatsManager)c.getSystemService(Context.USAGE_STATS_SERVICE);
        long end=System.currentTimeMillis(),start=end-10*60*1000L;UsageEvents events=u.queryEvents(start,end);if(events==null)return "unknown";
        UsageEvents.Event e=new UsageEvents.Event();String latest="unknown";long latestTime=0;
        while(events.hasNextEvent()){events.getNextEvent(e);int type=e.getEventType();boolean foreground=type==UsageEvents.Event.MOVE_TO_FOREGROUND;
            if(Build.VERSION.SDK_INT>=29)foreground=foreground||type==UsageEvents.Event.ACTIVITY_RESUMED;
            if(foreground&&e.getTimeStamp()>=latestTime){latestTime=e.getTimeStamp();latest=e.getPackageName();}}
        return latest;
    }

    public static List<String> launchableApps(Context c){
        PackageManager pm=c.getPackageManager();Intent q=new Intent(Intent.ACTION_MAIN);q.addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> infos=pm.queryIntentActivities(q,PackageManager.MATCH_ALL);List<String> out=new ArrayList<>();
        for(ResolveInfo r:infos){String label=String.valueOf(r.loadLabel(pm));String pkg=r.activityInfo==null?"?":r.activityInfo.packageName;out.add(label+" · "+pkg);}Collections.sort(out,Comparator.naturalOrder());return out;
    }

    public static String snapshot(Context c){
        List<String> apps=launchableApps(c);StringBuilder s=new StringBuilder();s.append("usageAccess=").append(hasUsageAccess(c)).append("\nrecentForeground=").append(recentForegroundPackage(c)).append("\nlaunchableApps=").append(apps.size());
        for(int i=0;i<Math.min(24,apps.size());i++)s.append("\n").append(apps.get(i));
        String snapshot=s.toString();GodsEyeWorldModel.publishText(c.getApplicationContext(),"APP_CONTEXT",snapshot,"app context foreground="+recentForegroundPackage(c)+" launchable="+apps.size());return snapshot;
    }
}
