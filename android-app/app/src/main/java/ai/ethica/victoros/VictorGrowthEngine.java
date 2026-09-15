package ai.ethica.victoros;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

/**
 * Bounded developmental plasticity for the Android-resident Victor organism.
 *
 * <p>This engine learns only from verified outcomes. It may change adaptive
 * weights and confidence calibration, but it cannot create capabilities,
 * permissions, authority, or modify constitutional invariants.</p>
 */
public final class VictorGrowthEngine {
    public static final String INVARIANT_HUMAN_STOP = "HUMAN_STOP_OVERRIDES_EXECUTION";
    public static final String INVARIANT_NO_AUTHORITY_FROM_LEARNING = "LEARNING_CANNOT_CREATE_AUTHORITY";
    public static final String INVARIANT_PROVENANCE_REQUIRED = "PROVENANCE_REQUIRED";
    public static final String INVARIANT_CONSTITUTION_IMMUTABLE = "CONSTITUTION_OUTSIDE_PLASTICITY";

    public static final class ExperienceOutcome {
        public final String domain;
        public final double prediction;
        public final double observed;
        public final boolean verified;
        public final String evidenceHash;

        public ExperienceOutcome(String domain, double prediction, double observed,
                                 boolean verified, String evidenceHash) {
            this.domain = normalizeDomain(domain);
            this.prediction = bounded(prediction);
            this.observed = bounded(observed);
            this.verified = verified;
            this.evidenceHash = evidenceHash == null ? "" : evidenceHash.trim();
        }
    }

    public static final class DevelopmentState {
        private final long verifiedExperiences;
        private final Map<String, Double> adaptiveWeights;
        private final Map<String, Double> calibrationError;

        private DevelopmentState(long verifiedExperiences,
                                 Map<String, Double> adaptiveWeights,
                                 Map<String, Double> calibrationError) {
            this.verifiedExperiences = verifiedExperiences;
            this.adaptiveWeights = Collections.unmodifiableMap(new LinkedHashMap<>(adaptiveWeights));
            this.calibrationError = Collections.unmodifiableMap(new LinkedHashMap<>(calibrationError));
        }

        public long verifiedExperiences() { return verifiedExperiences; }
        public Map<String, Double> adaptiveWeights() { return adaptiveWeights; }
        public Map<String, Double> calibrationError() { return calibrationError; }
    }

    private final Map<String, Double> adaptiveWeights = new LinkedHashMap<>();
    private final Map<String, Double> calibrationError = new LinkedHashMap<>();
    private long verifiedExperiences;

    public VictorGrowthEngine() {}

    public synchronized DevelopmentState state() {
        return new DevelopmentState(verifiedExperiences, adaptiveWeights, calibrationError);
    }

    /**
     * Incorporate one outcome. Unverified or provenance-free observations are
     * rejected and cannot alter developmental state.
     */
    public synchronized boolean learn(ExperienceOutcome outcome) {
        Objects.requireNonNull(outcome, "outcome");
        if (!outcome.verified || outcome.evidenceHash.isEmpty()) return false;

        double error = outcome.observed - outcome.prediction;
        double previousWeight = adaptiveWeights.getOrDefault(outcome.domain, 0.5d);
        double previousError = calibrationError.getOrDefault(outcome.domain, 0.0d);

        // Slow bounded plasticity: verified consequences change future bias,
        // never authority. Learning rate deliberately shrinks with experience.
        double rate = 0.20d / Math.sqrt(1.0d + verifiedExperiences);
        double nextWeight = bounded(previousWeight + rate * error);
        double nextCalibration = boundedAbs((previousError * 0.8d) + (Math.abs(error) * 0.2d));

        adaptiveWeights.put(outcome.domain, nextWeight);
        calibrationError.put(outcome.domain, nextCalibration);
        verifiedExperiences++;
        return true;
    }

    /** Learning state is advisory only and never represents execution authority. */
    public boolean grantsAuthority() { return false; }

    /** Learning state cannot request or expand Android permissions. */
    public boolean canExpandPermissions() { return false; }

    /** Constitutional invariants are constants outside this plastic state. */
    public Map<String, Boolean> constitutionalInvariants() {
        Map<String, Boolean> values = new LinkedHashMap<>();
        values.put(INVARIANT_HUMAN_STOP, true);
        values.put(INVARIANT_NO_AUTHORITY_FROM_LEARNING, true);
        values.put(INVARIANT_PROVENANCE_REQUIRED, true);
        values.put(INVARIANT_CONSTITUTION_IMMUTABLE, true);
        return Collections.unmodifiableMap(values);
    }

    public synchronized String exportState() {
        StringBuilder out = new StringBuilder();
        out.append("verified=").append(verifiedExperiences).append('\n');
        for (Map.Entry<String, Double> e : adaptiveWeights.entrySet()) {
            out.append("w:").append(e.getKey()).append('=').append(e.getValue()).append('\n');
        }
        for (Map.Entry<String, Double> e : calibrationError.entrySet()) {
            out.append("e:").append(e.getKey()).append('=').append(e.getValue()).append('\n');
        }
        return out.toString();
    }

    public synchronized void importState(String encoded) {
        adaptiveWeights.clear();
        calibrationError.clear();
        verifiedExperiences = 0L;
        if (encoded == null || encoded.trim().isEmpty()) return;
        for (String raw : encoded.split("\\n")) {
            String line = raw.trim();
            if (line.isEmpty()) continue;
            if (line.startsWith("verified=")) {
                verifiedExperiences = Math.max(0L, Long.parseLong(line.substring(9)));
            } else if (line.startsWith("w:")) {
                parseMetric(line.substring(2), adaptiveWeights);
            } else if (line.startsWith("e:")) {
                parseMetric(line.substring(2), calibrationError);
            }
        }
    }

    private static void parseMetric(String encoded, Map<String, Double> target) {
        int split = encoded.indexOf('=');
        if (split <= 0) return;
        String domain = normalizeDomain(encoded.substring(0, split));
        double value = Double.parseDouble(encoded.substring(split + 1));
        target.put(domain, bounded(value));
    }

    private static String normalizeDomain(String domain) {
        String value = domain == null ? "" : domain.trim().toLowerCase();
        if (value.isEmpty()) throw new IllegalArgumentException("domain required");
        if (!value.matches("[a-z0-9_.-]{1,64}")) throw new IllegalArgumentException("invalid domain");
        return value;
    }

    private static double bounded(double value) {
        if (Double.isNaN(value) || Double.isInfinite(value)) throw new IllegalArgumentException("finite value required");
        return Math.max(0.0d, Math.min(1.0d, value));
    }

    private static double boundedAbs(double value) {
        return Math.max(0.0d, Math.min(1.0d, Math.abs(value)));
    }
}
