package ai.ethica.victoros;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public final class VictorStore implements VictorPhysiology.ReceiptLedger, VictorPhysiology.StatePersistence {
    private static final String PREFS = "victor_os_state_v1";
    private static final String EVENTS = "events";
    private static final String PHYS = "phys_";
    private static final long SENSOR_RECEIPT_INTERVAL_MS = 10_000L;
    private static final Object LEDGER_LOCK = new Object();
    private static volatile String verifiedHead;
    private final SharedPreferences prefs;

    public VictorStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        if (!prefs.contains("born")) {
            prefs.edit().putString("born", Instant.now().toString()).putInt("energy", 82)
                    .putInt("integrity", 100).putInt("focus", 64).apply();
            append("SYSTEM", "VictorOS initialized", "GENESIS");
        }
    }

    public String append(String organ, String message, String state) {
        synchronized (LEDGER_LOCK) {
            if (!isLedgerTrustedLocked()) throw new IllegalStateException("Receipt ledger is corrupt; mutation refused");
            try {
                JSONArray events = strictEvents();
                JSONObject event = new JSONObject();
                String timestamp = Instant.now().toString();
                String previous = events.length() == 0 ? "GENESIS" : events.getJSONObject(events.length()-1).getString("hash");
                event.put("id", events.length() + 1);
                event.put("timestamp", timestamp);
                event.put("organ", organ);
                event.put("message", message);
                event.put("state", state);
                event.put("previous", previous);
                String hash = sha256(previous + "|" + timestamp + "|" + organ + "|" + message + "|" + state);
                event.put("hash", hash);
                events.put(event);
                if (!prefs.edit().putString(EVENTS, events.toString()).commit()) throw new IllegalStateException("Could not persist receipt");
                verifiedHead = hash;
                return hash;
            } catch (JSONException e) { throw new IllegalStateException("Could not append receipt", e); }
        }
    }

    @Override public String append(String eventType, Map<String, String> payload) {
        synchronized (LEDGER_LOCK) {
            if (!isLedgerTrustedLocked()) return "CORRUPT";
        }
        TreeMap<String,String> sorted = new TreeMap<>(payload);
        return append("PHYSIOLOGY", eventType + " " + new JSONObject(sorted), eventType.toUpperCase());
    }

    private JSONArray strictEvents() {
        try { return new JSONArray(prefs.getString(EVENTS, "[]")); }
        catch (JSONException e) { throw new IllegalStateException("Malformed receipt ledger", e); }
    }

    public JSONArray events() {
        try { return new JSONArray(prefs.getString(EVENTS, "[]")); }
        catch (JSONException e) { return new JSONArray(); }
    }

    public List<String> verify() {
        synchronized (LEDGER_LOCK) { return verifyLocked(); }
    }

    private List<String> verifyLocked() {
        List<String> problems = new ArrayList<>();
        JSONArray all;
        try { all = new JSONArray(prefs.getString(EVENTS, "[]")); }
        catch (JSONException malformed) { problems.add("Malformed event ledger"); verifiedHead=null; return problems; }
        String previous = "GENESIS";
        for (int i=0; i<all.length(); i++) {
            try {
                JSONObject e = all.getJSONObject(i);
                String expected = sha256(previous + "|" + e.getString("timestamp") + "|" + e.getString("organ") + "|" + e.getString("message") + "|" + e.getString("state"));
                if (!previous.equals(e.optString("previous")) || !expected.equals(e.optString("hash"))) problems.add("Receipt " + (i+1));
                previous = e.getString("hash");
            } catch (JSONException ex) { problems.add("Malformed receipt " + (i+1)); }
        }
        verifiedHead = problems.isEmpty() ? previous : null;
        return problems;
    }

    @Override public boolean verifyIntegrity() {
        synchronized (LEDGER_LOCK) { return verifyLocked().isEmpty(); }
    }

    public boolean isLedgerTrusted() {
        synchronized (LEDGER_LOCK) { return isLedgerTrustedLocked(); }
    }

    private boolean isLedgerTrustedLocked() {
        String current = lastHashUnlocked();
        if ("CORRUPT".equals(current)) { verifiedHead=null; return false; }
        if (verifiedHead != null && verifiedHead.equals(current)) return true;
        return verifyLocked().isEmpty();
    }

    @Override public String lastHash() {
        synchronized (LEDGER_LOCK) { return lastHashUnlocked(); }
    }

    private String lastHashUnlocked() {
        try {
            JSONArray all = new JSONArray(prefs.getString(EVENTS, "[]"));
            return all.length() == 0 ? "GENESIS" : all.getJSONObject(all.length()-1).getString("hash");
        } catch (JSONException e) { return "CORRUPT"; }
    }

    @Override public synchronized VictorPhysiology.State load() {
        VictorPhysiology.State s = new VictorPhysiology.State();
        if (!prefs.contains(PHYS + "initialized")) return s;
        s.identityIntegrity = getDouble(PHYS+"identity",1.0);
        s.continuityIntegrity = getDouble(PHYS+"continuity",1.0);
        s.epistemicConfidence = getDouble(PHYS+"confidence",1.0);
        s.resourcePressure = getDouble(PHYS+"resource",0.0);
        s.authorityConflict = getDouble(PHYS+"authority_conflict",0.0);
        s.memoryConflict = getDouble(PHYS+"memory_conflict",0.0);
        s.securityPressure = getDouble(PHYS+"security",0.0);
        s.humanStop = prefs.getBoolean(PHYS+"human_stop",false);
        try { s.governanceMode = VictorPhysiology.GovernanceMode.valueOf(prefs.getString(PHYS+"mode","GREEN")); }
        catch (Exception ignored) { s.governanceMode = VictorPhysiology.GovernanceMode.BLACK; }
        s.physiologyReceiptHead = prefs.getString(PHYS+"head","GENESIS");
        s.activeLeases = prefs.getInt(PHYS+"active_leases",0);
        s.revokedLeases = prefs.getInt(PHYS+"revoked_leases",0);
        s.immuneAlerts = prefs.getInt(PHYS+"immune_alerts",0);
        s.unresolvedAuthorityConflicts = prefs.getInt(PHYS+"authority_unresolved",0);
        s.updatedAt = prefs.getString(PHYS+"updated",Instant.now().toString());
        return s;
    }

    @Override public synchronized void save(VictorPhysiology.State s) {
        SharedPreferences.Editor e = prefs.edit();
        e.putBoolean(PHYS+"initialized",true);
        putDouble(e,PHYS+"identity",s.identityIntegrity); putDouble(e,PHYS+"continuity",s.continuityIntegrity);
        putDouble(e,PHYS+"confidence",s.epistemicConfidence); putDouble(e,PHYS+"resource",s.resourcePressure);
        putDouble(e,PHYS+"authority_conflict",s.authorityConflict); putDouble(e,PHYS+"memory_conflict",s.memoryConflict);
        putDouble(e,PHYS+"security",s.securityPressure); e.putBoolean(PHYS+"human_stop",s.humanStop);
        e.putString(PHYS+"mode",s.governanceMode.name()); e.putString(PHYS+"head",s.physiologyReceiptHead);
        e.putInt(PHYS+"active_leases",s.activeLeases); e.putInt(PHYS+"revoked_leases",s.revokedLeases);
        e.putInt(PHYS+"immune_alerts",s.immuneAlerts); e.putInt(PHYS+"authority_unresolved",s.unresolvedAuthorityConflicts);
        e.putString(PHYS+"updated",s.updatedAt); e.commit();
    }

    public void recordGodsEyeMetadata(String source, String hash, int bytes, String summary) {
        if (!isLedgerTrusted()) return;
        String safeSummary = summary == null ? "" : summary.replace('\n',' ').replace('\r',' ');
        if (safeSummary.length() > 180) safeSummary = safeSummary.substring(0,180);
        String metadata = source + " | " + hash + " | " + bytes + " bytes | " + safeSummary;
        String throttleKey = "gods_eye_receipt_ms_" + source.replaceAll("[^A-Za-z0-9_]","_");
        long now = System.currentTimeMillis();
        long prior = prefs.getLong(throttleKey, 0L);
        prefs.edit().putString("gods_eye_last", metadata).apply();
        if (now - prior >= SENSOR_RECEIPT_INTERVAL_MS) {
            append("GODS_EYE", source + " hash=" + hash + " bytes=" + bytes, "OBSERVED");
            prefs.edit().putLong(throttleKey, now).apply();
        }
    }

    public String latestGodsEyeMetadata() { return prefs.getString("gods_eye_last","No observations yet"); }
    public int getMetric(String key, int fallback) { return prefs.getInt(key, fallback); }
    public void setMetric(String key, int value) { prefs.edit().putInt(key, Math.max(0, Math.min(100, value))).apply(); }
    public String born() { return prefs.getString("born", "unknown"); }

    private double getDouble(String key,double fallback){ try{return Double.parseDouble(prefs.getString(key,Double.toString(fallback)));}catch(Exception e){return fallback;} }
    private static void putDouble(SharedPreferences.Editor e,String key,double value){e.putString(key,Double.toString(value));}
    static String sha256(String value) { return sha256(value.getBytes(java.nio.charset.StandardCharsets.UTF_8)); }
    static String sha256(byte[] bytes) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder out = new StringBuilder();
            for (byte b : digest) out.append(String.format("%02x", b));
            return out.toString();
        } catch (Exception e) { throw new IllegalStateException(e); }
    }
}
