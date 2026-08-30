package ai.ethica.victoros;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.ImageFormat;
import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraDevice;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.media.Image;
import android.media.ImageReader;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import java.nio.ByteBuffer;
import java.util.Collections;

public final class VictorCameraService extends Service {
    public static final String ACTION_STOP="ai.ethica.victoros.STOP_CAMERA";
    private HandlerThread thread; private Handler handler; private CameraDevice camera; private CameraCaptureSession session; private ImageReader reader; private long lastFrameMs;
    @Override public void onCreate(){super.onCreate();thread=new HandlerThread("VictorCameraEye");thread.start();handler=new Handler(thread.getLooper());}
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        if(intent!=null&&ACTION_STOP.equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
        VictorForegroundNotifications.start(this,2103,"Victor · Camera Eye","Camera perception is active",ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA);
        VictorStore store=new VictorStore(this);if(store.load().humanStop||!store.isLedgerTrusted()){stopSelf();return START_NOT_STICKY;}
        if(camera==null)openCamera();return START_NOT_STICKY;
    }
    private void openCamera(){
        try{
            CameraManager manager=(CameraManager)getSystemService(Context.CAMERA_SERVICE);String chosen=null;
            for(String id:manager.getCameraIdList()){CameraCharacteristics c=manager.getCameraCharacteristics(id);Integer facing=c.get(CameraCharacteristics.LENS_FACING);if(facing!=null&&facing==CameraCharacteristics.LENS_FACING_FRONT){chosen=id;break;}if(chosen==null)chosen=id;}
            if(chosen==null)throw new IllegalStateException("No camera available");
            reader=ImageReader.newInstance(640,480,ImageFormat.JPEG,2);
            reader.setOnImageAvailableListener(r->{Image image=null;try{VictorStore store=new VictorStore(getApplicationContext());if(store.load().humanStop||!store.isLedgerTrusted()){stopSelf();return;}image=r.acquireLatestImage();if(image==null)return;long now=System.currentTimeMillis();if(now-lastFrameMs<1000)return;lastFrameMs=now;ByteBuffer b=image.getPlanes()[0].getBuffer();byte[] jpeg=new byte[b.remaining()];b.get(jpeg);GodsEyeWorldModel.publishBinary(getApplicationContext(),"CAMERA",jpeg,"camera jpeg 640x480");}catch(Exception e){GodsEyeWorldModel.publishText(getApplicationContext(),"CAMERA_ERROR",e.getClass().getSimpleName(),"camera frame error");}finally{if(image!=null)image.close();}},handler);
            manager.openCamera(chosen,new CameraDevice.StateCallback(){
                @Override public void onOpened(CameraDevice d){camera=d;VictorStore store=new VictorStore(getApplicationContext());if(store.load().humanStop||!store.isLedgerTrusted()){d.close();camera=null;stopSelf();return;}startSession();}
                @Override public void onDisconnected(CameraDevice d){d.close();camera=null;stopSelf();}
                @Override public void onError(CameraDevice d,int error){d.close();camera=null;GodsEyeWorldModel.publishText(getApplicationContext(),"CAMERA_ERROR","camera2 error="+error,"camera device error");stopSelf();}
            },handler);
        }catch(Exception e){GodsEyeWorldModel.publishText(getApplicationContext(),"CAMERA_ERROR",e.getClass().getSimpleName()+": "+e.getMessage(),"camera start error");stopSelf();}
    }
    private void startSession(){
        if(camera==null||reader==null)return;
        try{camera.createCaptureSession(Collections.singletonList(reader.getSurface()),new CameraCaptureSession.StateCallback(){
            @Override public void onConfigured(CameraCaptureSession s){session=s;try{CaptureRequest.Builder b=camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);b.addTarget(reader.getSurface());b.set(CaptureRequest.CONTROL_AF_MODE,CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE);s.setRepeatingRequest(b.build(),null,handler);}catch(Exception e){GodsEyeWorldModel.publishText(getApplicationContext(),"CAMERA_ERROR",e.getClass().getSimpleName(),"camera session error");}}
            @Override public void onConfigureFailed(CameraCaptureSession s){GodsEyeWorldModel.publishText(getApplicationContext(),"CAMERA_ERROR","configure failed","camera session configure failed");stopSelf();}
        },handler);}catch(Exception e){GodsEyeWorldModel.publishText(getApplicationContext(),"CAMERA_ERROR",e.getClass().getSimpleName(),"camera session create error");stopSelf();}
    }
    @Override public void onDestroy(){if(session!=null){session.close();session=null;}if(camera!=null){camera.close();camera=null;}if(reader!=null){reader.close();reader=null;}if(thread!=null){thread.quitSafely();thread=null;}super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
