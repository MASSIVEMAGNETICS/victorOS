package ai.ethica.victoros;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import java.util.List;

/** Opt-in semantic view of the active Android UI. No gesture actuator in v0.2. */
public final class VictorAccessibilityService extends AccessibilityService {
    private long lastPublishMs;

    @Override public void onAccessibilityEvent(AccessibilityEvent event){
        if(event==null)return;
        VictorStore store=new VictorStore(getApplicationContext());
        if(store.load().humanStop || !store.verifyIntegrity())return;
        long now=System.currentTimeMillis();if(now-lastPublishMs<250)return;lastPublishMs=now;
        String pkg=event.getPackageName()==null?"unknown":event.getPackageName().toString();
        String cls=event.getClassName()==null?"unknown":event.getClassName().toString();
        StringBuilder payload=new StringBuilder();payload.append("package=").append(pkg).append("\nclass=").append(cls).append("\nevent=").append(event.getEventType()).append('\n');
        AccessibilityNodeInfo source=event.getSource();
        boolean passwordSource=source!=null&&source.isPassword();
        List<CharSequence> eventText=event.getText();
        if(passwordSource)payload.append("eventText=[REDACTED_PASSWORD]\n");
        else if(eventText!=null&&!eventText.isEmpty())payload.append("eventText=").append(eventText).append('\n');
        AccessibilityNodeInfo root=getRootInActiveWindow();if(root!=null){int[] count={0};walk(root,payload,0,count);}
        String raw=payload.length()>12000?payload.substring(0,12000):payload.toString();
        GodsEyeWorldModel.publishText(getApplicationContext(),"ACTIVE_UI",raw,"active UI "+pkg+" / "+cls);
    }

    private void walk(AccessibilityNodeInfo node,StringBuilder out,int depth,int[] count){
        if(node==null||depth>5||count[0]>=90||out.length()>11000)return;count[0]++;
        out.append(depth).append(':').append(node.getClassName()==null?"?":node.getClassName());
        if(node.isPassword())out.append(" text=[REDACTED_PASSWORD]");
        else {CharSequence t=node.getText();CharSequence d=node.getContentDescription();if(t!=null&&t.length()>0)out.append(" text=").append(t);if(d!=null&&d.length()>0)out.append(" desc=").append(d);}
        String id=node.getViewIdResourceName();if(id!=null)out.append(" id=").append(id);out.append('\n');
        for(int i=0;i<node.getChildCount();i++){AccessibilityNodeInfo child=node.getChild(i);if(child!=null)walk(child,out,depth+1,count);}
    }

    @Override public void onInterrupt(){
        VictorStore store=new VictorStore(getApplicationContext());
        if(!store.load().humanStop&&store.verifyIntegrity())GodsEyeWorldModel.publishText(getApplicationContext(),"ACTIVE_UI","accessibility interrupted","active UI sensor interrupted");
    }
}
