package ai.ethica.victoros;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Local multimodal perception-fusion organ for God's Eye View.
 *
 * This class performs deterministic, offline correlation only. It does not
 * claim object recognition, speech transcription, or latent-model semantics.
 * It fuses the signals Victor actually has: active UI structure/text, recent
 * app context, screen/camera presence, microphone activity, source recency and
 * cross-modal agreement into one bounded perceptual frame.
 */
public final class VictorPerceptionFusion {
    public enum AudioState { UNKNOWN, QUIET, ACTIVE, LOUD }

    public static final class Signal {
        public final String source;
        public final String summary;
        public final String text;
        public final String contentHash;
        public final int byteCount;
        public final long observedAtMs;

        Signal(String source, String summary, String text, String contentHash, int byteCount, long observedAtMs) {
            this.source = safe(source);
            this.summary = safe(summary);
            this.text = text == null ? "" : text;
            this.contentHash = safe(contentHash);
            this.byteCount = Math.max(0, byteCount);
            this.observedAtMs = observedAtMs;
        }
    }

    public static final class PerceptualFrame {
        public final String createdAt;
        public final String activePackage;
        public final List<String> modalities;
        public final List<String> entities;
        public final List<String> conflicts;
        public final AudioState audioState;
        public final double confidence;
        public final double attention;
        public final boolean screenPresent;
        public final boolean cameraPresent;
        public final boolean activeUiPresent;
        public final boolean appContextPresent;

        PerceptualFrame(String activePackage, List<String> modalities, List<String> entities,
                        List<String> conflicts, AudioState audioState, double confidence,
                        double attention, boolean screenPresent, boolean cameraPresent,
                        boolean activeUiPresent, boolean appContextPresent) {
            this.createdAt = Instant.now().toString();
            this.activePackage = activePackage;
            this.modalities = Collections.unmodifiableList(new ArrayList<>(modalities));
            this.entities = Collections.unmodifiableList(new ArrayList<>(entities));
            this.conflicts = Collections.unmodifiableList(new ArrayList<>(conflicts));
            this.audioState = audioState;
            this.confidence = clamp01(confidence);
            this.attention = clamp01(attention);
            this.screenPresent = screenPresent;
            this.cameraPresent = cameraPresent;
            this.activeUiPresent = activeUiPresent;
            this.appContextPresent = appContextPresent;
        }

        public String summary() {
            StringBuilder out = new StringBuilder();
            out.append("FUSED WORLD STATE\n");
            out.append("Active app: ").append(activePackage.isEmpty() ? "unknown" : activePackage).append('\n');
            out.append("Modalities: ").append(modalities.isEmpty() ? "none" : String.join(", ", modalities)).append('\n');
            out.append("Audio: ").append(audioState).append("  •  Confidence ")
                    .append(String.format(Locale.US, "%.2f", confidence)).append("  •  Attention ")
                    .append(String.format(Locale.US, "%.2f", attention));
            if (!entities.isEmpty()) out.append("\nEntities: ").append(String.join(" | ", entities));
            if (!conflicts.isEmpty()) out.append("\nConflicts: ").append(String.join(" | ", conflicts));
            return out.toString();
        }
    }

    private static final long DEFAULT_WINDOW_MS = 5_000L;
    private static final int MAX_ENTITIES = 12;
    private static final int MAX_ENTITY_CHARS = 72;
    private static final Pattern UI_PACKAGE = Pattern.compile("(?m)^package=([^\\s]+)");
    private static final Pattern APP_FOREGROUND = Pattern.compile("(?m)^recentForeground=([^\\s]+)");
    private static final Pattern UI_ENTITY = Pattern.compile("(?:text|desc)=([^\\n]+)");
    private static final Pattern RMS = Pattern.compile("rms=([0-9]*\\.?[0-9]+)");

    private final Map<String, Signal> latest = new LinkedHashMap<>();
    private final long fusionWindowMs;

    public VictorPerceptionFusion() { this(DEFAULT_WINDOW_MS); }

    VictorPerceptionFusion(long fusionWindowMs) {
        this.fusionWindowMs = Math.max(250L, fusionWindowMs);
    }

    public synchronized PerceptualFrame ingestText(String source, String text, String summary,
                                                    String contentHash, int byteCount) {
        return ingest(new Signal(source, summary, text, contentHash, byteCount, System.currentTimeMillis()),
                System.currentTimeMillis());
    }

    public synchronized PerceptualFrame ingestBinary(String source, String summary,
                                                      String contentHash, int byteCount) {
        return ingest(new Signal(source, summary, "", contentHash, byteCount, System.currentTimeMillis()),
                System.currentTimeMillis());
    }

    synchronized PerceptualFrame ingestAt(String source, String text, String summary,
                                          String contentHash, int byteCount, long observedAtMs,
                                          long nowMs) {
        return ingest(new Signal(source, summary, text, contentHash, byteCount, observedAtMs), nowMs);
    }

