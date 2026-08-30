package ai.ethica.victoros;

import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.IBinder;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Locale;

public final class VictorMicrophoneService extends Service {
    public static final String ACTION_STOP="ai.ethica.victoros.STOP_MIC";
    private volatile boolean running;
    private AudioRecord recorder;
    private Thread worker;

    @Override public int onStartCommand(Intent intent,int flags,int startId){
        if(intent!=null&&ACTION_STOP.equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
        VictorForegroundNotifications.start(this,2102,"Victor · Microphone Ear","Microphone perception is active",ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
        if(running)return START_STICKY;
        try{startAudio();return START_STICKY;}catch(Exception e){GodsEyeWorldModel.publishText(getApplicationContext(),"MIC_ERROR",e.getClass().getSimpleName()+": "+e.getMessage(),"microphone start error");stopSelf();return START_NOT_STICKY;}
    }

    private void startAudio(){
        int sampleRate=16000;int min=AudioRecord.getMinBufferSize(sampleRate,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT);
        if(min<=0)throw new IllegalStateException("AudioRecord buffer unavailable");
        recorder=new AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION,sampleRate,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,Math.max(min,sampleRate*2));
        if(recorder.getState()!=AudioRecord.STATE_INITIALIZED)throw new IllegalStateException("AudioRecord init failed");
        recorder.startRecording();running=true;
        worker=new Thread(()->{
            short[] samples=new short[4096];long last=0;
            while(running){int n=recorder.read(samples,0,samples.length);if(n<=0)continue;long now=System.currentTimeMillis();if(now-last<500)continue;last=now;
                double sum=0;ByteBuffer raw=ByteBuffer.allocate(n*2).order(ByteOrder.LITTLE_ENDIAN);for(int i=0;i<n;i++){short s=samples[i];sum+=(double)s*s;raw.putShort(s);}double rms=Math.sqrt(sum/Math.max(1,n))/32768.0;
                GodsEyeWorldModel.publishBinary(getApplicationContext(),"MIC",raw.array(),"pcm16 16kHz rms="+String.format(Locale.US,"%.4f",rms));
            }
        },"VictorMicrophoneEar");worker.start();
    }

    @Override public void onDestroy(){running=false;if(recorder!=null){try{recorder.stop();}catch(Exception ignored){}recorder.release();recorder=null;}if(worker!=null){try{worker.join(500);}catch(InterruptedException ignored){Thread.currentThread().interrupt();}worker=null;}super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
