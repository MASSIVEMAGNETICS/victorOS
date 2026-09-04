package ai.ethica.victoros;

import android.content.Context;
import android.content.SharedPreferences;

/** Android persistence adapter for developmental state. */
public final class VictorAndroidDevelopmentStore implements VictorDevelopmentRuntime.Persistence {
    private static final String PREFS = "victor_development_state_v1";
    private static final String COMMITTED = "committed_state";
    private static final String PENDING = "pending_state";
    private static final String PENDING_EVIDENCE = "pending_evidence";
    private static final String PENDING_HASH = "pending_hash";
    private static final String RECEIPT = "commit_receipt";
    private final SharedPreferences prefs;

    public VictorAndroidDevelopmentStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    @Override public synchronized String loadCommitted() {
        return prefs.getString(COMMITTED, "");
    }

    @Override public synchronized VictorDevelopmentRuntime.Pending loadPending() {
        String state = prefs.getString(PENDING, "");
        if (state == null || state.isEmpty()) return null;
        return new VictorDevelopmentRuntime.Pending(
                state,
                prefs.getString(PENDING_EVIDENCE, ""),
                prefs.getString(PENDING_HASH, ""));
    }

    @Override public synchronized void stage(String encodedState, String evidenceHash, String stateHash) {
        boolean ok = prefs.edit()
                .putString(PENDING, encodedState)
                .putString(PENDING_EVIDENCE, evidenceHash)
                .putString(PENDING_HASH, stateHash)
                .commit();
        if (!ok) throw new IllegalStateException("Could not stage developmental state");
    }

    @Override public synchronized void commitPending(String receiptHash) {
        String pending = prefs.getString(PENDING, "");
        if (pending == null || pending.isEmpty()) throw new IllegalStateException("No staged developmental state");
        boolean ok = prefs.edit()
                .putString(COMMITTED, pending)
                .putString(RECEIPT, receiptHash == null ? "" : receiptHash)
                .remove(PENDING)
                .remove(PENDING_EVIDENCE)
                .remove(PENDING_HASH)
                .commit();
        if (!ok) throw new IllegalStateException("Could not commit developmental state");
    }

    @Override public synchronized void discardPending() {
        prefs.edit().remove(PENDING).remove(PENDING_EVIDENCE).remove(PENDING_HASH).commit();
    }

    public synchronized String lastReceipt() { return prefs.getString(RECEIPT, ""); }
}
