package ai.ethica.victoros;

import org.junit.Test;
import static org.junit.Assert.*;

public final class VictorPerceptionFusionTest {
    @Test public void matchingUiAndUsageSignalsAgreeOnActiveApp(){
        VictorPerceptionFusion f=new VictorPerceptionFusion(5000);
        f.ingestAt("APP_CONTEXT","usageAccess=true\nrecentForeground=com.example.app\nlaunchableApps=2","app context","a",100,1000,1000);
        VictorPerceptionFusion.PerceptualFrame frame=f.ingestAt("ACTIVE_UI","package=com.example.app\nclass=Main\n0:Button text=Open\n1:TextView desc=Dashboard\n","active UI","b",120,1100,1100);
        assertEquals("com.example.app",frame.activePackage);
        assertTrue(frame.conflicts.isEmpty());
        assertTrue(frame.entities.contains("Open"));
        assertTrue(frame.entities.contains("Dashboard"));
        assertTrue(frame.confidence>0.60);
    }

    @Test public void conflictingAppSignalsAreExplicitNotSilentlyResolved(){
        VictorPerceptionFusion f=new VictorPerceptionFusion(5000);
        f.ingestAt("APP_CONTEXT","recentForeground=com.one","app context","a",10,1000,1000);
        VictorPerceptionFusion.PerceptualFrame frame=f.ingestAt("ACTIVE_UI","package=com.two\n0:TextView text=Hello\n","active UI","b",20,1001,1001);
        assertEquals("com.two",frame.activePackage);
        assertEquals(1,frame.conflicts.size());
        assertTrue(frame.conflicts.get(0).contains("com.two!=com.one"));
    }

    @Test public void passwordRedactionNeverBecomesEntity(){
        VictorPerceptionFusion f=new VictorPerceptionFusion(5000);
        VictorPerceptionFusion.PerceptualFrame frame=f.ingestAt("ACTIVE_UI","package=com.test\n0:EditText text=[REDACTED_PASSWORD]\n1:Button text=Login\n","active UI","x",10,1000,1000);
        assertFalse(frame.entities.toString().contains("REDACTED_PASSWORD"));
        assertTrue(frame.entities.contains("Login"));
    }

    @Test public void microphoneRmsProducesBoundedActivityState(){
        VictorPerceptionFusion f=new VictorPerceptionFusion(5000);
        VictorPerceptionFusion.PerceptualFrame quiet=f.ingestAt("MIC","","pcm16 16kHz rms=0.0040","m1",100,1000,1000);
        assertEquals(VictorPerceptionFusion.AudioState.QUIET,quiet.audioState);
        VictorPerceptionFusion.PerceptualFrame active=f.ingestAt("MIC","","pcm16 16kHz rms=0.0800","m2",100,1100,1100);
        assertEquals(VictorPerceptionFusion.AudioState.ACTIVE,active.audioState);
        VictorPerceptionFusion.PerceptualFrame loud=f.ingestAt("MIC","","pcm16 16kHz rms=0.4100","m3",100,1200,1200);
        assertEquals(VictorPerceptionFusion.AudioState.LOUD,loud.audioState);
        assertTrue(loud.attention>active.attention);
    }

    @Test public void visualAndSemanticModalitiesShareOneFrame(){
        VictorPerceptionFusion f=new VictorPerceptionFusion(5000);
        f.ingestAt("SCREEN","","screen 720x1600 jpeg","s",2000,1000,1000);
        f.ingestAt("CAMERA","","camera jpeg 640x480","c",3000,1001,1001);
        VictorPerceptionFusion.PerceptualFrame frame=f.ingestAt("ACTIVE_UI","package=com.test\n0:TextView text=Settings\n","active UI","u",100,1002,1002);
        assertTrue(frame.screenPresent);
        assertTrue(frame.cameraPresent);
        assertTrue(frame.activeUiPresent);
        assertTrue(frame.modalities.contains("SCREEN"));
        assertTrue(frame.modalities.contains("CAMERA"));
        assertTrue(frame.modalities.contains("ACTIVE_UI"));
    }

    @Test public void staleSignalsAgeOutOfSharedSpace(){
        VictorPerceptionFusion f=new VictorPerceptionFusion(1000);
        f.ingestAt("SCREEN","","screen","s",10,1000,1000);
        VictorPerceptionFusion.PerceptualFrame frame=f.currentFrameAt(2501);
        assertFalse(frame.screenPresent);
        assertTrue(frame.modalities.isEmpty());
    }

    @Test public void clearErasesEphemeralFusedState(){
        VictorPerceptionFusion f=new VictorPerceptionFusion(5000);
        f.ingestAt("ACTIVE_UI","package=com.test\n0:TextView text=Private local text\n","active UI","u",100,1000,1000);
        f.clear();
        VictorPerceptionFusion.PerceptualFrame frame=f.currentFrameAt(1001);
        assertTrue(frame.activePackage.isEmpty());
        assertTrue(frame.entities.isEmpty());
        assertTrue(frame.modalities.isEmpty());
    }
}
