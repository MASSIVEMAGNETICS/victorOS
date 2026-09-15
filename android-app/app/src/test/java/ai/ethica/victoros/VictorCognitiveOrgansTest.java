package ai.ethica.victoros;

import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public final class VictorCognitiveOrgansTest {
    @Test
    public void retainsConfiguredTwoCharacterNegator() {
        assertTrue(VictorCognitiveOrgans.hasNegation("no camera is available"));
    }

    @Test
    public void detectsLongerConfiguredNegators() {
        assertTrue(VictorCognitiveOrgans.hasNegation("camera is not available"));
        assertTrue(VictorCognitiveOrgans.hasNegation("camera never started"));
    }

    @Test
    public void affirmativePhraseRemainsNonNegated() {
        assertFalse(VictorCognitiveOrgans.hasNegation("camera is available"));
    }
}
