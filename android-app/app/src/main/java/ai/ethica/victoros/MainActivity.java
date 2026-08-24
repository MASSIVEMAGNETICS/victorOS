package ai.ethica.victoros;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.time.Instant;
import java.util.List;

public final class MainActivity extends Activity {
    private static final int BG = Color.rgb(5, 6, 7), PANEL = Color.rgb(18, 21, 24);
    private static final int GREEN = Color.rgb(168, 255, 53), PURPLE = Color.rgb(183, 92, 255), WHITE = Color.rgb(238, 242, 244);
    private VictorStore store;
    private LinearLayout root;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        store = new VictorStore(this);
        showHome();
    }

    private void frame(String title, boolean back) {
        ScrollView scroll = new ScrollView(this); scroll.setBackgroundColor(BG);
        root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setPadding(dp(18), dp(18), dp(18), dp(36));
        scroll.addView(root); setContentView(scroll);
        if (back) addButton("‹ VICTOROS", v -> showHome(), PURPLE);
        TextView brand = text(title, 28, GREEN); brand.setTypeface(Typeface.DEFAULT_BOLD); root.addView(brand);
        root.addView(text("PERSISTENT EXPERIENCE INTELLIGENCE", 11, Color.GRAY));
        spacer(16);
    }

    private void showHome() {
        frame("VICTOR//OS", false);
        addPanel("SYSTEM ALIVE", "Born " + store.born() + "\nReceipts " + store.events().length() + "  •  Chain " + (store.verify().isEmpty() ? "VERIFIED" : "BROKEN"), GREEN);
        LinearLayout row = null;
        String[][] organs = {
                {"◉ CORTEX", "Intent and cognition"}, {"▣ MEMORY VAULT", "Persistent experience"},
                {"⌁ CHRONOS", "Verified causal history"}, {"◇ ETHICA", "Authority and policy"},
                {"♥ HOMEOSTASIS", "Internal operating state"}, {">_ COMMAND", "Bounded execution"}
        };
        for (int i=0;i<organs.length;i++) {
            if (i%2==0) { row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); root.addView(row, matchWrap()); }
            final int index=i;
            Button b = button(organs[i][0] + "\n" + organs[i][1], v -> openOrgan(index), PANEL);
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(112), 1); p.setMargins(dp(4),dp(4),dp(4),dp(4)); row.addView(b,p);
        }
    }

    private void openOrgan(int index) {
        switch(index) {
            case 0: cortex(); break; case 1: memory(); break; case 2: chronos(); break;
            case 3: ethica(); break; case 4: homeostasis(); break; default: command();
        }
    }

    private void cortex() {
        frame("CORTEX", true); addPanel("LOCAL COGNITION BUS", "Capture an intent. Victor records it as experience; execution still requires an explicit bounded command.", PURPLE);
        EditText input = input("What matters right now?"); root.addView(input, matchWrap());
        addButton("COMMIT INTENT", v -> { String s=input.getText().toString().trim(); if(s.isEmpty()) return; store.append("CORTEX", s, "OBSERVED"); input.setText(""); toastDialog("Intent committed", "Stored locally with a chained Chronos receipt."); }, GREEN);
    }

    private void memory() {
        frame("MEMORY VAULT", true); JSONArray events=store.events();
        addPanel("EPISODIC MEMORY", events.length()+" durable experiences on this device", PURPLE);
        for(int i=events.length()-1;i>=Math.max(0,events.length()-30);i--) try { JSONObject e=events.getJSONObject(i); addPanel(e.optString("organ")+" · "+e.optString("state"), e.optString("message")+"\n"+e.optString("timestamp"), WHITE); } catch(Exception ignored) {}
    }

    private void chronos() {
        frame("CHRONOS LEDGER", true); List<String> faults=store.verify();
        addPanel(faults.isEmpty()?"CHAIN VERIFIED":"CHAIN FAILURE", faults.isEmpty()?"Every local receipt links cryptographically to the prior receipt.":faults.toString(), faults.isEmpty()?GREEN:Color.RED);
        JSONArray events=store.events(); for(int i=events.length()-1;i>=Math.max(0,events.length()-20);i--) try { JSONObject e=events.getJSONObject(i); addPanel("#"+e.optInt("id")+" "+e.optString("organ"), e.optString("hash").substring(0,16)+"…\n"+e.optString("message"), PURPLE); } catch(Exception ignored) {}
    }

    private void ethica() {
        frame("ETHICA GOVERNOR", true);
        addPanel("ACTIVE CONSTITUTION", "1. Local-first and owner-controlled\n2. Explicit authority before execution\n3. Evidence before claims\n4. Every mutation emits a receipt\n5. Fail closed when authority is unclear", GREEN);
        addPanel("NETWORK AUTHORITY", "DENIED BY DEFAULT\nVictorOS v0.1 requests no internet permission.", PURPLE);
    }

    private void homeostasis() {
        frame("HOMEOSTASIS", true); metric("ENERGY", "energy"); metric("INTEGRITY", "integrity"); metric("FOCUS", "focus");
        addButton("RUN SELF-CHECK", v -> { List<String> faults=store.verify(); store.setMetric("integrity", faults.isEmpty()?100:25); store.append("HOMEOSTASIS", faults.isEmpty()?"Self-check passed":"Self-check failed", faults.isEmpty()?"VERIFIED":"FAULT"); homeostasis(); }, GREEN);
    }

    private void metric(String label,String key) { int value=store.getMetric(key,50); addPanel(label+"  "+value+"%", progress(value), value>40?GREEN:Color.RED); }
    private String progress(int value) { int blocks=value/10; return "██████████".substring(0,blocks)+"░░░░░░░░░░".substring(0,10-blocks); }

    private void command() {
        frame("COMMAND CENTER", true); addPanel("BOUNDED EXECUTION", "Commands mutate only VictorOS local state. No shell, file, microphone, location, or network authority exists in this build.", PURPLE);
        EditText input=input("remember <text> | focus <0-100> | status | verify"); root.addView(input,matchWrap());
        addButton("AUTHORIZE + EXECUTE", v -> execute(input.getText().toString().trim()), GREEN);
    }

    private void execute(String cmd) {
        String result; String state="COMPLETED";
        if(cmd.startsWith("remember ") && cmd.length()>9) result="Remembered: "+cmd.substring(9);
        else if(cmd.startsWith("focus ")) { try { int n=Integer.parseInt(cmd.substring(6).trim()); if(n<0||n>100) throw new Exception(); store.setMetric("focus",n); result="Focus set to "+n; } catch(Exception e){ result="Rejected: focus must be 0–100"; state="BLOCKED_POLICY"; } }
        else if(cmd.equals("status")) result="Energy "+store.getMetric("energy",0)+" · Integrity "+store.getMetric("integrity",0)+" · Focus "+store.getMetric("focus",0);
        else if(cmd.equals("verify")) result=store.verify().isEmpty()?"Chronos chain verified":"Chronos chain failed";
        else { result="Rejected: command is outside the current capability lease"; state="BLOCKED_AUTHORITY"; }
        store.append("COMMAND", cmd.isEmpty()?"<empty>":cmd+" → "+result, state); toastDialog(state,result);
    }

    private EditText input(String hint) { EditText e=new EditText(this); e.setHint(hint); e.setHintTextColor(Color.GRAY); e.setTextColor(WHITE); e.setBackgroundColor(PANEL); e.setPadding(dp(14),dp(14),dp(14),dp(14)); e.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE); return e; }
    private void addPanel(String heading,String body,int accent) { LinearLayout p=new LinearLayout(this); p.setOrientation(LinearLayout.VERTICAL); p.setPadding(dp(14),dp(14),dp(14),dp(14)); p.setBackgroundColor(PANEL); TextView h=text(heading,15,accent); h.setTypeface(Typeface.DEFAULT_BOLD); p.addView(h); p.addView(text(body,13,WHITE)); LinearLayout.LayoutParams lp=matchWrap(); lp.setMargins(0,dp(5),0,dp(7)); root.addView(p,lp); }
    private void addButton(String label,View.OnClickListener action,int color) { Button b=button(label,action,color); LinearLayout.LayoutParams p=matchWrap(); p.setMargins(0,dp(6),0,dp(6)); root.addView(b,p); }
    private Button button(String label,View.OnClickListener action,int color) { Button b=new Button(this); b.setText(label); b.setTextColor(color==PANEL?WHITE:BG); b.setTextSize(13); b.setAllCaps(false); b.setGravity(Gravity.CENTER); b.setBackgroundColor(color); b.setOnClickListener(action); return b; }
    private TextView text(String value,int size,int color) { TextView v=new TextView(this); v.setText(value); v.setTextSize(size); v.setTextColor(color); v.setLineSpacing(0,1.15f); return v; }
    private void spacer(int n) { View v=new View(this); root.addView(v,new LinearLayout.LayoutParams(1,dp(n))); }
    private LinearLayout.LayoutParams matchWrap(){ return new LinearLayout.LayoutParams(-1,-2); }
    private int dp(int n){ return (int)(n*getResources().getDisplayMetrics().density); }
    private void toastDialog(String title,String message){ new AlertDialog.Builder(this).setTitle(title).setMessage(message).setPositiveButton("OK",null).show(); }
}
