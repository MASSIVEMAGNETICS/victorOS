package ai.ethica.victoros;

import org.json.JSONArray;
import org.json.JSONObject;

/** Chronos adapter dedicated to verified developmental learning receipts. */
public final class VictorGrowthChronosAdapter implements VictorDevelopmentRuntime.Chronos {
    private final VictorStore store;

    public VictorGrowthChronosAdapter(VictorStore store) {
        if (store == null) throw new IllegalArgumentException("store required");
        this.store = store;
    }

    @Override public boolean verifyIntegrity() { return store.verifyIntegrity(); }

    @Override public String appendVerifiedLearning(String evidenceHash, String stateHash, long verifiedExperiences) {
        if (!verifyIntegrity()) return "CORRUPT";
        String message = "schema=" + VictorDevelopmentRuntime.SCHEMA
                + " evidence=" + evidenceHash
                + " state=" + stateHash
                + " verified_experiences=" + verifiedExperiences
                + " authority=observation_only";
        return store.append("DEVELOPMENT", message, "VERIFIED_LEARNING");
    }

    @Override public boolean containsVerifiedLearning(String evidenceHash, String stateHash) {
        if (!verifyIntegrity()) return false;
        String eNeedle = "evidence=" + evidenceHash;
        String sNeedle = "state=" + stateHash;
        JSONArray events = store.events();
        for (int i = events.length() - 1; i >= 0; i--) {
            JSONObject event = events.optJSONObject(i);
            if (event == null) continue;
            if (!"DEVELOPMENT".equals(event.optString("organ"))) continue;
            if (!"VERIFIED_LEARNING".equals(event.optString("state"))) continue;
            String message = event.optString("message", "");
            if (message.contains(eNeedle) && message.contains(sNeedle)
                    && message.contains("authority=observation_only")) return true;
        }
        return false;
    }
}
