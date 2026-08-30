package ai.ethica.victoros;

import android.content.Context;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Local common shared-space world model for Victor's sensory organs.
 * Raw sensory payloads remain process-local and bounded in memory. Persistent
 * receipts contain only source/hash/size metadata, never raw screen/camera/audio.
 */
public final class GodsEyeWorldModel {
    public static final class Observation {
        public final String timestamp, source, summary, contentHash;
        public final int byteCount;
        Observation(String source,String summary,String hash,int bytes){
            this.timestamp=Instant.now().toString(); this.source=source; this.summary=summary;
            this.contentHash=hash; this.byteCount=bytes;
        }
        @Override public String toString(){return timestamp+" | "+source+" | "+summary+" | "+contentHash.substring(0,Math.min(12,contentHash.length()))+"…";}
    }

    private static final int MAX_RECENT = 64;
    private static final int MAX_BINARY_BYTES = 6 * 1024 * 1024;
    private static final Deque<Observation> RECENT = new ArrayDeque<>();
    private static final Map<String,byte[]> LATEST_BINARY = new HashMap<>();
    private static final Map<String,String> LATEST_TEXT = new HashMap<>();

    private GodsEyeWorldModel() {}

    public static synchronized Observation publishText(Context context,String source,String text,String summary){
        VictorStore store=new VictorStore(context.getApplicationContext());
        if(store.load().humanStop)return blocked(source,"HUMAN STOP");
        if(!store.verifyIntegrity())return blocked(source,"LEDGER CORRUPT");
        String payload=text==null?"":text;String hash=VictorStore.sha256(payload);LATEST_TEXT.put(source,payload);
        return commit(store,source,summary==null?"text observation":summary,hash,payload.getBytes(java.nio.charset.StandardCharsets.UTF_8).length);
    }

    public static synchronized Observation publishBinary(Context context,String source,byte[] bytes,String summary){
        VictorStore store=new VictorStore(context.getApplicationContext());
        if(store.load().humanStop)return blocked(source,"HUMAN STOP");
        if(!store.verifyIntegrity())return blocked(source,"LEDGER CORRUPT");
        byte[] input=bytes==null?new byte[0]:bytes;byte[] bounded=input.length<=MAX_BINARY_BYTES?Arrays.copyOf(input,input.length):Arrays.copyOf(input,MAX_BINARY_BYTES);
        String hash=VictorStore.sha256(input);LATEST_BINARY.put(source,bounded);return commit(store,source,summary==null?"binary observation":summary,hash,input.length);
    }

    private static Observation blocked(String source,String reason){return new Observation(source,"blocked by "+reason,VictorStore.sha256(reason),0);}
    private static Observation commit(VictorStore store,String source,String summary,String hash,int bytes){
        Observation o=new Observation(source,summary,hash,bytes);RECENT.addFirst(o);while(RECENT.size()>MAX_RECENT)RECENT.removeLast();store.recordGodsEyeMetadata(source,hash,bytes,summary);return o;
    }

    public static synchronized void clearEphemeral(){LATEST_BINARY.clear();LATEST_TEXT.clear();RECENT.clear();}
    public static synchronized byte[] latestBinary(String source){byte[] b=LATEST_BINARY.get(source);return b==null?null:Arrays.copyOf(b,b.length);}
    public static synchronized String latestText(String source){return LATEST_TEXT.get(source);}
    public static synchronized List<Observation> recent(){return new ArrayList<>(RECENT);}
    public static synchronized String summary(){if(RECENT.isEmpty())return "No live observations in this process.";StringBuilder out=new StringBuilder();int n=0;for(Observation o:RECENT){out.append(o).append('\n');if(++n>=12)break;}return out.toString().trim();}
}
