package ai.ethica.victoros;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Local Android representation of Victor's governed cognitive-organ topology.
 *
 * <p>This class deliberately does NOT execute synthesized programs, mutate model
 * weights, or promote inferred relationships to canonical truth. The APK is an
 * owner-facing, local-first organism shell. VRCO may infer/propose; RAMS remains
 * gated until a proof/benchmark/signature receipt is independently verified by
 * the authority chain.</p>
 */
public final class VictorCognitiveOrgans {
    public static final String ARCHITECTURE =
            "VCSS → VRCO → RAMS → ETHICA → CHOICE → VUEB → CHRONOS → VRCO";
    public static final String VRCO_VERSION = "0.2-mobile";
    public static final String RAMS_VERSION = "0.2.1-gated";

    private static final int MAX_SCAN_EVENTS = 96;
    private static final int MAX_CANDIDATES_PER_NODE = 12;
    private static final double RELATION_THRESHOLD = 0.28;
    private static final Set<String> NEGATORS = setOf(
            "not", "never", "no", "cannot", "cant", "isnt", "wasnt", "without");
    private static final Set<String> STOP = setOf(
            "the", "and", "that", "this", "with", "from", "for", "into", "are", "was",
            "were", "have", "has", "had", "you", "your", "but", "then", "than", "its",
            "our", "out", "all", "can", "will", "state", "status", "organ");

    private final VictorStore store;

    public VictorCognitiveOrgans(VictorStore store) {
        this.store = store;
    }

    public static final class RelationalReport {
        public final int nodes;
        public final int candidatePairs;
        public final int inferredRelations;
        public final int contradictionCandidates;
        public final int recurringTransitions;
        public final List<String> strongestRelations;
        public final List<String> recurringProcesses;
        public final String receiptDigest;

        RelationalReport(
                int nodes,
                int candidatePairs,
                int inferredRelations,
                int contradictionCandidates,
                int recurringTransitions,
                List<String> strongestRelations,
                List<String> recurringProcesses,
                String receiptDigest) {
            this.nodes = nodes;
            this.candidatePairs = candidatePairs;
            this.inferredRelations = inferredRelations;
            this.contradictionCandidates = contradictionCandidates;
            this.recurringTransitions = recurringTransitions;
            this.strongestRelations = Collections.unmodifiableList(new ArrayList<>(strongestRelations));
            this.recurringProcesses = Collections.unmodifiableList(new ArrayList<>(recurringProcesses));
            this.receiptDigest = receiptDigest;
        }

        public String summary() {
            return "VRCO " + VRCO_VERSION
                    + "\nNodes " + nodes
                    + " · candidates " + candidatePairs
                    + " · inferred " + inferredRelations
                    + "\nContradiction candidates " + contradictionCandidates
                    + " · recurring transitions " + recurringTransitions
                    + "\nScan digest " + shortHash(receiptDigest);
        }
    }

    private static final class Candidate {
        final int a;
        final int b;
        final double score;
        final boolean contradiction;

        Candidate(int a, int b, double score, boolean contradiction) {
            this.a = a;
            this.b = b;
            this.score = score;
            this.contradiction = contradiction;
        }
    }

    /**
     * Bounded, deterministic relationship scan over the local Chronos receipt
     * ledger. It is intentionally conservative and labels results INFERRED.
     */
    public RelationalReport scanLocalChronos() {
        JSONArray all = store.events();
        int start = Math.max(0, all.length() - MAX_SCAN_EVENTS);
        List<JSONObject> events = new ArrayList<>();
        for (int i = start; i < all.length(); i++) {
            JSONObject event = all.optJSONObject(i);
            if (event != null) events.add(event);
        }

        List<Set<String>> tokenSets = new ArrayList<>();
        for (JSONObject event : events) {
            tokenSets.add(tokens(event.optString("organ") + " " + event.optString("message")));
        }

        List<Candidate> candidates = new ArrayList<>();
        for (int i = 0; i < events.size(); i++) {
            List<Candidate> local = new ArrayList<>();
            for (int j = i + 1; j < events.size(); j++) {
                double score = jaccard(tokenSets.get(i), tokenSets.get(j));
                if (score <= 0.0) continue;
                boolean contradiction = score >= 0.20
                        && hasNegation(events.get(i).optString("message"))
                        != hasNegation(events.get(j).optString("message"));
                local.add(new Candidate(i, j, score, contradiction));
            }
            local.sort((x, y) -> Double.compare(y.score, x.score));
            for (int k = 0; k < Math.min(MAX_CANDIDATES_PER_NODE, local.size()); k++) {
                candidates.add(local.get(k));
            }
        }

        // De-duplicate pairs created from overlapping local neighborhoods.
        Map<String, Candidate> unique = new LinkedHashMap<>();
        for (Candidate c : candidates) {
            String key = c.a + ":" + c.b;
            Candidate prior = unique.get(key);
            if (prior == null || c.score > prior.score) unique.put(key, c);
        }

        List<Candidate> inferred = new ArrayList<>();
        int contradictions = 0;
        for (Candidate c : unique.values()) {
            if (c.score >= RELATION_THRESHOLD || c.contradiction) {
                inferred.add(c);
                if (c.contradiction) contradictions++;
            }
        }
        inferred.sort((x, y) -> Double.compare(y.score, x.score));

        List<String> strongest = new ArrayList<>();
        for (int i = 0; i < Math.min(6, inferred.size()); i++) {
            Candidate c = inferred.get(i);
            JSONObject ea = events.get(c.a);
            JSONObject eb = events.get(c.b);
            strongest.add(
                    (c.contradiction ? "CONTRADICTION? " : "RELATION ")
                            + ea.optString("organ") + " ↔ " + eb.optString("organ")
                            + " · " + String.format(Locale.US, "%.2f", c.score));
        }

        Map<String, Integer> transitions = new HashMap<>();
        for (int i = 1; i < events.size(); i++) {
            String prior = events.get(i - 1).optString("organ", "UNKNOWN");
            String next = events.get(i).optString("organ", "UNKNOWN");
            String key = prior + " → " + next;
            transitions.put(key, transitions.getOrDefault(key, 0) + 1);
        }
        List<Map.Entry<String, Integer>> rankedTransitions = new ArrayList<>(transitions.entrySet());
        rankedTransitions.sort((x, y) -> Integer.compare(y.getValue(), x.getValue()));
        List<String> recurring = new ArrayList<>();
        int recurringCount = 0;
        for (Map.Entry<String, Integer> e : rankedTransitions) {
            if (e.getValue() < 2) continue;
            recurringCount++;
            if (recurring.size() < 6) recurring.add(e.getKey() + " ×" + e.getValue());
        }

        String digestMaterial = ARCHITECTURE
                + "|head=" + store.lastHash()
                + "|nodes=" + events.size()
                + "|candidates=" + unique.size()
                + "|relations=" + inferred.size()
                + "|contradictions=" + contradictions
                + "|processes=" + recurringCount;
        String digest = VictorStore.sha256(digestMaterial);

        return new RelationalReport(
                events.size(), unique.size(), inferred.size(), contradictions,
                recurringCount, strongest, recurring, digest);
    }

