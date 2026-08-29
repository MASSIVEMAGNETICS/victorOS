package ai.ethica.victoros;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
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
    private static final int BG = Color.rgb(5, 6, 7);
    private static final int PANEL = Color.rgb(18, 21, 24);
    private static final int GREEN = Color.rgb(168, 255, 53);
    private static final int PURPLE = Color.rgb(183, 92, 255);
    private static final int WHITE = Color.rgb(238, 242, 244);
    private static final int MUTED = Color.rgb(145, 154, 162);

    private VictorStore store;
    private SecureSecretStore secrets;
    private LinearLayout root;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        store = new VictorStore(this);
        secrets = new SecureSecretStore(this);
        SyncJobService.reconcile(this, store);
        handleSharedText(getIntent());
        showHome();
        if (store.isSyncEnabled()) syncNow(false);
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleSharedText(intent);
        showNow();
    }

    private void frame(String title, boolean back) {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(BG);
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(16), dp(16), dp(34));
        scroll.addView(root);
        setContentView(scroll);
        if (back) addButton("‹ EMPIRE", v -> showHome(), PURPLE);
        TextView brand = text(title, 27, GREEN);
        brand.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(brand);
        root.addView(text("VICTOR // GOD'S EYE VIEW // OWNER CONTROL PLANE", 10, MUTED));
        spacer(14);
    }

    private void showHome() {
        frame("EMPIRE", false);
        String chain = store.verify().isEmpty() ? "VERIFIED" : "BROKEN";
        String sync = store.isSyncEnabled() ? "AUTO" : "LOCAL";
        addPanel("SYSTEM ALIVE", "Chronos " + chain + "  •  " + store.nodes().length() + " nodes  •  " + store.edges().length() + " edges\nMode " + sync + "  •  Revision " + store.getLastRemoteRevision(), GREEN);

        String[][] menu = {
                {"NOW", "What needs you"}, {"MAP", "Node clusters"},
                {"PROJECTS", "Work + blockers"}, {"REVENUE", "Money loops"},
                {"MEMORY", "Episodes + receipts"}, {"EVIDENCE", "Truth + provenance"},
                {"SYSTEMS", "Victor organs"}, {"CONTROL", "Chiefs + sync"}
        };
        LinearLayout row = null;
        for (int i = 0; i < menu.length; i++) {
            if (i % 2 == 0) {
                row = new LinearLayout(this);
                row.setOrientation(LinearLayout.HORIZONTAL);
                root.addView(row, matchWrap());
            }
            final int index = i;
            Button b = button(menu[i][0] + "\n" + menu[i][1], v -> openSection(index), PANEL);
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(96), 1);
            p.setMargins(dp(4), dp(4), dp(4), dp(4));
            row.addView(b, p);
        }
        spacer(10);
        JSONArray top = store.attentionNodes(3);
        for (int i = 0; i < top.length(); i++) nodePanel(top.optJSONObject(i), i == 0 ? GREEN : PURPLE);
    }

    private void openSection(int index) {
        switch (index) {
            case 0: showNow(); break;
            case 1: showMap(); break;
            case 2: showProjects(); break;
            case 3: showRevenue(); break;
            case 4: showMemory(); break;
            case 5: showEvidence(); break;
            case 6: showSystems(); break;
            default: showControl();
        }
    }

    private void showNow() {
        frame("NOW", true);
        addPanel("SPAN OF CONTROL", "Victor surfaces three priorities here. Workers report through chiefs and orchestrators; everything else stays below the fold.", PURPLE);
        JSONArray top = store.attentionNodes(3);
        for (int i = 0; i < top.length(); i++) nodePanel(top.optJSONObject(i), i == 0 ? GREEN : WHITE);
        if (!store.getLastSyncError().isEmpty()) addPanel("SYNC ATTENTION", store.getLastSyncError(), Color.RED);
        addButton("SYNC NOW", v -> syncNow(true), GREEN);
    }

    private void showMap() {
        frame("MAP", true);
        addPanel("GRAPH OF GRAPHS", "Tap a node to inspect it. Connections are typed relationships; the map is a projection of canonical state, not the source of truth.", PURPLE);
        GraphView graph = new GraphView(this);
        graph.setData(store.nodes(), store.edges());
        graph.setOnNodeSelectedListener(node -> nodeDialog(node));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, dp(470));
        p.setMargins(0, dp(6), 0, dp(10));
        root.addView(graph, p);
    }

    private void showProjects() {
        frame("PROJECTS", true);
        addPanel("EXECUTION PORTFOLIO", "Projects are nodes with explicit ownership, status and attention. Terminal outcomes should emit Chronos receipts.", PURPLE);
        JSONArray nodes = store.nodes();
        int shown = 0;
        for (int i = 0; i < nodes.length(); i++) {
            JSONObject node = nodes.optJSONObject(i);
            if (node == null) continue;
            String kind = node.optString("kind");
            if ("project".equals(kind) || "product".equals(kind) || "research_layer".equals(kind)) {
                nodePanel(node, shown++ == 0 ? GREEN : WHITE);
            }
        }
        if (shown == 0) addPanel("NO PROJECT NODES", "Add projects from CONTROL.", MUTED);
    }

    private void showRevenue() {
        frame("REVENUE", true);
        addPanel("SELF-FUNDING LOOPS", "This view contains revenue and distribution nodes only. A sale is not canonical until the transaction/outcome is observed and receipted.", PURPLE);
        JSONArray nodes = store.nodes();
        int shown = 0;
        for (int i = 0; i < nodes.length(); i++) {
            JSONObject node = nodes.optJSONObject(i);
            if (node == null) continue;
            String cluster = node.optString("cluster");
            if ("REVENUE".equals(cluster) || "DISTRIBUTION".equals(cluster)) {
                nodePanel(node, shown++ < 2 ? GREEN : WHITE);
            }
        }
    }

    private void showMemory() {
        frame("MEMORY", true);
        JSONArray events = store.events();
        addPanel("CHRONOS MEMORY", events.length() + " durable local receipts\nRemote revision: " + store.getLastRemoteRevision(), PURPLE);
        for (int i = events.length() - 1; i >= Math.max(0, events.length() - 35); i--) {
            JSONObject e = events.optJSONObject(i);
            if (e == null) continue;
            addPanel("#" + e.optInt("id") + "  " + e.optString("organ") + " · " + e.optString("state"), e.optString("message") + "\n" + e.optString("timestamp"), WHITE);
        }
        addButton("SHARE CANONICAL SNAPSHOT", v -> shareSnapshot(), GREEN);
    }

    private void showEvidence() {
        frame("EVIDENCE", true);
        List<String> faults = store.verify();
        addPanel(faults.isEmpty() ? "CHAIN VERIFIED" : "CHAIN FAILURE", faults.isEmpty() ? "Every local receipt cryptographically links to the prior receipt." : faults.toString(), faults.isEmpty() ? GREEN : Color.RED);
        addPanel("EPISTEMIC RULES", "Observed ≠ inferred ≠ predicted.\nCorrelation never silently becomes causality.\nRemote graph imports require a revision and create a local evidence receipt.", PURPLE);
        JSONArray events = store.events();
        for (int i = events.length() - 1; i >= Math.max(0, events.length() - 15); i--) {
            JSONObject e = events.optJSONObject(i);
            if (e == null) continue;
            String hash = e.optString("hash");
            addPanel("#" + e.optInt("id") + " " + e.optString("state"), (hash.length() > 16 ? hash.substring(0, 16) + "…" : hash) + "\n" + e.optString("message"), WHITE);
        }
    }

    private void showSystems() {
        frame("SYSTEMS", true);
        addPanel("VICTOR SUBSTRATE", "The Empire shell sits above the existing organs. It does not replace Chronos, Ethica, Cortex or local state.", PURPLE);
        nodeById("victoros");
        nodeById("gev");
        nodeById("chronos");
        nodeById("ethica");
        addPanel("HOMEOSTASIS", "Energy " + store.getMetric("energy", 0) + "%  •  Integrity " + store.getMetric("integrity", 0) + "%  •  Focus " + store.getMetric("focus", 0) + "%", GREEN);
        addButton("CORTEX", v -> cortex(), PANEL);
        addButton("HOMEOSTASIS", v -> homeostasis(), PANEL);
        addButton("BOUNDED COMMAND", v -> command(), PANEL);
    }

    private void showControl() {
        frame("CONTROL", true);
        addPanel("ROOT AUTHORITY", "Bando → Victor Prime → Empire Steward → Chiefs → Orchestrators → Workers", GREEN);
        JSONArray nodes = store.nodes();
        for (int i = 0; i < nodes.length(); i++) {
            JSONObject node = nodes.optJSONObject(i);
            if (node == null) continue;
            String kind = node.optString("kind");
            if ("chief".equals(kind) || "meta_orchestrator".equals(kind) || "portfolio_orchestrator".equals(kind)) nodePanel(node, PURPLE);
        }

        spacer(8);
        addPanel("AUTO UPDATE", "Background sync uses Android JobScheduler (minimum 15-minute periodic cadence). The app also attempts a sync when opened. HTTPS + bearer token are mandatory.", WHITE);
        EditText endpoint = input("https://your-victor-host/v1/sync");
        endpoint.setText(store.getSyncEndpoint());
        root.addView(endpoint, matchWrap());
        EditText token = input(secrets.getToken().isEmpty() ? "Bearer token" : "Bearer token already stored — enter only to replace");
        token.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        root.addView(token, matchWrap());
        addButton("SAVE SYNC CONFIG", v -> {
            String ep = endpoint.getText().toString().trim();
            if (!ep.isEmpty() && !ep.startsWith("https://")) {
                toastDialog("Rejected", "Endpoint must begin with https://");
                return;
            }
            store.setSyncEndpoint(ep);
            String entered = token.getText().toString().trim();
            if (!entered.isEmpty()) secrets.putToken(entered);
            store.append("CONTROL", "Sync configuration updated for " + (ep.isEmpty() ? "<disabled endpoint>" : ep), "OWNER_SETTING");
            token.setText("");
            SyncJobService.reconcile(this, store);
            toastDialog("Saved", "Sync configuration stored. Token is protected by Android Keystore.");
        }, GREEN);
        addButton(store.isSyncEnabled() ? "DISABLE AUTO SYNC" : "ENABLE AUTO SYNC", v -> {
            if (!store.isSyncEnabled() && (store.getSyncEndpoint().isEmpty() || secrets.getToken().isEmpty())) {
                toastDialog("Cannot enable", "Save an HTTPS endpoint and bearer token first.");
                return;
            }
            store.setSyncEnabled(!store.isSyncEnabled());
            SyncJobService.reconcile(this, store);
            showControl();
        }, store.isSyncEnabled() ? Color.RED : GREEN);
        addButton("SYNC NOW", v -> syncNow(true), PURPLE);
        addPanel("SYNC STATUS", "Last: " + store.getLastSyncAt() + "\nRevision: " + store.getLastRemoteRevision() + (store.getLastSyncError().isEmpty() ? "" : "\nError: " + store.getLastSyncError()), MUTED);

        spacer(8);
        addButton("ADD / UPDATE NODE", v -> nodeEditor(), GREEN);
        addButton("SHARE SNAPSHOT", v -> shareSnapshot(), PURPLE);
    }

    private void cortex() {
        frame("CORTEX", true);
        addPanel("LOCAL COGNITION BUS", "Capture an intent. Victor records it as experience; execution remains capability-bounded.", PURPLE);
        EditText input = input("What matters right now?");
        root.addView(input, matchWrap());
        addButton("COMMIT INTENT", v -> {
            String s = input.getText().toString().trim();
            if (s.isEmpty()) return;
            store.append("CORTEX", s, "OBSERVED");
            input.setText("");
            toastDialog("Intent committed", "Stored locally with a chained Chronos receipt.");
        }, GREEN);
    }

    private void homeostasis() {
        frame("HOMEOSTASIS", true);
        metric("ENERGY", "energy");
        metric("INTEGRITY", "integrity");
        metric("FOCUS", "focus");
        addButton("RUN SELF-CHECK", v -> {
            List<String> faults = store.verify();
            store.setMetric("integrity", faults.isEmpty() ? 100 : 25);
            store.append("HOMEOSTASIS", faults.isEmpty() ? "Self-check passed" : "Self-check failed", faults.isEmpty() ? "VERIFIED" : "FAULT");
            homeostasis();
        }, GREEN);
    }

    private void command() {
        frame("COMMAND", true);
        addPanel("BOUNDED EXECUTION", "This console mutates only VictorOS private state. Network sync is a separate capability and cannot execute arbitrary server commands.", PURPLE);
        EditText input = input("remember <text> | focus <0-100> | status | verify | snapshot");
        root.addView(input, matchWrap());
        addButton("AUTHORIZE + EXECUTE", v -> execute(input.getText().toString().trim()), GREEN);
    }

    private void execute(String cmd) {
        String result;
        String state = "COMPLETED";
        if (cmd.startsWith("remember ") && cmd.length() > 9) result = "Remembered: " + cmd.substring(9);
        else if (cmd.startsWith("focus ")) {
            try {
                int n = Integer.parseInt(cmd.substring(6).trim());
                if (n < 0 || n > 100) throw new Exception();
                store.setMetric("focus", n);
                result = "Focus set to " + n;
            } catch (Exception e) {
                result = "Rejected: focus must be 0–100";
                state = "BLOCKED_POLICY";
            }
        } else if (cmd.equals("status")) result = "Energy " + store.getMetric("energy", 0) + " · Integrity " + store.getMetric("integrity", 0) + " · Focus " + store.getMetric("focus", 0);
        else if (cmd.equals("verify")) result = store.verify().isEmpty() ? "Chronos chain verified" : "Chronos chain failed";
        else if (cmd.equals("snapshot")) result = "Snapshot contains " + store.nodes().length() + " nodes, " + store.edges().length() + " edges, " + store.events().length() + " receipts";
        else {
            result = "Rejected: command is outside the current capability lease";
            state = "BLOCKED_AUTHORITY";
        }
        store.append("COMMAND", cmd.isEmpty() ? "<empty>" : cmd + " → " + result, state);
        toastDialog(state, result);
    }

    private void syncNow(boolean showResult) {
        if (!store.isSyncEnabled()) {
            if (showResult) toastDialog("Sync disabled", "Enable automatic sync in CONTROL after configuring an HTTPS endpoint and token.");
            return;
        }
        new Thread(() -> {
            EmpireSyncClient.Result result = EmpireSyncClient.sync(getApplicationContext(), store);
            runOnUiThread(() -> {
                if (showResult) toastDialog(result.success ? "SYNC VERIFIED" : "SYNC FAILED", result.message);
            });
        }, "victor-sync-now").start();
    }

    private void nodeEditor() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(16), dp(4), dp(16), 0);
        EditText id = input("node-id");
        EditText label = input("Label");
        EditText cluster = input("CLUSTER");
        EditText kind = input("project | system | product | chief");
        EditText attention = input("attention 0-100");
        attention.setInputType(InputType.TYPE_CLASS_NUMBER);
        layout.addView(id); layout.addView(label); layout.addView(cluster); layout.addView(kind); layout.addView(attention);
        new AlertDialog.Builder(this).setTitle("Add / Update Node").setView(layout)
                .setPositiveButton("COMMIT", (d, which) -> {
                    try {
                        JSONObject node = new JSONObject();
                        node.put("id", id.getText().toString().trim());
                        node.put("label", label.getText().toString().trim());
                        node.put("cluster", cluster.getText().toString().trim());
                        node.put("kind", kind.getText().toString().trim());
                        node.put("status", "active");
                        String a = attention.getText().toString().trim();
                        node.put("attention", a.isEmpty() ? 50 : Integer.parseInt(a));
                        node.put("updatedAt", Instant.now().toString());
                        store.upsertNode(node, "owner-mobile");
                    } catch (Exception e) {
                        toastDialog("Rejected", e.getMessage() == null ? "Invalid node" : e.getMessage());
                    }
                }).setNegativeButton("CANCEL", null).show();
    }

    private void nodeDialog(JSONObject node) {
        if (node == null) return;
        toastDialog(node.optString("label"), "ID: " + node.optString("id") + "\nCluster: " + node.optString("cluster") + "\nKind: " + node.optString("kind") + "\nStatus: " + node.optString("status") + "\nAttention: " + node.optInt("attention") + "\nSource: " + node.optString("source"));
    }

    private void nodeById(String id) {
        JSONArray nodes = store.nodes();
        for (int i = 0; i < nodes.length(); i++) {
            JSONObject node = nodes.optJSONObject(i);
            if (node != null && id.equals(node.optString("id"))) {
                nodePanel(node, GREEN);
                return;
            }
        }
    }

    private void nodePanel(JSONObject node, int accent) {
        if (node == null) return;
        addPanel(node.optString("label") + "  [" + node.optInt("attention", 0) + "]", node.optString("cluster") + " · " + node.optString("kind") + " · " + node.optString("status") + "\n" + node.optString("id"), accent);
    }

    private void handleSharedText(Intent intent) {
        if (intent == null || !Intent.ACTION_SEND.equals(intent.getAction())) return;
        CharSequence shared = intent.getCharSequenceExtra(Intent.EXTRA_TEXT);
        if (shared == null) return;
        String text = VictorStore.clean(shared.toString(), 4096);
        if (text.isEmpty()) return;
        try {
            String hash = VictorStore.sha256(text);
            JSONObject node = new JSONObject();
            node.put("id", "inbox-" + hash.substring(0, 12));
            node.put("label", text.length() > 72 ? text.substring(0, 72) + "…" : text);
            node.put("cluster", "INBOX");
            node.put("kind", "inbox");
            node.put("status", "untriaged");
            node.put("attention", 86);
            node.put("updatedAt", Instant.now().toString());
            store.upsertNode(node, "android-share-intent");
            store.append("INGEST", "Shared text captured as " + node.optString("id") + " evidence " + hash.substring(0, 16), "OBSERVED");
        } catch (Exception ignored) {}
    }

    private void shareSnapshot() {
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("application/json");
        send.putExtra(Intent.EXTRA_TEXT, store.exportSnapshot().toString());
        startActivity(Intent.createChooser(send, "Share Victor canonical snapshot"));
    }

    private void metric(String label, String key) {
        int value = store.getMetric(key, 50);
        addPanel(label + "  " + value + "%", progress(value), value > 40 ? GREEN : Color.RED);
    }

    private String progress(int value) {
        int blocks = Math.max(0, Math.min(10, value / 10));
        return "██████████".substring(0, blocks) + "░░░░░░░░░░".substring(0, 10 - blocks);
    }

    private EditText input(String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setHintTextColor(MUTED);
        e.setTextColor(WHITE);
        e.setTextSize(16);
        e.setBackgroundColor(PANEL);
        e.setPadding(dp(14), dp(14), dp(14), dp(14));
        e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        LinearLayout.LayoutParams p = matchWrap();
        p.setMargins(0, dp(4), 0, dp(4));
        e.setLayoutParams(p);
        return e;
    }

    private void addPanel(String heading, String body, int accent) {
        LinearLayout p = new LinearLayout(this);
        p.setOrientation(LinearLayout.VERTICAL);
        p.setPadding(dp(14), dp(14), dp(14), dp(14));
        p.setBackgroundColor(PANEL);
        TextView h = text(heading, 15, accent);
        h.setTypeface(Typeface.DEFAULT_BOLD);
        p.addView(h);
        p.addView(text(body, 13, WHITE));
        LinearLayout.LayoutParams lp = matchWrap();
        lp.setMargins(0, dp(5), 0, dp(7));
        root.addView(p, lp);
    }

    private void addButton(String label, View.OnClickListener action, int color) {
        Button b = button(label, action, color);
        LinearLayout.LayoutParams p = matchWrap();
        p.setMargins(0, dp(6), 0, dp(6));
        root.addView(b, p);
    }

    private Button button(String label, View.OnClickListener action, int color) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextColor(color == PANEL ? WHITE : BG);
        b.setTextSize(13);
        b.setAllCaps(false);
        b.setGravity(Gravity.CENTER);
        b.setBackgroundColor(color);
        b.setMinHeight(dp(48));
        b.setOnClickListener(action);
        return b;
    }

    private TextView text(String value, int size, int color) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(size);
        v.setTextColor(color);
        v.setLineSpacing(0, 1.15f);
        return v;
    }

    private void spacer(int n) {
        View v = new View(this);
        root.addView(v, new LinearLayout.LayoutParams(1, dp(n)));
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(-1, -2);
    }

    private int dp(int n) {
        return (int) (n * getResources().getDisplayMetrics().density);
    }

    private void toastDialog(String title, String message) {
        new AlertDialog.Builder(this).setTitle(title).setMessage(message).setPositiveButton("OK", null).show();
    }
}
