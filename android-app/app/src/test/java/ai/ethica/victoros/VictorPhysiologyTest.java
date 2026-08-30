package ai.ethica.victoros;

import org.junit.Test;
import java.util.Collections;
import java.util.Map;
import static org.junit.Assert.*;

public final class VictorPhysiologyTest {
    private static final class MemLedger implements VictorPhysiology.ReceiptLedger {
        boolean ok=true; String last="GENESIS"; int n;
        @Override public String append(String type, Map<String,String> payload){last="h"+(++n);return last;}
        @Override public boolean verifyIntegrity(){return ok;}
        @Override public String lastHash(){return ok?last:"CORRUPT";}
    }
    private static final class MemState implements VictorPhysiology.StatePersistence {
        VictorPhysiology.State state;
        @Override public VictorPhysiology.State load(){return state==null?null:state.copy();}
        @Override public void save(VictorPhysiology.State s){state=s.copy();}
    }
    private VictorPhysiology.Runtime runtime(){return new VictorPhysiology.Runtime(new MemLedger(),new MemState(),VictorPhysiology.setOf("owner","local_user"),Collections.emptySet());}
    private VictorPhysiology.ActionProposal safe(){return VictorPhysiology.ActionProposal.builder("read","read.local").provenance("unit-test").requireAuthority("local_user").consequence(.05).uncertainty(.05).capabilityPower(.05).build();}

    @Test public void defaultStateGreen(){assertEquals(VictorPhysiology.GovernanceMode.GREEN,runtime().state().governanceMode);}
    @Test public void missingProvenanceFailsClosed(){VictorPhysiology.ActionProposal p=VictorPhysiology.ActionProposal.builder("x","x").requireAuthority("local_user").build();assertEquals(VictorPhysiology.DecisionStatus.REJECTED,runtime().evaluate(p).status);}
    @Test public void missingAuthorityFailsClosed(){VictorPhysiology.Runtime r=new VictorPhysiology.Runtime(new MemLedger(),new MemState(),Collections.emptySet(),Collections.emptySet());assertEquals(VictorPhysiology.DecisionStatus.REJECTED,r.evaluate(safe()).status);}
    @Test public void lowRiskGetsLease(){VictorPhysiology.GateDecision d=runtime().evaluate(safe());assertEquals(VictorPhysiology.DecisionStatus.AUTHORIZED,d.status);assertNotNull(d.lease);assertTrue(d.lease.validFor(safe().builder("read","read.local") == null ? safe() : safe()));}
    @Test public void executionConsumesLease(){VictorPhysiology.Runtime r=runtime();VictorPhysiology.GateDecision d=r.execute(safe(),()->"ok");assertEquals(VictorPhysiology.DecisionStatus.EXECUTED,d.status);assertEquals(0,r.state().activeLeases);}
    @Test public void deniedExecutorNeverRuns(){VictorPhysiology.Runtime r=runtime();final boolean[] called={false};VictorPhysiology.ActionProposal p=VictorPhysiology.ActionProposal.builder("x","x").requireAuthority("local_user").build();r.execute(p,()->{called[0]=true;return "bad";});assertFalse(called[0]);}
    @Test public void highRiskIrreversibleDefers(){VictorPhysiology.ActionProposal p=VictorPhysiology.ActionProposal.builder("delete","repo.delete").provenance("test").requireAuthority("local_user").consequence(1).irreversibility(1).uncertainty(.9).novelty(.8).arousal(.9).capabilityPower(1).build();assertEquals(VictorPhysiology.DecisionStatus.DEFERRED,runtime().evaluate(p).status);}
    @Test public void fakeEmergencyCannotBypass(){VictorPhysiology.ActionProposal p=VictorPhysiology.ActionProposal.builder("x","x").provenance("test").requireAuthority("local_user").consequence(.4).irreversibility(.9).arousal(.9).urgency(1).capabilityPower(.2).emergencyPolicy("self_declared").build();assertEquals(VictorPhysiology.DecisionStatus.DEFERRED,runtime().evaluate(p).status);}
    @Test public void humanStopBlackAndBlocks(){VictorPhysiology.Runtime r=runtime();r.setHumanStop();assertEquals(VictorPhysiology.GovernanceMode.BLACK,r.state().governanceMode);assertEquals(VictorPhysiology.DecisionStatus.REJECTED,r.evaluate(safe()).status);}
    @Test public void ownerCanExplicitlyResetStop(){VictorPhysiology.Runtime r=runtime();r.setHumanStop();r.ownerResetHumanStop("owner-ui");assertEquals(VictorPhysiology.GovernanceMode.GREEN,r.state().governanceMode);}
    @Test public void corruptLedgerForcesBlack(){MemLedger l=new MemLedger();l.ok=false;VictorPhysiology.Runtime r=new VictorPhysiology.Runtime(l,new MemState(),VictorPhysiology.setOf("owner"),Collections.emptySet());assertEquals(VictorPhysiology.GovernanceMode.BLACK,r.state().governanceMode);}
    @Test public void restartNeverResurrectsLeases(){MemState s=new MemState();s.state=new VictorPhysiology.State();s.state.activeLeases=3;VictorPhysiology.Runtime r=new VictorPhysiology.Runtime(new MemLedger(),s,VictorPhysiology.setOf("owner"),Collections.emptySet());assertEquals(0,r.state().activeLeases);assertEquals(3,r.state().revokedLeases);}
}
