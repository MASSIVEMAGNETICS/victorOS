package ai.ethica.victoros;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Collections;
import java.util.List;

public final class MainActivity extends Activity {
    private static final int BG = Color.rgb(5, 6, 7), PANEL = Color.rgb(18, 21, 24);
    private static final int GREEN = Color.rgb(168, 255, 53), PURPLE = Color.rgb(183, 92, 255), WHITE = Color.rgb(238, 242, 244);
    private static final int REQ_SCREEN=2001, REQ_CAMERA=2002, REQ_MIC=2003;
    private static final long CAMERA_PREVIEW_REFRESH_MS=500L;
    private VictorStore store;
    private VictorPhysiology.Runtime physiology;
    private VictorCognitiveOrgans cognitive;
    private LinearLayout root;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        store = new VictorStore(this);
        physiology = new VictorPhysiology.Runtime(store, store, VictorPhysiology.setOf("owner","local_user"), Collections.emptySet());
        cognitive = new VictorCognitiveOrgans(store);
        showHome();
    }

    private void frame(String title, boolean back) {
        ScrollView scroll = new ScrollView(this); scroll.setBackgroundColor(BG);
        root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setPadding(dp(18), dp(18), dp(18), dp(36));
        scroll.addView(root); setContentView(scroll);
        if (back) addButton("‹ VICTOROS", v -> showHome(), PURPLE);
        TextView brand = text(title, 28, GREEN); brand.setTypeface(Typeface.DEFAULT_BOLD); root.addView(brand);
        root.addView(text("GOVERNED PERSISTENT EXPERIENCE INTELLIGENCE", 11, Color.GRAY));
        spacer(16);
    }

    private void showHome() {
        frame("VICTOR//OS", false);
        VictorPhysiology.State p=physiology.state();
        addPanel("SYSTEM "+p.governanceMode,
                "Born " + store.born() + "\nReceipts " + store.events().length() + "  •  Chain " + (store.verify().isEmpty() ? "VERIFIED" : "BROKEN")
                        +"\nHuman STOP "+(p.humanStop?"ACTIVE":"clear")+"  •  Sensory receipt "+shortHash(p.physiologyReceiptHead),
                p.governanceMode==VictorPhysiology.GovernanceMode.GREEN?GREEN:Color.RED);
        addPanel("COGNITIVE ORGAN BUS", VictorCognitiveOrgans.ARCHITECTURE
                + "\nVRCO " + VictorCognitiveOrgans.VRCO_VERSION
                + "  •  RAMS " + VictorCognitiveOrgans.RAMS_VERSION
                + "\nArchitecture receipt " + shortHash(cognitive.architectureAttestation()), PURPLE);
        LinearLayout row = null;
        String[][] organs = {
                {"◉ CORTEX", "Intent and cognition"}, {"▣ MEMORY VAULT", "Persistent experience"},
                {"⌁ CHRONOS", "Verified causal history"}, {"◇ ETHICA", "Authority and policy"},
                {"♥ HOMEOSTASIS", "Internal operating state"}, {"⊙ GOD'S EYE", "Shared sensory world"},
                {"⌘ VRCO", "Relational cognition"}, {"⚙ RAMS", "Governed discovery"},
                {">_ COMMAND", "Bounded execution"}
        };
        for (int i=0;i<organs.length;i++) {
            if (i%2==0) { row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); root.addView(row, matchWrap()); }
            Button b = button(organs[i][0] + "\n" + organs[i][1], v -> openOrgan(indexOfButton(v)), PANEL);
            b.setTag(i);
            LinearLayout.LayoutParams pms = new LinearLayout.LayoutParams(0, dp(112), 1); pms.setMargins(dp(4),dp(4),dp(4),dp(4)); row.addView(b,pms);
        }
    }

    private int indexOfButton(View view) {
        Object tag = view.getTag();
        return tag instanceof Integer ? (Integer) tag : 8;
    }

    private void openOrgan(int index) {
        switch(index) {
            case 0: cortex(); break; case 1: memory(); break; case 2: chronos(); break;
            case 3: ethica(); break; case 4: homeostasis(); break; case 5: godsEye(); break;
            case 6: relational(); break; case 7: rams(); break; default: command();
        }
    }

    private void cortex() {
        frame("CORTEX", true); addPanel("LOCAL COGNITION BUS", "Capture an intent. Memory mutation passes through the governed physiology runtime.", PURPLE);
        EditText input = input("What matters right now?"); root.addView(input, matchWrap());
        addButton("COMMIT INTENT", v -> {
            String s=input.getText().toString().trim(); if(s.isEmpty()) return;
            VictorPhysiology.ActionProposal p=proposal("commit_intent","memory.local").consequence(.08).capabilityPower(.08).metadata("length",Integer.toString(s.length())).build();
            VictorPhysiology.GateDecision d=physiology.execute(p,()->{store.append("CORTEX",s,"OBSERVED");return "Intent committed";});
            if(d.executed())input.setText("");showDecision("Cortex",d);
        }, GREEN);
    }

    private void memory() {
        frame("MEMORY VAULT", true); JSONArray events=store.events();
        addPanel("EPISODIC MEMORY", events.length()+" durable receipts/experiences on this device", PURPLE);
        for(int i=events.length()-1;i>=Math.max(0,events.length()-30);i--) try { JSONObject e=events.getJSONObject(i); addPanel(e.optString("organ")+" · "+e.optString("state"), e.optString("message")+"\n"+e.optString("timestamp"), WHITE); } catch(Exception ignored) {}
    }

    private void chronos() {
        frame("CHRONOS LEDGER", true); List<String> faults=store.verify();
        addPanel(faults.isEmpty()?"CHAIN VERIFIED":"CHAIN FAILURE", faults.isEmpty()?"Every local receipt links cryptographically to the prior receipt.":faults.toString(), faults.isEmpty()?GREEN:Color.RED);
        JSONArray events=store.events(); for(int i=events.length()-1;i>=Math.max(0,events.length()-20);i--) try { JSONObject e=events.getJSONObject(i); String h=e.optString("hash");addPanel("#"+e.optInt("id")+" "+e.optString("organ"), shortHash(h)+"\n"+e.optString("message"), PURPLE); } catch(Exception ignored) {}
    }

    private void ethica() {
        frame("ETHICA GOVERNOR", true);VictorPhysiology.State s=physiology.state();
        addPanel("PHYSIOLOGY MODE · "+s.governanceMode, s.summary(), s.governanceMode==VictorPhysiology.GovernanceMode.GREEN?GREEN:Color.RED);
        addPanel("ACTIVE CONSTITUTION", "Identity continuity\nHuman STOP authority\nProvenance required\nNo silent canonical overwrite\nNo unauthorized capability escalation\nEvidence before claims\nUnknown is valid\nEvery consequential mutation receives a receipt", GREEN);
        addPanel("COGNITIVE AUTHORITY", "VRCO may INFER and PROPOSE. RAMS may DISCOVER and PROPOSE. Neither may silently canonicalize truth, bypass Ethica, or execute synthesized code. Choice + VUEB + verification remain mandatory.", PURPLE);
        addPanel("NETWORK AUTHORITY", "ABSENT\nThis local-first build requests no INTERNET permission.", PURPLE);
    }

    private void homeostasis() {
        frame("HOMEOSTASIS", true); metric("ENERGY", "energy"); metric("INTEGRITY", "integrity"); metric("FOCUS", "focus");
        VictorPhysiology.State s=physiology.state();addPanel("ORGANISM STATE",s.summary(),s.governanceMode==VictorPhysiology.GovernanceMode.GREEN?GREEN:Color.RED);
        addButton("RUN SELF-CHECK", v -> {
            VictorPhysiology.ActionProposal p=proposal("self_check","state.integrity").consequence(.05).capabilityPower(.05).build();
            VictorPhysiology.GateDecision d=physiology.execute(p,()->{List<String> faults=store.verify();store.setMetric("integrity",faults.isEmpty()?100:25);store.append("HOMEOSTASIS",faults.isEmpty()?"Self-check passed":"Self-check failed",faults.isEmpty()?"VERIFIED":"FAULT");return faults.isEmpty()?"Self-check passed":"Self-check failed";});
            if(d.executed())homeostasis();else showDecision("Self-check",d);
        }, GREEN);
    }

    private void godsEye(){
        frame("GOD'S EYE VIEW",true);VictorPhysiology.State s=physiology.state();
        addPanel("COMMON SHARED SPACE", "Screen pixels + active UI + camera + microphone + app context feed one local world model. Raw sensory payloads stay in RAM; persistent history stores only hashes/metadata. No network exfiltration path exists in this build.", PURPLE);
        addPanel("GOVERNANCE · "+s.governanceMode,"Human STOP="+s.humanStop+"\n"+s.summary(),s.humanStop?Color.RED:GREEN);
        if(!s.humanStop)addButton("HUMAN STOP — CUT ALL SENSES",v->activateHumanStop(),Color.RED);
        else addButton("OWNER RESET HUMAN STOP",v->{try{physiology.ownerResetHumanStop("local-owner-ui");godsEye();}catch(Exception e){toastDialog("Reset blocked",e.getMessage());}},GREEN);

        boolean usage=VictorAppContextSensor.hasUsageAccess(this);
        addPanel("APP CONTEXT",usage?"Usage Access enabled\nRecent foreground: "+VictorAppContextSensor.recentForegroundPackage(this):"Usage Access not enabled. Android requires you to grant this special access in Settings.",usage?GREEN:PURPLE);
        addButton("OPEN USAGE ACCESS SETTINGS",v->openGovernedSettings(Settings.ACTION_USAGE_ACCESS_SETTINGS,"usage_access_settings"),PURPLE);
        if(usage)addButton("SCAN APP CONTEXT NOW",v->{VictorAppContextSensor.snapshot(this);godsEye();},GREEN);

        addPanel("ACTIVE UI",isAccessibilityEnabled()?"Accessibility perception appears enabled. Victor can inspect the active UI hierarchy; gesture execution remains disabled in this build.":"Enable VictorOS in Android Accessibility settings to expose the active UI tree.",isAccessibilityEnabled()?GREEN:PURPLE);
        addButton("OPEN ACCESSIBILITY SETTINGS",v->openGovernedSettings(Settings.ACTION_ACCESSIBILITY_SETTINGS,"accessibility_settings"),PURPLE);

        addPanel("SCREEN EYE", "Android MediaProjection requires a system consent prompt before pixels can be captured.", WHITE);
        addButton("START SCREEN EYE",v->requestScreenEye(),GREEN);addButton("STOP SCREEN EYE",v->stopSensor(VictorScreenCaptureService.class,"sensor.screen.stop"),PURPLE);

        addPanel("CAMERA EYE",checkSelfPermission(Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED?"Camera permission granted":"Camera permission required",WHITE);
        if(s.humanStop) {
            addPanel("LIVE CAMERA PREVIEW", "Blocked by Human STOP. Ephemeral camera pixels are unavailable until the owner explicitly resets Human STOP.", Color.RED);
        } else {
            addLiveCameraPreview();
        }
        addButton("START CAMERA EYE",v->requestCameraEye(),GREEN);addButton("STOP CAMERA EYE",v->stopSensor(VictorCameraService.class,"sensor.camera.stop"),PURPLE);

        addPanel("MICROPHONE EAR",checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED?"Microphone permission granted":"Microphone permission required",WHITE);
        addButton("START MICROPHONE EAR",v->requestMicrophoneEar(),GREEN);addButton("STOP MICROPHONE EAR",v->stopSensor(VictorMicrophoneService.class,"sensor.microphone.stop"),PURPLE);

        addPanel("LATEST PERSISTENT SENSOR RECEIPT",store.latestGodsEyeMetadata(),PURPLE);
        addPanel("LIVE SHARED-SPACE FEED",GodsEyeWorldModel.summary(),WHITE);
    }

    private void addLiveCameraPreview() {
        addPanel("LIVE CAMERA PREVIEW", "RAM-only render of the newest bounded CAMERA JPEG. Nothing new is persisted by this view. Refresh stops automatically when this view leaves the screen or Human STOP activates.", PURPLE);
        ImageView preview = new ImageView(this);
        preview.setAdjustViewBounds(true);
        preview.setScaleType(ImageView.ScaleType.CENTER_CROP);
        preview.setBackgroundColor(Color.BLACK);
        preview.setContentDescription("God's Eye live camera preview");
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(300));
        params.setMargins(0, dp(4), 0, dp(8));
        root.addView(preview, params);
        refreshCameraPreview(preview);
    }

    private void refreshCameraPreview(ImageView preview) {
        if(!preview.isAttachedToWindow()) return;
        VictorPhysiology.State current=physiology.state();
        if(current.humanStop) {
            preview.setImageDrawable(null);
            return;
        }
        byte[] frame=GodsEyeWorldModel.latestBinary("CAMERA");
        if(frame!=null&&frame.length>0) {
            Bitmap bitmap=BitmapFactory.decodeByteArray(frame,0,frame.length);
            if(bitmap!=null) preview.setImageBitmap(bitmap);
        }
        preview.postDelayed(() -> refreshCameraPreview(preview), CAMERA_PREVIEW_REFRESH_MS);
    }

    private void relational() {
        frame("VRCO · RELATIONAL COGNITION", true);
        VictorCognitiveOrgans.RelationalReport report = cognitive.scanLocalChronos();
        addPanel("PAIRWISE / PROCESS SCAN", report.summary(), GREEN);
        addPanel("AUTHORITY BOUNDARY", "Results are candidate relationships only. INFERRED ≠ VERIFIED ≠ CANONICAL. VRCO cannot bypass Ethica, Choice, VUEB, or Chronos.", PURPLE);
        addPanel("STRONGEST LOCAL RELATIONS", report.strongestRelations.isEmpty()?"No relation above threshold yet.":join(report.strongestRelations), WHITE);
        addPanel("RECURRING TRANSITIONS", report.recurringProcesses.isEmpty()?"No repeated transition motif yet.":join(report.recurringProcesses), WHITE);
        addButton("RUN SCAN + WRITE INFERENCE RECEIPT", v -> {
            VictorPhysiology.ActionProposal p=proposal("vrco_scan","cognition.relational.scan").consequence(.04).uncertainty(.08).capabilityPower(.05).build();
            VictorPhysiology.GateDecision d=physiology.execute(p,()->{
                VictorCognitiveOrgans.RelationalReport fresh=cognitive.scanLocalChronos();
                store.append("VRCO",fresh.summary()+" strongest="+fresh.strongestRelations,"INFERRED");
                return "VRCO inference receipt committed: "+shortHash(fresh.receiptDigest);
            });
            if(d.executed())relational();else showDecision("VRCO",d);
        }, GREEN);
    }

    private void rams() {
        frame("RAMS · GOVERNED DISCOVERY", true);
        addPanel("DISCOVERY ORGAN", cognitive.ramsGateSummary(), PURPLE);
        addPanel("CURRENT APK MODE", "RAMS is intentionally fail-closed. The phone does not exec generated Python/AST payloads and does not treat structural receipt shape as a cryptographic signature.", GREEN);
        addPanel("ORGAN PATH", VictorCognitiveOrgans.ARCHITECTURE+"\nAttestation "+shortHash(cognitive.architectureAttestation()), WHITE);
        addPanel("LOCAL SAFETY PREFLIGHT", cognitive.localSafetyPreflight()?"PASS · Chronos receipt chain is trusted":"BLOCKED · local receipt chain is not trusted", cognitive.localSafetyPreflight()?GREEN:Color.RED);
        addButton("RUN RAMS SAFETY PREFLIGHT + RECEIPT", v -> {
            VictorPhysiology.ActionProposal p=proposal("rams_preflight","cognition.discovery.preflight").consequence(.03).uncertainty(.05).capabilityPower(.04).build();
            VictorPhysiology.GateDecision d=physiology.execute(p,()->{
                boolean pass=cognitive.localSafetyPreflight();
                if(!pass)throw new IllegalStateException("Chronos ledger is not trusted");
                String attestation=cognitive.architectureAttestation();
                store.append("RAMS","Governed discovery preflight passed; synthesized-code execution remains gated; architecture="+shortHash(attestation),"PREFLIGHT");
                return "RAMS preflight passed. Discovery execution remains gated.";
            });
            if(d.executed())rams();else showDecision("RAMS",d);
        }, GREEN);
    }

    private void activateHumanStop(){
        physiology.setHumanStop();stopService(new Intent(this,VictorScreenCaptureService.class));stopService(new Intent(this,VictorCameraService.class));stopService(new Intent(this,VictorMicrophoneService.class));GodsEyeWorldModel.clearEphemeral();godsEye();
    }

    private void requestScreenEye(){
        VictorPhysiology.ActionProposal p=proposal("request_screen_consent","sensor.screen.consent").consequence(.08).uncertainty(.05).capabilityPower(.10).build();
        VictorPhysiology.GateDecision d=physiology.execute(p,()->{MediaProjectionManager m=(MediaProjectionManager)getSystemService(MEDIA_PROJECTION_SERVICE);startActivityForResult(m.createScreenCaptureIntent(),REQ_SCREEN);return "screen consent requested";});
        if(!d.executed())showDecision("Screen eye",d);
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode==REQ_SCREEN){
            if(resultCode!=RESULT_OK||data==null){toastDialog("Screen eye","Screen capture consent was not granted.");return;}
            final Intent token=data;
            VictorPhysiology.ActionProposal p=proposal("start_screen_eye","sensor.screen.capture").consequence(.20).uncertainty(.05).capabilityPower(.28).build();
            VictorPhysiology.GateDecision d=physiology.execute(p,()->{Intent s=new Intent(this,VictorScreenCaptureService.class);s.putExtra(VictorScreenCaptureService.EXTRA_RESULT_CODE,resultCode);s.putExtra(VictorScreenCaptureService.EXTRA_DATA,token);startForegroundService(s);return "screen eye started";});showDecision("Screen eye",d);
        }
    }

    private void requestCameraEye(){
        if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED){
            VictorPhysiology.GateDecision d=physiology.execute(proposal("request_camera_permission","permission.camera").consequence(.08).capabilityPower(.10).build(),()->{requestPermissions(new String[]{Manifest.permission.CAMERA},REQ_CAMERA);return "camera permission requested";});if(!d.executed())showDecision("Camera",d);return;
        }startCameraEye();
    }
    private void startCameraEye(){VictorPhysiology.GateDecision d=physiology.execute(proposal("start_camera_eye","sensor.camera.capture").consequence(.20).uncertainty(.05).capabilityPower(.28).build(),()->{startForegroundService(new Intent(this,VictorCameraService.class));return "camera eye started";});showDecision("Camera eye",d);}

    private void requestMicrophoneEar(){
        if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){
            VictorPhysiology.GateDecision d=physiology.execute(proposal("request_microphone_permission","permission.microphone").consequence(.08).capabilityPower(.10).build(),()->{requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},REQ_MIC);return "microphone permission requested";});if(!d.executed())showDecision("Microphone",d);return;
        }startMicrophoneEar();
    }
    private void startMicrophoneEar(){VictorPhysiology.GateDecision d=physiology.execute(proposal("start_microphone_ear","sensor.microphone.capture").consequence(.20).uncertainty(.05).capabilityPower(.28).build(),()->{startForegroundService(new Intent(this,VictorMicrophoneService.class));return "microphone ear started";});showDecision("Microphone ear",d);}

    @Override public void onRequestPermissionsResult(int requestCode,String[] permissions,int[] grantResults){
        super.onRequestPermissionsResult(requestCode,permissions,grantResults);boolean granted=grantResults.length>0&&grantResults[0]==PackageManager.PERMISSION_GRANTED;
        if(requestCode==REQ_CAMERA){if(granted)startCameraEye();else toastDialog("Camera","Permission denied.");}
        if(requestCode==REQ_MIC){if(granted)startMicrophoneEar();else toastDialog("Microphone","Permission denied.");}
    }

    private void stopSensor(Class<?> cls,String capability){VictorPhysiology.GateDecision d=physiology.execute(proposal("stop_sensor",capability).consequence(.01).capabilityPower(.02).build(),()->{stopService(new Intent(this,cls));return "sensor stopped";});showDecision("Sensor",d);}
    private void openGovernedSettings(String action,String capability){VictorPhysiology.GateDecision d=physiology.execute(proposal("open_settings",capability).consequence(.03).capabilityPower(.03).build(),()->{startActivity(new Intent(action));return "settings opened";});if(!d.executed())showDecision("Settings",d);}

    private boolean isAccessibilityEnabled(){String enabled=Settings.Secure.getString(getContentResolver(),Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);return enabled!=null&&enabled.toLowerCase().contains("ai.ethica.victoros")&&enabled.toLowerCase().contains("victoraccessibilityservice");}

    private void metric(String label,String key) { int value=store.getMetric(key,50); addPanel(label+"  "+value+"%", progress(value), value>40?GREEN:Color.RED); }
    private String progress(int value) { int blocks=value/10; return "██████████".substring(0,blocks)+"░░░░░░░░░░".substring(0,10-blocks); }

    private void command() {
        frame("COMMAND CENTER", true); addPanel("BOUNDED EXECUTION", "Commands mutate only VictorOS local state and pass through VictorPhysiologyRuntime before execution.", PURPLE);
        EditText input=input("remember <text> | focus <0-100> | status | verify | scan"); root.addView(input,matchWrap());
        addButton("AUTHORIZE + EXECUTE", v -> execute(input.getText().toString().trim()), GREEN);
    }

    private void execute(String cmd) {
        if(cmd.startsWith("remember ")&&cmd.length()>9){String memory=cmd.substring(9);VictorPhysiology.GateDecision d=physiology.execute(proposal("remember","memory.local").consequence(.08).capabilityPower(.08).build(),()->{store.append("MEMORY",memory,"COMMITTED");return "Remembered: "+memory;});showDecision("Command",d);return;}
        if(cmd.startsWith("focus ")){try{int n=Integer.parseInt(cmd.substring(6).trim());if(n<0||n>100)throw new NumberFormatException();VictorPhysiology.GateDecision d=physiology.execute(proposal("set_focus","state.focus").consequence(.05).capabilityPower(.05).build(),()->{store.setMetric("focus",n);return "Focus set to "+n;});showDecision("Command",d);}catch(Exception e){toastDialog("BLOCKED_POLICY","focus must be 0–100");}return;}
        if(cmd.equals("status")){VictorPhysiology.GateDecision d=physiology.execute(proposal("status","state.read").consequence(.01).capabilityPower(.01).build(),()->"Energy "+store.getMetric("energy",0)+" · Integrity "+store.getMetric("integrity",0)+" · Focus "+store.getMetric("focus",0)+" · Physiology "+physiology.state().governanceMode+" · VRCO "+VictorCognitiveOrgans.VRCO_VERSION+" · RAMS "+VictorCognitiveOrgans.RAMS_VERSION);showDecision("Command",d);return;}
        if(cmd.equals("verify")){VictorPhysiology.GateDecision d=physiology.execute(proposal("verify","chronos.verify").consequence(.01).capabilityPower(.01).build(),()->store.verify().isEmpty()?"Chronos chain verified":"Chronos chain failed");showDecision("Command",d);return;}
        if(cmd.equals("scan")){relational();return;}
        toastDialog("BLOCKED_AUTHORITY","Rejected: command is outside the current capability vocabulary.");
    }

    private VictorPhysiology.ActionProposal.Builder proposal(String name,String capability){return VictorPhysiology.ActionProposal.builder(name,capability).provenance("local-owner-ui").requireAuthority("local_user");}
    private void showDecision(String title,VictorPhysiology.GateDecision d){String body="status="+d.status+"\nrisk="+String.format(java.util.Locale.US,"%.3f",d.riskScore)+"\nreasons="+d.reasons+(d.actualOutcome==null?"":"\noutcome="+d.actualOutcome);toastDialog(title,body);}
    private String shortHash(String h){if(h==null)return "none";return h.length()>16?h.substring(0,16)+"…":h;}
    private String join(List<String> items){StringBuilder out=new StringBuilder();for(String item:items){if(out.length()>0)out.append("\n");out.append("• ").append(item);}return out.toString();}
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