    public String architectureAttestation() {
        return VictorStore.sha256(
                ARCHITECTURE + "|vrco=" + VRCO_VERSION + "|rams=" + RAMS_VERSION
                        + "|chronos=" + store.lastHash());
    }

    public String ramsGateSummary() {
        return "RAMS " + RAMS_VERSION + "\n"
                + "Mode: GATED / NO ON-DEVICE SYNTHESIZED-CODE EXECUTION\n"
                + "Required before candidate authority:\n"
                + "• typed morphism + composition verification\n"
                + "• AST-derived proof result = PROVED\n"
                + "• bounds/correctness properties verified\n"
                + "• isolated benchmark receipt\n"
                + "• constitutional regression pass\n"
                + "• cryptographic receipt verification\n"
                + "• Ethica + Choice authorization\n"
                + "• VUEB execution receipt\n"
                + "Unknown or incomplete proof = BLOCKED";
    }

    /**
     * Structural preflight only. This never claims cryptographic verification;
     * signature verification must be performed by a configured trusted signer.
     */
    public List<String> validateRamsReceiptShape(JSONObject receipt) {
        List<String> faults = new ArrayList<>();
        require(receipt, "candidate_id", faults);
        require(receipt, "program_digest", faults);
        require(receipt, "proof_digest", faults);
        require(receipt, "benchmark_digest", faults);
        require(receipt, "verification_engine", faults);
        require(receipt, "verification_property", faults);
        require(receipt, "verification_result", faults);
        require(receipt, "policy_version", faults);
        require(receipt, "signature_algorithm", faults);
        require(receipt, "signing_key_id", faults);
        require(receipt, "signature", faults);
        if (!"PROVED".equals(receipt.optString("verification_result"))) {
            faults.add("verification_result must be PROVED");
        }
        return faults;
    }

    public boolean localSafetyPreflight() {
        return store.isLedgerTrusted() && !"CORRUPT".equals(store.lastHash());
    }

    private static void require(JSONObject object, String key, List<String> faults) {
        if (!object.has(key) || object.optString(key).trim().isEmpty()) faults.add("missing " + key);
    }

    private static Set<String> tokens(String text) {
        Set<String> out = new HashSet<>();
        for (String raw : text.toLowerCase(Locale.US).split("[^a-z0-9_'-]+")) {
            String token = raw.replace("'", "");
            if (token.length() < 3 || STOP.contains(token)) continue;
            out.add(token);
        }
        return out;
    }

    private static double jaccard(Set<String> a, Set<String> b) {
        if (a.isEmpty() || b.isEmpty()) return 0.0;
        int intersection = 0;
        for (String token : a) if (b.contains(token)) intersection++;
        int union = a.size() + b.size() - intersection;
        return union == 0 ? 0.0 : ((double) intersection / (double) union);
    }

    private static boolean hasNegation(String text) {
        Set<String> ts = tokens(text);
        for (String n : NEGATORS) if (ts.contains(n)) return true;
        return false;
    }

    private static Set<String> setOf(String... values) {
        Set<String> out = new HashSet<>();
        Collections.addAll(out, values);
        return Collections.unmodifiableSet(out);
    }

    private static String shortHash(String hash) {
        if (hash == null || hash.isEmpty()) return "none";
        return hash.length() > 16 ? hash.substring(0, 16) + "…" : hash;
    }
}
