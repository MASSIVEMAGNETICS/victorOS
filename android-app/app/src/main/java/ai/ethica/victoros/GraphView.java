package ai.ethica.victoros;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PointF;
import android.graphics.Typeface;
import android.view.MotionEvent;
import android.view.View;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class GraphView extends View {
    public interface OnNodeSelectedListener { void onNodeSelected(JSONObject node); }

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Map<String, PointF> positions = new LinkedHashMap<>();
    private JSONArray nodes = new JSONArray();
    private JSONArray edges = new JSONArray();
    private OnNodeSelectedListener listener;

    public GraphView(Context context) {
        super(context);
        setBackgroundColor(Color.rgb(12, 14, 17));
        setFocusable(true);
    }

    public void setData(JSONArray nodes, JSONArray edges) {
        this.nodes = nodes == null ? new JSONArray() : nodes;
        this.edges = edges == null ? new JSONArray() : edges;
        positions.clear();
        invalidate();
    }

    public void setOnNodeSelectedListener(OnNodeSelectedListener listener) {
        this.listener = listener;
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        layoutNodes(getWidth(), getHeight());

        paint.setStrokeWidth(dp(1));
        paint.setColor(Color.rgb(67, 76, 86));
        for (int i = 0; i < edges.length(); i++) {
            JSONObject edge = edges.optJSONObject(i);
            if (edge == null) continue;
            PointF a = positions.get(edge.optString("from"));
            PointF b = positions.get(edge.optString("to"));
            if (a != null && b != null) canvas.drawLine(a.x, a.y, b.x, b.y, paint);
        }

        for (int i = 0; i < nodes.length(); i++) {
            JSONObject node = nodes.optJSONObject(i);
            if (node == null) continue;
            PointF point = positions.get(node.optString("id"));
            if (point == null) continue;
            float radius = dp(7) + (node.optInt("attention", 50) / 100f) * dp(7);
            paint.setColor(clusterColor(node.optString("cluster")));
            canvas.drawCircle(point.x, point.y, radius, paint);
            if (node.optInt("attention", 0) >= 90) {
                paint.setStyle(Paint.Style.STROKE);
                paint.setStrokeWidth(dp(2));
                paint.setColor(Color.WHITE);
                canvas.drawCircle(point.x, point.y, radius + dp(3), paint);
                paint.setStyle(Paint.Style.FILL);
            }
        }

        paint.setTypeface(Typeface.DEFAULT_BOLD);
        paint.setTextSize(dp(11));
        paint.setColor(Color.rgb(220, 225, 230));
        int y = dp(18);
        for (String cluster : clusterOrder()) {
            paint.setColor(clusterColor(cluster));
            canvas.drawText(cluster, dp(10), y, paint);
            y += dp(15);
        }
    }

    private void layoutNodes(int width, int height) {
        if (!positions.isEmpty() || width <= 0 || height <= 0) return;
        List<String> clusters = clusterOrder();
        if (clusters.isEmpty()) return;
        float cx = width / 2f;
        float cy = height / 2f;
        float outer = Math.max(dp(70), Math.min(width, height) * 0.34f);

        Map<String, List<JSONObject>> grouped = new LinkedHashMap<>();
        for (String cluster : clusters) grouped.put(cluster, new ArrayList<>());
        for (int i = 0; i < nodes.length(); i++) {
            JSONObject node = nodes.optJSONObject(i);
            if (node == null) continue;
            grouped.computeIfAbsent(node.optString("cluster", "UNSORTED"), k -> new ArrayList<>()).add(node);
        }

        for (int c = 0; c < clusters.size(); c++) {
            String cluster = clusters.get(c);
            double clusterAngle = (Math.PI * 2d * c / clusters.size()) - Math.PI / 2d;
            float clusterX = cx + (float) Math.cos(clusterAngle) * outer;
            float clusterY = cy + (float) Math.sin(clusterAngle) * outer;
            List<JSONObject> members = grouped.get(cluster);
            if (members == null || members.isEmpty()) continue;
            for (int i = 0; i < members.size(); i++) {
                double local = members.size() == 1 ? 0 : (Math.PI * 2d * i / members.size());
                float localRadius = members.size() == 1 ? 0 : dp(24) + Math.min(dp(30), members.size() * dp(2));
                float x = clamp(clusterX + (float) Math.cos(local) * localRadius, dp(24), width - dp(24));
                float y = clamp(clusterY + (float) Math.sin(local) * localRadius, dp(24), height - dp(24));
                positions.put(members.get(i).optString("id"), new PointF(x, y));
            }
        }
    }

    private List<String> clusterOrder() {
        List<String> clusters = new ArrayList<>();
        for (int i = 0; i < nodes.length(); i++) {
            JSONObject node = nodes.optJSONObject(i);
            if (node == null) continue;
            String cluster = node.optString("cluster", "UNSORTED");
            if (!clusters.contains(cluster)) clusters.add(cluster);
        }
        return clusters;
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        if (event.getAction() != MotionEvent.ACTION_UP) return true;
        JSONObject selected = null;
        float best = dp(34);
        for (int i = 0; i < nodes.length(); i++) {
            JSONObject node = nodes.optJSONObject(i);
            if (node == null) continue;
            PointF p = positions.get(node.optString("id"));
            if (p == null) continue;
            float dx = event.getX() - p.x;
            float dy = event.getY() - p.y;
            float distance = (float) Math.sqrt(dx * dx + dy * dy);
            if (distance < best) {
                best = distance;
                selected = node;
            }
        }
        if (selected != null && listener != null) listener.onNodeSelected(selected);
        performClick();
        return true;
    }

    @Override public boolean performClick() {
        super.performClick();
        return true;
    }

    private int clusterColor(String cluster) {
        int[] colors = {
                Color.rgb(168, 255, 53), Color.rgb(183, 92, 255), Color.rgb(54, 190, 255),
                Color.rgb(255, 178, 66), Color.rgb(255, 91, 126), Color.rgb(80, 224, 177)
        };
        int index = Math.floorMod(cluster == null ? 0 : cluster.hashCode(), colors.length);
        return colors[index];
    }

    private float clamp(float value, float min, float max) {
        return Math.max(min, Math.min(max, value));
    }

    private int dp(int n) {
        return (int) (n * getResources().getDisplayMetrics().density);
    }
}
