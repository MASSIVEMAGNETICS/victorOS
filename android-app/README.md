# Victor GEV Android v0.2

Native Android owner console for VictorOS / God's Eye View (GEV). It is designed to run directly on a Samsung Galaxy S20/S21-class phone or any Android 8.0+ device while preserving Victor's local-first, evidence-bearing state model.

## What changed from v0.1

v0.1 proved a zero-permission, local-only Android shell with persistent state and a SHA-256-linked Chronos receipt chain.

v0.2 adds the **Empire Control Plane** without replacing those organs:

- Mobile main menu: **NOW / MAP / PROJECTS / REVENUE / MEMORY / EVIDENCE / SYSTEMS / CONTROL**.
- Tappable node-cluster GEV projection backed by a typed Empire graph.
- Seeded management topology: Victor Prime → Empire Steward → specialist chiefs → workers/projects.
- Local node create/update from the phone.
- Android Share integration: share text from another app to **Victor GEV** and it becomes an `INBOX` node plus a Chronos observation receipt.
- Canonical snapshot export through Android's standard share sheet.
- Optional authenticated HTTPS synchronization to an owner-controlled Victor endpoint.
- Automatic periodic sync through Android `JobScheduler` (Android's minimum periodic cadence is 15 minutes) plus an attempted sync when the app opens.
- Sync token encrypted at rest using Android Keystore AES-GCM.
- Remote graph validation, bounded response size, redirect rejection and Chronos receipts for accepted remote revisions.

## Phone-first operating model

The phone is usable when the laptop is off.

```text
Android phone
  ├─ private local state
  ├─ Chronos receipt chain
  ├─ Empire node/edge graph
  ├─ GEV projection
  ├─ owner commands
  └─ pending local events
          │
          │ authenticated HTTPS when available
          ▼
Owner-controlled Victor sync endpoint
  ├─ canonical revision
  ├─ wider Empire graph
  ├─ server-side sensors/connectors
  └─ durable cross-device state
```

If the server is unavailable, local operation continues. Sync failure never deletes or rewrites local Chronos history.

## Sync security boundary

The Android manifest requests exactly one Android permission:

```text
android.permission.INTERNET
```

No contacts, SMS, microphone, camera, location, storage/files, accessibility, notification-listener or device-admin authority is requested.

Additional rules:

- `android:allowBackup=false`.
- `android:usesCleartextTraffic=false`.
- Sync accepts only `https://` endpoints.
- HTTP redirects are rejected so the bearer token is not forwarded to another host.
- Local Chronos verification must pass before sync transmits.
- The bearer token is encrypted with a key held by Android Keystore.
- Remote graph payloads are bounded and structurally validated before becoming the local projected graph.
- Remote imports emit local Chronos receipts carrying the remote revision and an evidence hash.
- The sync endpoint cannot send arbitrary shell commands to the phone.

CI inspects the **built APK merged manifest** and fails if any Android permission other than `INTERNET` appears, backup is enabled, or cleartext traffic is enabled.

## Sync endpoint contract

Configure the complete endpoint URL from **CONTROL**, for example:

```text
https://victor.example.com/v1/sync
```

The client sends:

```json
{
  "schema": "victor-mobile-sync/v1",
  "deviceId": "<stable-device-uuid>",
  "sentAt": "<ISO-8601>",
  "lastRemoteRevision": "<revision-or-none>",
  "localHead": "<latest-chronos-hash>",
  "events": []
}
```

with:

```text
Authorization: Bearer <owner-token>
X-Victor-Device: <stable-device-uuid>
```

A minimal successful response is:

```json
{
  "revision": "rev-42",
  "ackedThrough": 12
}
```

A canonical graph response can additionally contain:

```json
{
  "revision": "rev-43",
  "ackedThrough": 12,
  "nodes": [
    {
      "id": "project-id",
      "label": "Project",
      "cluster": "EXECUTION",
      "kind": "project",
      "status": "active",
      "attention": 90,
      "updatedAt": "2026-08-29T00:00:00Z"
    }
  ],
  "edges": [
    {"from": "empire-steward", "to": "project-id", "relation": "supervises"}
  ]
}
```

The remote endpoint is responsible for authentication, canonicalization, durable server storage, replay protection and revision assignment. The Android client does not treat network availability as truth.

## Install on a Samsung Galaxy S20/S21

1. Build or download the `Victor-GEV-Android-v0.2-debug` GitHub Actions artifact.
2. Extract the artifact ZIP to get `app-debug.apk`.
3. Open the APK on the phone.
4. Android will ask you to allow installation from the app/file manager you used to open it; enable that source only if you intend to sideload this build.
5. Install and launch **Victor GEV**.
6. It works immediately in local mode. Configure server sync later under **CONTROL**.

## Build locally

Requirements:

- JDK 17
- Android SDK Platform 35
- Gradle 8.9 (CI supplies it automatically)

From `android-app/`:

```powershell
gradle --no-daemon --stacktrace assembleDebug
```

APK:

```text
app/build/outputs/apk/debug/app-debug.apk
```

## Acceptance tests before widening authority

1. Install the exact CI artifact on a physical Android device.
2. Open MAP and verify cluster rendering/tap selection.
3. Create a node in CONTROL; force-stop/reopen; verify it persists.
4. Share text from another Android app to Victor GEV; verify an INBOX node and Chronos receipt appear.
5. Run EVIDENCE and verify the Chronos chain.
6. Configure a test HTTPS endpoint/token and sync; verify the server receives only pending receipts.
7. Apply a known remote revision and verify it becomes visible with a `VERIFIED_IMPORT` receipt.
8. Disable the server/network and verify local state remains usable.
9. Reboot the phone, reopen Victor GEV, and verify state continuity. The periodic job is intentionally rescheduled on app launch rather than requesting boot authority.

Do not add new Android permissions or remote execution capabilities in the same acceptance cycle.
