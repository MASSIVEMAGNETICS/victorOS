package ai.ethica.victoros;

import android.app.Activity;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.content.pm.ServiceInfo;
import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;

public final class VictorScreenCaptureService extends Service {
    public static final String ACTION_STOP="ai.ethica.victoros.STOP_SCREEN";
    public static final String EXTRA_RESULT_CODE="result_code";
    public static final String EXTRA_DATA="capture_data";
    private MediaProjection projection; private VirtualDisplay display; private ImageReader reader; private HandlerThread thread; private Handler handler; private long lastFrameMs;

    @Override public void onCreate(){super.onCreate();thread=new HandlerThread("VictorScreenEye");thread.start();handler=new Handler(thread.getLooper());}

    @SuppressWarnings("deprecation")
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        if(intent!=null&&ACTION_STOP.equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
        VictorForegroundNotifications.start(this,2101,"Victor · Screen Eye","Screen perception is active",ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        if(new VictorStore(this).load().humanStop){stopSelf();return START_NOT_STICKY;}
        if(projection!=null)return START_NOT_STICKY;
        if(intent==null){stopSelf();return START_NOT_STICKY;}
        int resultCode=intent.getIntExtra(EXTRA_RESULT_CODE,Activity.RESULT_CANCELED);Intent data=intent.getParcelableExtra(EXTRA_DATA);
        if(resultCode!=Activity.RESULT_OK||data==null){stopSelf();return START_NOT_STICKY;}
        MediaProjectionManager m=(MediaProjectionManager)getSystemService(Context.MEDIA_PROJECTION_SERVICE);projection=m.getMediaProjection(resultCode,data);
        if(projection==null){stopSelf();return START_NOT_STICKY;}
        projection.registerCallback(new MediaProjection.Callback(){@Override public void onStop(){stopSelf();}},handler);startCapture();return START_NOT_STICKY;
    }

    private void startCapture(){
        int sourceW=getResources().getDisplayMetrics().widthPixels,sourceH=getResources().getDisplayMetrics().heightPixels;
        int width=Math.min(720,Math.max(320,sourceW));int height=Math.max(320,(int)Math.round(sourceH*(width/(double)Math.max(1,sourceW))));int dpi=Math.max(160,getResources().getDisplayMetrics().densityDpi);
        reader=ImageReader.newInstance(width,height,PixelFormat.RGBA_8888,2);
        reader.setOnImageAvailableListener(r->{Image image=null;try{
            if(new VictorStore(getApplicationContext()).load().humanStop){stopSelf();return;}
            image=r.acquireLatestImage();if(image==null)return;long now=System.currentTimeMillis();if(now-lastFrameMs<1000)return;lastFrameMs=now;
            Image.Plane plane=image.getPlanes()[0];ByteBuffer buffer=plane.getBuffer();int pixelStride=plane.getPixelStride(),rowStride=plane.getRowStride(),rowPadding=rowStride-pixelStride*width;
            int paddedWidth=width+Math.max(0,rowPadding/pixelStride);Bitmap padded=Bitmap.createBitmap(paddedWidth,height,Bitmap.Config.ARGB_8888);padded.copyPixelsFromBuffer(buffer);
            Bitmap cropped=Bitmap.createBitmap(padded,0,0,width,height);ByteArrayOutputStream out=new ByteArrayOutputStream();cropped.compress(Bitmap.CompressFormat.JPEG,58,out);
            GodsEyeWorldModel.publishBinary(getApplicationContext(),"SCREEN",out.toByteArray(),"screen "+width+"x"+height+" jpeg");cropped.recycle();padded.recycle();
        }catch(Exception e){GodsEyeWorldModel.publishText(getApplicationContext(),"SCREEN_ERROR",e.getClass().getSimpleName(),"screen capture error");}finally{if(image!=null)image.close();}},handler);
        display=projection.createVirtualDisplay("VictorGodsEyeScreen",width,height,dpi,DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,reader.getSurface(),null,handler);
    }

    @Override public void onDestroy(){if(display!=null){display.release();display=null;}if(reader!=null){reader.close();reader=null;}if(projection!=null){projection.stop();projection=null;}if(thread!=null){thread.quitSafely();thread=null;}super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
