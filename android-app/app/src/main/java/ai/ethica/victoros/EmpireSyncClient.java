package ai.ethica.victoros;

import android.content.Context;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public final class EmpireSyncClient {
    private static final int MAX_RESPONSE_BYTES = 2 * 1024 * 1024;

    public static final class Result {
        public final boolean success;
        public final String message;

        Result(boolean success, String message) {
            this.success = success;
            this.message = message;
        }
    }

    private EmpireSyncClient() {}

    public static Result sync(Context context, VictorStore store) {
        if (!store.isSyncEnabled()) return new Result(false, "Automatic sync is disabled");
        if (!store.verify().isEmpty()) {
            store.recordSyncFailure("Local Chronos chain failed verification");
            return new Result(false, "Blocked: local Chronos chain is not verified");
        }

        String endpoint = store.getSyncEndpoint();
        String token = new SecureSecretStore(context).getToken();
        if (endpoint.isEmpty()) return new Result(false, "No sync endpoint configured");
        if (token.isEmpty()) return new Result(false, "No sync token configured");

        try {
            URI uri = URI.create(endpoint);
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null || uri.getHost().isEmpty()) {
                store.recordSyncFailure("Endpoint must be HTTPS");
                return new Result(false, "Blocked: endpoint must use HTTPS");
            }

            URL url = uri.toURL();
            HttpURLConnection connection = (HttpURLConnection) url.openConnection();
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(15000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("Authorization", "Bearer " + token);
            connection.setRequestProperty("X-Victor-Device", store.deviceId());

            byte[] payload = store.buildSyncPayload().toString().getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(payload.length);
            try (OutputStream out = connection.getOutputStream()) {
                out.write(payload);
            }

            int status = connection.getResponseCode();
            if (status >= 300 && status < 400) {
                connection.disconnect();
                store.recordSyncFailure("Redirect rejected: HTTP " + status);
                return new Result(false, "Blocked: sync redirects are not allowed");
            }

            InputStream stream = status >= 200 && status < 300 ? connection.getInputStream() : connection.getErrorStream();
            String body = readBounded(stream);
            connection.disconnect();

            if (status < 200 || status >= 300) {
                String safe = body == null ? "" : VictorStore.clean(body.replace('\n', ' '), 180);
                store.recordSyncFailure("HTTP " + status + (safe.isEmpty() ? "" : ": " + safe));
                return new Result(false, "Sync failed: HTTP " + status);
            }

            JSONObject response = new JSONObject(body == null || body.trim().isEmpty() ? "{}" : body);
            store.applySyncResponse(response);
            return new Result(true, "Synced revision " + store.getLastRemoteRevision());
        } catch (Exception e) {
            String safe = VictorStore.clean(e.getClass().getSimpleName() + ": " + (e.getMessage() == null ? "sync error" : e.getMessage()), 240);
            store.recordSyncFailure(safe);
            return new Result(false, safe);
        }
    }

    private static String readBounded(InputStream stream) throws Exception {
        if (stream == null) return "";
        try (InputStream in = stream; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int total = 0;
            int read;
            while ((read = in.read(buffer)) != -1) {
                total += read;
                if (total > MAX_RESPONSE_BYTES) throw new IllegalStateException("Sync response exceeded 2 MiB");
                out.write(buffer, 0, read);
            }
            return out.toString(StandardCharsets.UTF_8.name());
        }
    }
}
