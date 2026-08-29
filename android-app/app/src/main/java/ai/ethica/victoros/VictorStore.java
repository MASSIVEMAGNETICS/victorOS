package ai.ethica.victoros;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

public final class VictorStore {
    private static final String PREFS = "victor_os_state_v1";
    private static final String EVENTS = "events";
    private static final String NODES = "empire_nodes_v2";
    private static final String EDGES = "empire_edges_v2";
    private static final int MAX_REMOTE_NODES = 5000;
    private static final int MAX_REMOTE_EDGES = 20000;
    private final SharedPreferences prefs;

    public VictorStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        if (!prefs.contains("born")) {
            prefs.edit().putString("born", Instant.now().toString()).putInt("energy", 82)
                    .putInt("integrity", 100).putInt("focus", 64).apply();
            append("SYSTEM", "VictorOS initialized", "GENESIS");
        }
        if (!prefs.contains("device_id")) {
            prefs.edit().putString("device_id", UUID.randomUUID().toString()).apply();
        }
        if (!prefs.getBoolean("empire_seeded_v2", false)) seedEmpireGraph();
    }

    public synchronized String append(String organ, String message, String state) {
        try {
            JSONArray events = events();
            JSONObject event = new JSONObject();
            String timestamp = Instant.now().toString();
            String previous = events.length() == 0 ? "GENESIS" : events.getJSONObject(events.length() - 1).getString("hash");
            event.put("id", events.length() + 1);
            event.put("timestamp", timestamp);
            event.put("organ", clean(organ, 48));
            event.put("message", clean(message, 4096));
            event.put("state", clean(state, 48));
            event.put("previous", previous);
            event.put("hash", sha256(previous + "|" + timestamp + "|" + event.getString("organ") + "|" + event.getString("message") + "|" + event.getString("state")));
            events.put(event);
            prefs.edit().putString(EVENTS, events.toString()).apply();
            return event.getString("hash");
        } catch (JSONException e) {
            throw new IllegalStateException("Could not append receipt", e);
        }
    }

    public synchronized JSONArray events() {
        return parseArray(prefs.getString(EVENTS, "[]"));
    }

    public synchronized JSONArray eventsAfter(int id) {
        JSONArray out = new JSONArray();
        JSONArray all = events();
        for (int i = 0; i < all.length(); i++) {
            JSONObject event = all.optJSONObject(i);
            if (event != null && event.optInt("id", 0) > id) out.put(event);
        }
        return out;
    }

    public synchronized List<String> verify() {
        List<String> problems = new ArrayList<>();
        JSONArray all = events();
        String previous = "GENESIS";
        for (int i = 0; i < all.length(); i++) {
            try {
                JSONObject e = all.getJSONObject(i);
                String expected = sha256(previous + "|" + e.getString("timestamp") + "|" + e.getString("organ") + "|" + e.getString("message") + "|" + e.getString("state"));
                if (!previous.equals(e.optString("previous")) || !expected.equals(e.optString("hash"))) {
                    problems.add("Receipt " + (i + 1));
                }
                previous = e.getString("hash");
            } catch (JSONException ex) {
                problems.add("Malformed receipt " + (i + 1));
            }
        }
        return problems;
    }

    public synchronized JSONArray nodes() {
        return parseArray(prefs.getString(NODES, "[]"));
    }

    public synchronized JSONArray edges() {
        return parseArray(prefs.getString(EDGES, "[]"));
    }

    public synchronized JSONArray attentionNodes(int limit) {
        JSONArray source = nodes();
        List<JSONObject> sorted = new ArrayList<>();
        for (int i = 0; i < source.length(); i++) {
            JSONObject node = source.optJSONObject(i);
            if (node != null && !"archived".equalsIgnoreCase(node.optString("status"))) sorted.add(node);
        }
        sorted.sort((a, b) -> Integer.compare(b.optInt("attention", 0), a.optInt("attention", 0)));
        JSONArray out = new JSONArray();
        for (int i = 0; i < Math.min(Math.max(0, limit), sorted.size()); i++) out.put(sorted.get(i));
        return out;
    }

    public synchronized void upsertNode(JSONObject input, String source) {
        JSONObject normalized = normalizeNode(input, source);
        JSONArray current = nodes();
        JSONArray next = new JSONArray();
        boolean replaced = false;
        for (int i = 0; i < current.length(); i++) {
            JSONObject node = current.optJSONObject(i);
            if (node == null) continue;
            if (normalized.optString("id").equals(node.optString("id"))) {
                next.put(normalized);
                replaced = true;
            } else next.put(node);
        }
        if (!replaced) next.put(normalized);
        prefs.edit().putString(NODES, next.toString()).apply();
        append("GRAPH", (replaced ? "Updated node " : "Created node ") + normalized.optString("id"), "CANONICAL_LOCAL");
    }

    public synchronized JSONObject exportSnapshot() {
        JSONObject out = new JSONObject();
        try {
            out.put("schema", "victor-empire-snapshot/v1");
            out.put("deviceId", deviceId());
            out.put("generatedAt", Instant.now().toString());
            out.put("revision", getLastRemoteRevision());
            out.put("nodes", nodes());
            out.put("edges", edges());
            out.put("events", events());
            out.put("chainVerified", verify().isEmpty());
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        return out;
    }

    public synchronized JSONObject buildSyncPayload() {
        JSONObject out = new JSONObject();
        try {
            out.put("schema", "victor-mobile-sync/v1");
            out.put("deviceId", deviceId());
            out.put("sentAt", Instant.now().toString());
            out.put("lastRemoteRevision", getLastRemoteRevision());
            out.put("events", eventsAfter(getLastAckedLocalId()));
            out.put("localHead", events().length() == 0 ? "GENESIS" : events().optJSONObject(events().length() - 1).optString("hash"));
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        return out;
    }

    public synchronized void applySyncResponse(JSONObject response) throws JSONException {
        if (response == null) throw new JSONException("Missing response");
        String revision = clean(response.optString("revision", ""), 256);
        int ackedThrough = response.optInt("ackedThrough", getLastAckedLocalId());
        JSONArray remoteNodes = response.optJSONArray("nodes");
        JSONArray remoteEdges = response.optJSONArray("edges");

        if (remoteNodes != null || remoteEdges != null) {
            if (revision.isEmpty()) throw new JSONException("Remote graph requires revision");
            JSONArray validatedNodes = remoteNodes == null ? nodes() : validateNodes(remoteNodes);
            JSONArray validatedEdges = remoteEdges == null ? edges() : validateEdges(remoteEdges, validatedNodes);
            String evidenceHash = sha256(revision + "|" + validatedNodes.toString() + "|" + validatedEdges.toString());
            prefs.edit()
                    .putString(NODES, validatedNodes.toString())
                    .putString(EDGES, validatedEdges.toString())
                    .putString("last_remote_revision", revision)
                    .putString("last_sync_at", Instant.now().toString())
                    .putString("last_sync_error", "")
                    .putInt("last_acked_local_id", Math.max(getLastAckedLocalId(), ackedThrough))
                    .apply();
            append("SYNC", "Applied remote revision " + revision + " evidence " + evidenceHash.substring(0, 16), "VERIFIED_IMPORT");
        } else {
            prefs.edit()
                    .putString("last_sync_at", Instant.now().toString())
                    .putString("last_sync_error", "")
                    .putInt("last_acked_local_id", Math.max(getLastAckedLocalId(), ackedThrough))
                    .apply();
            if (!revision.isEmpty()) prefs.edit().putString("last_remote_revision", revision).apply();
            append("SYNC", "Remote sync acknowledged through local event " + ackedThrough, "VERIFIED_ACK");
        }
    }

    public synchronized void recordSyncFailure(String message) {
        prefs.edit().putString("last_sync_error", clean(message, 512)).apply();
    }

    public int getMetric(String key, int fallback) {
        return prefs.getInt(key, fallback);
    }

    public void setMetric(String key, int value) {
        prefs.edit().putInt(key, Math.max(0, Math.min(100, value))).apply();
    }

    public String born() {
        return prefs.getString("born", "unknown");
    }

    public String deviceId() {
        return prefs.getString("device_id", "unknown");
    }

    public boolean isSyncEnabled() {
        return prefs.getBoolean("sync_enabled", false);
    }

    public void setSyncEnabled(boolean enabled) {
        prefs.edit().putBoolean("sync_enabled", enabled).apply();
        append("CONTROL", "Automatic sync " + (enabled ? "enabled" : "disabled"), "OWNER_SETTING");
    }

    public String getSyncEndpoint() {
        return prefs.getString("sync_endpoint", "");
    }

    public void setSyncEndpoint(String endpoint) {
        prefs.edit().putString("sync_endpoint", clean(endpoint, 1024)).apply();
    }

    public String getLastSyncAt() {
        return prefs.getString("last_sync_at", "never");
    }

    public String getLastSyncError() {
        return prefs.getString("last_sync_error", "");
    }

    public String getLastRemoteRevision() {
        return prefs.getString("last_remote_revision", "none");
    }

    public int getLastAckedLocalId() {
        return prefs.getInt("last_acked_local_id", 0);
    }

    private void seedEmpireGraph() {
        JSONArray nodes = new JSONArray();
        JSONArray edges = new JSONArray();
        try {
            addSeedNode(nodes, "victor-prime", "VICTOR PRIME", "CORE", "meta_orchestrator", 100);
            addSeedNode(nodes, "empire-steward", "Empire Steward", "CORE", "portfolio_orchestrator", 98);
            addSeedNode(nodes, "truth-chief", "Truth + Continuity Chief", "TRUTH", "chief", 93);
            addSeedNode(nodes, "execution-chief", "Execution Chief", "EXECUTION", "chief", 94);
            addSeedNode(nodes, "governance-chief", "Governance Chief", "GOVERNANCE", "chief", 95);
            addSeedNode(nodes, "revenue-chief", "Revenue Chief", "REVENUE", "chief", 96);
            addSeedNode(nodes, "distribution-chief", "Distribution Chief", "DISTRIBUTION", "chief", 92);
            addSeedNode(nodes, "research-chief", "Research Chief", "RESEARCH", "chief", 91);
            addSeedNode(nodes, "investigation-chief", "Investigation Chief", "INVESTIGATION", "chief", 88);
            addSeedNode(nodes, "victoros", "VictorOS", "SYSTEMS", "system", 99);
            addSeedNode(nodes, "chronos", "Chronos", "TRUTH", "organ", 99);
            addSeedNode(nodes, "gev", "God's Eye View", "SYSTEMS", "control_plane", 99);
            addSeedNode(nodes, "ethica", "Ethica Governor", "GOVERNANCE", "organ", 99);
            addSeedNode(nodes, "truth-compiler", "Truth Compiler", "TRUTH", "product", 90);
            addSeedNode(nodes, "massive-magnetics", "Massive Magnetics", "REVENUE", "business", 94);
            addSeedNode(nodes, "b-heard", "B Heard Network", "DISTRIBUTION", "business", 97);
            addSeedNode(nodes, "iambandobandz", "iambandobandz", "DISTRIBUTION", "brand", 95);
            addSeedNode(nodes, "creator-promotion", "Creator Promotion Loop", "REVENUE", "project", 100);
            addSeedNode(nodes, "youtube-topic", "YouTube Topic Release Player", "DISTRIBUTION", "project", 97);
            addSeedNode(nodes, "b-heard-tv", "B Heard TV", "DISTRIBUTION", "project", 75);
            addSeedNode(nodes, "nzt", "NZT", "RESEARCH", "research_layer", 80);
            addSeedNode(nodes, "cyberpi", "CyberPI", "INVESTIGATION", "product", 82);

            addSeedEdge(edges, "victor-prime", "empire-steward", "delegates");
            addSeedEdge(edges, "empire-steward", "truth-chief", "supervises");
            addSeedEdge(edges, "empire-steward", "execution-chief", "supervises");
            addSeedEdge(edges, "empire-steward", "governance-chief", "supervises");
            addSeedEdge(edges, "empire-steward", "revenue-chief", "supervises");
            addSeedEdge(edges, "empire-steward", "distribution-chief", "supervises");
            addSeedEdge(edges, "empire-steward", "research-chief", "supervises");
            addSeedEdge(edges, "empire-steward", "investigation-chief", "supervises");
            addSeedEdge(edges, "truth-chief", "chronos", "owns");
            addSeedEdge(edges, "truth-chief", "truth-compiler", "owns");
            addSeedEdge(edges, "governance-chief", "ethica", "owns");
            addSeedEdge(edges, "execution-chief", "victoros", "operates");
            addSeedEdge(edges, "victoros", "gev", "projects_state_to");
            addSeedEdge(edges, "revenue-chief", "massive-magnetics", "supervises");
            addSeedEdge(edges, "revenue-chief", "creator-promotion", "prioritizes");
            addSeedEdge(edges, "distribution-chief", "b-heard", "supervises");
            addSeedEdge(edges, "distribution-chief", "iambandobandz", "supervises");
            addSeedEdge(edges, "distribution-chief", "youtube-topic", "prioritizes");
            addSeedEdge(edges, "distribution-chief", "b-heard-tv", "deferred_owns");
            addSeedEdge(edges, "research-chief", "nzt", "supervises");
            addSeedEdge(edges, "investigation-chief", "cyberpi", "supervises");
            addSeedEdge(edges, "chronos", "gev", "feeds");
            addSeedEdge(edges, "ethica", "victor-prime", "governs");

            prefs.edit().putString(NODES, nodes.toString()).putString(EDGES, edges.toString())
                    .putBoolean("empire_seeded_v2", true).apply();
            append("GEV", "Empire control graph v2 seeded with " + nodes.length() + " nodes and " + edges.length() + " typed edges", "CANONICAL_LOCAL");
        } catch (JSONException e) {
            throw new IllegalStateException("Could not seed empire graph", e);
        }
    }

    private static void addSeedNode(JSONArray nodes, String id, String label, String cluster, String kind, int attention) throws JSONException {
        JSONObject node = new JSONObject();
        node.put("id", id);
        node.put("label", label);
        node.put("cluster", cluster);
        node.put("kind", kind);
        node.put("status", "active");
        node.put("attention", attention);
        node.put("updatedAt", Instant.now().toString());
        node.put("source", "mobile-seed-v0.2");
        nodes.put(node);
    }

    private static void addSeedEdge(JSONArray edges, String from, String to, String relation) throws JSONException {
        JSONObject edge = new JSONObject();
        edge.put("from", from);
        edge.put("to", to);
        edge.put("relation", relation);
        edge.put("source", "mobile-seed-v0.2");
        edges.put(edge);
    }

    private static JSONObject normalizeNode(JSONObject input, String source) {
        try {
            JSONObject node = new JSONObject();
            String id = clean(input.optString("id", ""), 128);
            String label = clean(input.optString("label", ""), 256);
            if (id.isEmpty() || label.isEmpty()) throw new IllegalArgumentException("Node requires id and label");
            node.put("id", id);
            node.put("label", label);
            node.put("cluster", clean(input.optString("cluster", "UNSORTED"), 64).toUpperCase());
            node.put("kind", clean(input.optString("kind", "node"), 64));
            node.put("status", clean(input.optString("status", "active"), 32));
            node.put("attention", Math.max(0, Math.min(100, input.optInt("attention", 50))));
            node.put("updatedAt", clean(input.optString("updatedAt", Instant.now().toString()), 64));
            node.put("source", clean(source, 128));
            return node;
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
    }

    private static JSONArray validateNodes(JSONArray input) throws JSONException {
        if (input.length() > MAX_REMOTE_NODES) throw new JSONException("Too many remote nodes");
        JSONArray out = new JSONArray();
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < input.length(); i++) {
            JSONObject raw = input.optJSONObject(i);
            if (raw == null) throw new JSONException("Node " + i + " is not an object");
            JSONObject node = normalizeNode(raw, "remote-canonical");
            String id = node.optString("id");
            if (!ids.add(id)) throw new JSONException("Duplicate node id " + id);
            out.put(node);
        }
        return out;
    }

    private static JSONArray validateEdges(JSONArray input, JSONArray nodes) throws JSONException {
        if (input.length() > MAX_REMOTE_EDGES) throw new JSONException("Too many remote edges");
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < nodes.length(); i++) {
            JSONObject node = nodes.optJSONObject(i);
            if (node != null) ids.add(node.optString("id"));
        }
        JSONArray out = new JSONArray();
        for (int i = 0; i < input.length(); i++) {
            JSONObject raw = input.optJSONObject(i);
            if (raw == null) throw new JSONException("Edge " + i + " is not an object");
            String from = clean(raw.optString("from", ""), 128);
            String to = clean(raw.optString("to", ""), 128);
            String relation = clean(raw.optString("relation", "related_to"), 64);
            if (!ids.contains(from) || !ids.contains(to)) throw new JSONException("Edge references unknown node");
            JSONObject edge = new JSONObject();
            edge.put("from", from);
            edge.put("to", to);
            edge.put("relation", relation);
            edge.put("source", "remote-canonical");
            out.put(edge);
        }
        return out;
    }

    private static JSONArray parseArray(String raw) {
        try {
            return new JSONArray(raw == null ? "[]" : raw);
        } catch (JSONException e) {
            return new JSONArray();
        }
    }

    static String sha256(String value) {
        try {
            byte[] bytes = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder();
            for (byte b : bytes) out.append(String.format("%02x", b));
            return out.toString();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    static String clean(String value, int max) {
        if (value == null) return "";
        String out = value.replace('\u0000', ' ').trim();
        return out.length() <= max ? out : out.substring(0, max);
    }
}
