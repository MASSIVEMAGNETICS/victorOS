package ai.ethica.victoros;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class EmpireControlPlaneTest {
    @Test
    public void seeds_expected_owner_topology() {
        EmpireControlPlane plane = new EmpireControlPlane();
        assertNotNull(plane.get("victor-prime"));
        assertNotNull(plane.get("empire-steward"));
        assertNotNull(plane.get("governance-chief"));
        assertTrue(plane.allNodes().size() >= 9);
        assertTrue(plane.allEdges().size() >= 8);
    }

    @Test
    public void presentation_model_never_grants_authority() {
        EmpireControlPlane plane = new EmpireControlPlane();
        assertFalse(plane.grantsAuthority());
    }

    @Test
    public void attention_is_bounded() {
        boolean threw = false;
        try {
            new EmpireControlPlane.Node("bad", "Bad", "project", "PROJECTS", "active", 101, null);
        } catch (IllegalArgumentException expected) {
            threw = true;
        }
        assertTrue(threw);
    }

    @Test
    public void surface_projection_is_cluster_scoped_and_ranked() {
        EmpireControlPlane plane = new EmpireControlPlane();
        plane.put(new EmpireControlPlane.Node("project-low", "Low", "project", "PROJECTS", "active", 20, null));
        plane.put(new EmpireControlPlane.Node("project-high", "High", "project", "PROJECTS", "active", 99, null));

        assertEquals("project-high", plane.forSurface(EmpireControlPlane.Surface.PROJECTS).get(0).id);
        for (EmpireControlPlane.Node node : plane.forSurface(EmpireControlPlane.Surface.PROJECTS)) {
            assertEquals("PROJECTS", node.cluster);
        }
    }

    @Test
    public void highest_attention_is_deterministic() {
        EmpireControlPlane plane = new EmpireControlPlane();
        assertEquals("victor-prime", plane.highestAttention(1).get(0).id);
        assertEquals(3, plane.highestAttention(3).size());
    }
}
