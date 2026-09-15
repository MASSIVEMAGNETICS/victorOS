package ai.ethica.victoros;

import org.junit.Test;
import static org.junit.Assert.*;

public final class VictorDevelopmentRuntimeTest {
    private static final class MemoryPersistence implements VictorDevelopmentRuntime.Persistence {
        String committed = "";
        VictorDevelopmentRuntime.Pending pending;
        String receipt = "";
        @Override public String loadCommitted(){ return committed; }
        @Override public VictorDevelopmentRuntime.Pending loadPending(){ return pending; }
        @Override public void stage(String s,String e,String h){ pending=new VictorDevelopmentRuntime.Pending(s,e,h); }
        @Override public void commitPending(String r){ committed=pending.encodedState; receipt=r; pending=null; }
        @Override public void discardPending(){ pending=null; }
    }

    private static final class MemoryChronos implements VictorDevelopmentRuntime.Chronos {
        boolean trusted=true;
        String evidence="", state="";
        boolean failAppend=false;
        @Override public boolean verifyIntegrity(){ return trusted; }
        @Override public String appendVerifiedLearning(String e,String s,long n){
            if(failAppend) throw new IllegalStateException("fail");
            evidence=e; state=s; return "receipt-"+n;
        }
        @Override public boolean containsVerifiedLearning(String e,String s){ return e.equals(evidence)&&s.equals(state); }
    }

    @Test public void verifiedOutcomePersistsAndSurvivesRestart(){
        MemoryPersistence p=new MemoryPersistence(); MemoryChronos c=new MemoryChronos();
        VictorDevelopmentRuntime r=new VictorDevelopmentRuntime(p,c);
        assertTrue(r.learn(new VictorGrowthEngine.ExperienceOutcome("planning",.2,.9,true,"ev1")));
        assertFalse(p.committed.isEmpty());
        VictorDevelopmentRuntime restarted=new VictorDevelopmentRuntime(p,c);
        assertEquals(1,restarted.state().verifiedExperiences());
        assertFalse(restarted.grantsAuthority());
        assertFalse(restarted.canExpandPermissions());
    }

    @Test public void corruptChronosBlocksLearning(){
        MemoryPersistence p=new MemoryPersistence(); MemoryChronos c=new MemoryChronos(); c.trusted=false;
        VictorDevelopmentRuntime r=new VictorDevelopmentRuntime(p,c);
        assertFalse(r.learn(new VictorGrowthEngine.ExperienceOutcome("memory",.5,.8,true,"ev2")));
        assertTrue(p.committed.isEmpty());
    }

    @Test public void failedReceiptRollsBackStagedState(){
        MemoryPersistence p=new MemoryPersistence(); MemoryChronos c=new MemoryChronos(); c.failAppend=true;
        VictorDevelopmentRuntime r=new VictorDevelopmentRuntime(p,c);
        assertFalse(r.learn(new VictorGrowthEngine.ExperienceOutcome("memory",.5,.8,true,"ev3")));
        assertNull(p.pending); assertTrue(p.committed.isEmpty());
    }

    @Test public void restartDiscardsUnreceiptedPendingState(){
        MemoryPersistence p=new MemoryPersistence(); MemoryChronos c=new MemoryChronos();
        p.pending=new VictorDevelopmentRuntime.Pending("verified=4\n","missing","state-x");
        new VictorDevelopmentRuntime(p,c);
        assertNull(p.pending); assertTrue(p.committed.isEmpty());
    }

    @Test public void restartPromotesReceiptBackedPendingState(){
        MemoryPersistence p=new MemoryPersistence(); MemoryChronos c=new MemoryChronos();
        p.pending=new VictorDevelopmentRuntime.Pending("verified=4\n","ev4","state-y");
        c.evidence="ev4"; c.state="state-y";
        VictorDevelopmentRuntime r=new VictorDevelopmentRuntime(p,c);
        assertNull(p.pending); assertEquals(4,r.state().verifiedExperiences());
    }
}
