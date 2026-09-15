package ai.ethica.victoros;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Read-only/local-first Empire topology projected above Victor's existing body.
 *
 * This model grants no Android permission, capability lease, network authority,
 * or execution authority. It is deliberately separate from physiology and
 * sensory state so presentation cannot become permission.
 */
public final class EmpireControlPlane {
    public enum Surface {
        NOW, MAP, PROJECTS, REVENUE, MEMORY, EVIDENCE, SYSTEMS, CONTROL
    }

    public static final class Node {
        public final String id;
        public final String label;
        public final String kind;
        public final String cluster;
        public final String status;
        public final int attention;
        public final String updatedAt;

        public Node(String id, String label, String kind, String cluster, String status, int attention, String updatedAt) {
            if (id == null || id.isBlank()) throw new IllegalArgumentException("id required");
            if (label == null || label.isBlank()) throw new IllegalArgumentException("label required");
            if (attention < 0 || attention > 100) throw new IllegalArgumentException("attention must be 0..100");
            this.id = id;
            this.label = label;
            this.kind = kind == null ? "unknown" : kind;
            this.cluster = cluster == null ? "UNCLASSIFIED" : cluster;
            this.status = status == null ? "unknown" : status;
            this.attention = attention;
            this.updatedAt = updatedAt == null ? Instant.EPOCH.toString() : updatedAt;
        }
    }

    public static final class Edge {
        public final String from;
        public final String to;
        public final String relation;

        public Edge(String from, String to, String relation) {
            if (from == null || from.isBlank() || to == null || to.isBlank()) {
                throw new IllegalArgumentException("edge endpoints required");
            }
            this.from = from;
            this.to = to;
            this.relation = relation == null ? "related" : relation;
        }
    }

    private final Map<String, Node> nodes = new LinkedHashMap<>();
    private final List<Edge> edges = new ArrayList<>();

    public EmpireControlPlane() {
        seedManagementTopology();
    }

    private void seedManagementTopology() {
        put(new Node("victor-prime", "Victor Prime", "principal", "CONTROL", "local", 100, Instant.EPOCH.toString()));
        put(new Node("empire-steward", "Empire Steward", "steward", "CONTROL", "local", 95, Instant.EPOCH.toString()));
        put(new Node("truth-chief", "Truth / Continuity", "chief", "EVIDENCE", "local", 90, Instant.EPOCH.toString()));
        put(new Node("execution-chief", "Execution", "chief", "PROJECTS", "local", 90, Instant.EPOCH.toString()));
        put(new Node("governance-chief", "Governance", "chief", "SYSTEMS", "local", 95, Instant.EPOCH.toString()));
        put(new Node("revenue-chief", "Revenue", "chief", "REVENUE", "local", 90, Instant.EPOCH.toString()));
        put(new Node("distribution-chief", "Distribution", "chief", "PROJECTS", "local", 80, Instant.EPOCH.toString()));
        put(new Node("research-chief", "Research", "chief", "MAP", "local", 75, Instant.EPOCH.toString()));
        put(new Node("investigation-chief", "Investigation", "chief", "EVIDENCE", "local", 80, Instant.EPOCH.toString()));

        edges.add(new Edge("victor-prime", "empire-steward", "delegates"));
        for (String id : List.of("truth-chief", "execution-chief", "governance-chief", "revenue-chief", "distribution-chief", "research-chief", "investigation-chief")) {
            edges.add(new Edge("empire-steward", id, "supervises"));
        }
    }

    public void put(Node node) {
        nodes.put(node.id, node);
    }

    public Node get(String id) {
        return nodes.get(id);
    }

    public List<Node> allNodes() {
        return Collections.unmodifiableList(new ArrayList<>(nodes.values()));
    }

    public List<Edge> allEdges() {
        return Collections.unmodifiableList(new ArrayList<>(edges));
    }

    public List<Node> forSurface(Surface surface) {
        String cluster = surface.name();
        List<Node> result = new ArrayList<>();
        for (Node node : nodes.values()) {
            if (cluster.equals(node.cluster)) result.add(node);
        }
        result.sort(Comparator.comparingInt((Node n) -> n.attention).reversed().thenComparing(n -> n.label));
        return Collections.unmodifiableList(result);
    }

    public List<Node> highestAttention(int limit) {
        if (limit < 0) throw new IllegalArgumentException("limit must be non-negative");
        List<Node> result = new ArrayList<>(nodes.values());
        result.sort(Comparator.comparingInt((Node n) -> n.attention).reversed().thenComparing(n -> n.label));
        if (result.size() > limit) result = new ArrayList<>(result.subList(0, limit));
        return Collections.unmodifiableList(result);
    }

    /** Presentation/state only. Never an authority signal. */
    public boolean grantsAuthority() {
        return false;
    }
}
