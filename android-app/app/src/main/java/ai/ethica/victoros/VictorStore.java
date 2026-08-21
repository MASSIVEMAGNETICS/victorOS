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

public final class VictorStore {
    private static final String PREFS = "victor_os_state_v1";
    private static final String EVENTS = "events";
    private final SharedPreferences prefs;

    public VictorStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        if (!prefs.contains("born")) {
            prefs.edit().putString("born", Instant.now().toString()).putInt("energy", 82)
                    .putInt("integrity", 100).putInt("focus", 64).apply();
            append("SYSTEM", "VictorOS initialized", "GENESIS");
        }
    }

    public synchronized String append(String organ, String message, String state) {
        try {
            JSONArray events = events();
            JSONObject event = new JSONObject();
            String timestamp = Instant.now().toString();
            String previous = events.length() == 0 ? "GENESIS" : events.getJSONObject(events.length()-1).getString("hash");
            event.put("id", events.length() + 1);
            event.put("timestamp", timestamp);
            event.put("organ", organ);
            event.put("message", message);
            event.put("state", state);
            event.put("previous", previous);
            event.put("hash", sha256(previous + "|" + timestamp + "|" + organ + "|" + message + "|" + state));
            events.put(event);
            prefs.edit().putString(EVENTS, events.toString()).apply();
            return event.getString("hash");
        } catch (JSONException e) { throw new IllegalStateException("Could not append receipt", e); }
    }

    public synchronized JSONArray events() {
        try { return new JSONArray(prefs.getString(EVENTS, "[]")); }
        catch (JSONException e) { return new JSONArray(); }
    }

    public synchronized List<String> verify() {
        List<String> problems = new ArrayList<>();
        JSONArray all = events();
        String previous = "GENESIS";
        for (int i=0; i<all.length(); i++) {
            try {
                JSONObject e = all.getJSONObject(i);
                String expected = sha256(previous + "|" + e.getString("timestamp") + "|" + e.getString("organ") + "|" + e.getString("message") + "|" + e.getString("state"));
                if (!previous.equals(e.optString("previous")) || !expected.equals(e.optString("hash"))) problems.add("Receipt " + (i+1));
                previous = e.getString("hash");
            } catch (JSONException ex) { problems.add("Malformed receipt " + (i+1)); }
        }
        return problems;
    }

    public int getMetric(String key, int fallback) { return prefs.getInt(key, fallback); }
    public void setMetric(String key, int value) { prefs.edit().putInt(key, Math.max(0, Math.min(100, value))).apply(); }
    public String born() { return prefs.getString("born", "unknown"); }

    private static String sha256(String value) {
        try {
            byte[] bytes = MessageDigest.getInstance("SHA-256").digest(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder();
            for (byte b : bytes) out.append(String.format("%02x", b));
            return out.toString();
        } catch (Exception e) { throw new IllegalStateException(e); }
    }
}