    private PerceptualFrame ingest(Signal signal, long nowMs) {
        latest.put(signal.source, signal);
        return buildFrame(nowMs);
    }

    public synchronized PerceptualFrame currentFrame() {
        return buildFrame(System.currentTimeMillis());
    }

    synchronized PerceptualFrame currentFrameAt(long nowMs) {
        return buildFrame(nowMs);
    }

    public synchronized void clear() { latest.clear(); }

    private PerceptualFrame buildFrame(long nowMs) {
        Map<String, Signal> live = new LinkedHashMap<>();
        for (Map.Entry<String, Signal> e : latest.entrySet()) {
            Signal s = e.getValue();
            if (nowMs >= s.observedAtMs && nowMs - s.observedAtMs <= fusionWindowMs) live.put(e.getKey(), s);
        }

        boolean screen = live.containsKey("SCREEN");
        boolean camera = live.containsKey("CAMERA");
        boolean mic = live.containsKey("MIC");
        boolean ui = live.containsKey("ACTIVE_UI");
        boolean app = live.containsKey("APP_CONTEXT");

        List<String> modalities = new ArrayList<>();
        if (screen) modalities.add("SCREEN");
        if (camera) modalities.add("CAMERA");
        if (mic) modalities.add("MIC");
        if (ui) modalities.add("ACTIVE_UI");
        if (app) modalities.add("APP_CONTEXT");

        String uiPkg = ui ? extract(UI_PACKAGE, live.get("ACTIVE_UI").text) : "";
        String appPkg = app ? extract(APP_FOREGROUND, live.get("APP_CONTEXT").text) : "";
        String activePackage = !uiPkg.isEmpty() ? uiPkg : appPkg;
        List<String> conflicts = new ArrayList<>();
        if (!uiPkg.isEmpty() && !appPkg.isEmpty() && !uiPkg.equals(appPkg)) {
            conflicts.add("active_app_disagreement:" + uiPkg + "!=" + appPkg);
        }

        Set<String> entitySet = new LinkedHashSet<>();
        if (ui) collectUiEntities(live.get("ACTIVE_UI").text, entitySet);
        List<String> entities = new ArrayList<>(entitySet);
        if (entities.size() > MAX_ENTITIES) entities = new ArrayList<>(entities.subList(0, MAX_ENTITIES));

        AudioState audioState = audioState(mic ? live.get("MIC").summary : "");
        int modalityCount = modalities.size();
        double confidence = modalityCount * 0.12;
        if (ui) confidence += 0.20;
        if (app) confidence += 0.14;
        if (screen) confidence += 0.10;
        if (camera) confidence += 0.05;
        if (mic) confidence += 0.05;
        if (!uiPkg.isEmpty() && uiPkg.equals(appPkg)) confidence += 0.18;
        confidence -= conflicts.size() * 0.18;

        double attention = 0.10;
        if (ui && !entities.isEmpty()) attention += 0.24;
        if (screen) attention += 0.10;
        if (camera) attention += 0.08;
        if (audioState == AudioState.ACTIVE) attention += 0.22;
        if (audioState == AudioState.LOUD) attention += 0.35;
        if (!conflicts.isEmpty()) attention += 0.18;

        return new PerceptualFrame(activePackage, modalities, entities, conflicts, audioState,
                confidence, attention, screen, camera, ui, app);
    }

    private static AudioState audioState(String summary) {
        String raw = extract(RMS, summary);
        if (raw.isEmpty()) return AudioState.UNKNOWN;
        try {
            double rms = Double.parseDouble(raw);
            if (rms < 0.015) return AudioState.QUIET;
            if (rms < 0.18) return AudioState.ACTIVE;
            return AudioState.LOUD;
        } catch (NumberFormatException ignored) {
            return AudioState.UNKNOWN;
        }
    }

    private static void collectUiEntities(String text, Set<String> out) {
        Matcher m = UI_ENTITY.matcher(text == null ? "" : text);
        while (m.find() && out.size() < MAX_ENTITIES) {
            String value = sanitizeEntity(m.group(1));
            if (!value.isEmpty() && !value.contains("[REDACTED_PASSWORD]")) out.add(value);
        }
    }

    private static String sanitizeEntity(String raw) {
        if (raw == null) return "";
        String s = raw.replace('\r', ' ').replace('\n', ' ').trim().replaceAll("\\s+", " ");
        if (s.equalsIgnoreCase("null") || s.equals("?")) return "";
        if (s.length() > MAX_ENTITY_CHARS) s = s.substring(0, MAX_ENTITY_CHARS) + "…";
        return s;
    }

    private static String extract(Pattern pattern, String text) {
        Matcher m = pattern.matcher(text == null ? "" : text);
        return m.find() ? safe(m.group(1)).trim() : "";
    }

    private static String safe(String value) { return value == null ? "" : value; }
    private static double clamp01(double value) { return Math.max(0.0, Math.min(1.0, value)); }
}
