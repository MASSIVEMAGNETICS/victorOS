package ai.ethica.victoros;

import java.util.Objects;

/**
 * Transactional bridge from verified outcomes into persistent developmental state.
 *
 * <p>Growth remains advisory. This runtime never grants capabilities or authority.
 * A candidate state is staged first, Chronos is appended second, and only then is
 * the candidate promoted to committed state. On restart, a staged state is
 * recovered only when a matching Chronos receipt exists; otherwise it is discarded.</p>
 */
public final class VictorDevelopmentRuntime {
    public static final String SCHEMA = "victor.development.v1";

    public interface Persistence {
        String loadCommitted();
        Pending loadPending();
        void stage(String encodedState, String evidenceHash, String stateHash);
        void commitPending(String receiptHash);
        void discardPending();
    }

    public interface Chronos {
        boolean verifyIntegrity();
        String appendVerifiedLearning(String evidenceHash, String stateHash, long verifiedExperiences);
        boolean containsVerifiedLearning(String evidenceHash, String stateHash);
    }

    public static final class Pending {
        public final String encodedState;
        public final String evidenceHash;
        public final String stateHash;

        public Pending(String encodedState, String evidenceHash, String stateHash) {
            this.encodedState = encodedState == null ? "" : encodedState;
            this.evidenceHash = evidenceHash == null ? "" : evidenceHash;
            this.stateHash = stateHash == null ? "" : stateHash;
        }
    }

    private final Persistence persistence;
    private final Chronos chronos;
    private final VictorGrowthEngine engine = new VictorGrowthEngine();

    public VictorDevelopmentRuntime(Persistence persistence, Chronos chronos) {
        this.persistence = Objects.requireNonNull(persistence, "persistence");
        this.chronos = Objects.requireNonNull(chronos, "chronos");
        recover();
        String committed = persistence.loadCommitted();
        if (committed != null && !committed.trim().isEmpty()) engine.importState(committed);
    }

    /** Recover only receipt-backed staged state. Unreceipted state is forgotten. */
    private void recover() {
        Pending pending = persistence.loadPending();
        if (pending == null) return;
        if (chronos.verifyIntegrity()
                && chronos.containsVerifiedLearning(pending.evidenceHash, pending.stateHash)) {
            persistence.commitPending("RECOVERED_FROM_CHRONOS");
        } else {
            persistence.discardPending();
        }
    }

    public synchronized boolean learn(VictorGrowthEngine.ExperienceOutcome outcome) {
        Objects.requireNonNull(outcome, "outcome");
        if (!chronos.verifyIntegrity()) return false;
        if (!outcome.verified || outcome.evidenceHash.isEmpty()) return false;

        VictorGrowthEngine candidate = new VictorGrowthEngine();
        candidate.importState(engine.exportState());
        if (!candidate.learn(outcome)) return false;

        String encoded = candidate.exportState();
        String stateHash = VictorStore.sha256(SCHEMA + "|" + encoded);
        persistence.stage(encoded, outcome.evidenceHash, stateHash);

        try {
            String receipt = chronos.appendVerifiedLearning(
                    outcome.evidenceHash,
                    stateHash,
                    candidate.state().verifiedExperiences());
            if (receipt == null || receipt.isEmpty() || "CORRUPT".equals(receipt)) {
                persistence.discardPending();
                return false;
            }
            persistence.commitPending(receipt);
            engine.importState(encoded);
            return true;
        } catch (RuntimeException failure) {
            persistence.discardPending();
            return false;
        }
    }

    public synchronized VictorGrowthEngine.DevelopmentState state() { return engine.state(); }
    public synchronized String exportState() { return engine.exportState(); }

    /** Explicitly repeats the architectural invariant in the runtime boundary. */
    public boolean grantsAuthority() { return false; }
    public boolean canExpandPermissions() { return false; }
}
