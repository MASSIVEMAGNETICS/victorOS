package ai.ethica.victoros;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;

public final class SyncJobService extends JobService {
    public static final int JOB_ID = 44021;
    private volatile Thread worker;

    public static void reconcile(Context context, VictorStore store) {
        JobScheduler scheduler = (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (scheduler == null) return;
        scheduler.cancel(JOB_ID);
        if (!store.isSyncEnabled() || store.getSyncEndpoint().isEmpty()) return;
        JobInfo job = new JobInfo.Builder(JOB_ID, new ComponentName(context, SyncJobService.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPeriodic(15 * 60 * 1000L)
                .build();
        scheduler.schedule(job);
    }

    @Override public boolean onStartJob(JobParameters params) {
        worker = new Thread(() -> {
            try {
                VictorStore store = new VictorStore(getApplicationContext());
                EmpireSyncClient.sync(getApplicationContext(), store);
            } finally {
                jobFinished(params, false);
            }
        }, "victor-empire-sync");
        worker.start();
        return true;
    }

    @Override public boolean onStopJob(JobParameters params) {
        Thread current = worker;
        if (current != null) current.interrupt();
        return true;
    }
}
