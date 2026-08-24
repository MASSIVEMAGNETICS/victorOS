# VictorOS Android v0.1

Native, offline-first Android shell for persistent experience intelligence.

## Implemented

- Organ-based home screen: Cortex, Memory Vault, Chronos, Ethica, Homeostasis, Command Center.
- Durable on-device episodic event store.
- SHA-256-linked Chronos receipt chain with integrity verification.
- Persistent homeostatic metrics.
- Bounded command interpreter with explicit policy/authority failures.
- Zero Android permissions and no network access.
- Android application backup disabled so private VictorOS state is not exported through the normal Android backup path.
- Android 8.0+ (`minSdk 26`), targeting Android 15 (`targetSdk 35`).

This build is a governed OS-style cognitive shell. It does **not** claim to be AGI and does not yet embed a local language model.

## Build on Windows 10

1. Install Android Studio with Android SDK Platform 35.
2. Open this folder in Android Studio.
3. Let Gradle sync.
4. Select **Build > Build APK(s)**.
5. Install `app/build/outputs/apk/debug/app-debug.apk` on the phone after enabling installation from your file manager.

CLI after Android Studio creates/downloads the wrapper:

```powershell
.\gradlew.bat assembleDebug
```

## Security boundary

The app requests no Android permissions. Its command system can modify only its private SharedPreferences state. Android backup is disabled and cleartext traffic is disabled in the application manifest. CI inspects the built debug APK—not only the source manifest—and fails if a merged manifest introduces any Android permission, enables application backup, or enables cleartext traffic.

Receipts detect accidental or unauthorized event-chain changes, but the private preference store is not encrypted in v0.1. Device compromise/root, physical extraction outside normal Android backup, and compromise of the OS itself remain outside the current threat boundary.
