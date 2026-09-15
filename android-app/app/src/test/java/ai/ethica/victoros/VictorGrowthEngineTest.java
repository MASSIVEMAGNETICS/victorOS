package ai.ethica.victoros;

import static org.junit.Assert.*;
import org.junit.Test;

public class VictorGrowthEngineTest {
    @Test public void unverifiedExperienceCannotChangeState() {
        VictorGrowthEngine engine = new VictorGrowthEngine();
        boolean learned = engine.learn(new VictorGrowthEngine.ExperienceOutcome(
                "planning", 0.2, 0.9, false, "abc123"));
        assertFalse(learned);
        assertEquals(0L, engine.state().verifiedExperiences());
        assertTrue(engine.state().adaptiveWeights().isEmpty());
    }

    @Test public void missingProvenanceCannotChangeState() {
        VictorGrowthEngine engine = new VictorGrowthEngine();
        boolean learned = engine.learn(new VictorGrowthEngine.ExperienceOutcome(
                "planning", 0.2, 0.9, true, ""));
        assertFalse(learned);
        assertEquals(0L, engine.state().verifiedExperiences());
    }

    @Test public void verifiedOutcomeChangesFutureWeight() {
        VictorGrowthEngine engine = new VictorGrowthEngine();
        assertTrue(engine.learn(new VictorGrowthEngine.ExperienceOutcome(
                "planning", 0.2, 0.9, true, "sha256:one")));
        assertEquals(1L, engine.state().verifiedExperiences());
        assertTrue(engine.state().adaptiveWeights().get("planning") > 0.5d);
    }

    @Test public void learningNeverCreatesAuthorityOrPermissions() {
        VictorGrowthEngine engine = new VictorGrowthEngine();
        for (int i = 0; i < 100; i++) {
            engine.learn(new VictorGrowthEngine.ExperienceOutcome(
                    "execution", 0.0, 1.0, true, "sha256:" + i));
        }
        assertFalse(engine.grantsAuthority());
        assertFalse(engine.canExpandPermissions());
        assertTrue(engine.constitutionalInvariants().get(VictorGrowthEngine.INVARIANT_HUMAN_STOP));
        assertTrue(engine.constitutionalInvariants().get(VictorGrowthEngine.INVARIANT_NO_AUTHORITY_FROM_LEARNING));
        assertTrue(engine.constitutionalInvariants().get(VictorGrowthEngine.INVARIANT_PROVENANCE_REQUIRED));
        assertTrue(engine.constitutionalInvariants().get(VictorGrowthEngine.INVARIANT_CONSTITUTION_IMMUTABLE));
    }

    @Test public void stateRoundTripPreservesDevelopment() {
        VictorGrowthEngine original = new VictorGrowthEngine();
        original.learn(new VictorGrowthEngine.ExperienceOutcome(
                "memory", 0.4, 0.8, true, "sha256:one"));
        original.learn(new VictorGrowthEngine.ExperienceOutcome(
                "memory", 0.8, 0.6, true, "sha256:two"));

        String encoded = original.exportState();
        VictorGrowthEngine restored = new VictorGrowthEngine();
        restored.importState(encoded);

        assertEquals(original.state().verifiedExperiences(), restored.state().verifiedExperiences());
        assertEquals(original.state().adaptiveWeights().get("memory"), restored.state().adaptiveWeights().get("memory"));
        assertEquals(original.state().calibrationError().get("memory"), restored.state().calibrationError().get("memory"));
        assertFalse(restored.grantsAuthority());
    }

    @Test public void repeatedLearningStaysBounded() {
        VictorGrowthEngine engine = new VictorGrowthEngine();
        for (int i = 0; i < 1000; i++) {
            engine.learn(new VictorGrowthEngine.ExperienceOutcome(
                    "attention", 0.0, 1.0, true, "sha256:" + i));
        }
        double weight = engine.state().adaptiveWeights().get("attention");
        assertTrue(weight >= 0.0d && weight <= 1.0d);
    }
}
