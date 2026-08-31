# VictorOS Android Owner Release Signing

Status: **required infrastructure; private key must remain outside this public repository**.

## Why this exists

Android only permits an installed application to be upgraded by an APK signed by the same signing identity. GitHub's default debug signing identity can change between runners/builds, so debug artifacts are development artifacts, not a durable VictorOS continuity mechanism.

VictorOS release identity therefore belongs to the owner, not to a CI runner and not to model weights.

## Invariants

1. The private keystore is never committed to Git.
2. Release builds fail closed when owner signing inputs are absent.
3. CI verifies the APK signer SHA-256 fingerprint against the owner-pinned fingerprint before publishing an artifact.
4. The existing Android sensory permission allowlist is re-verified on every signed release.
5. `android.permission.INTERNET` remains forbidden for the current local-only Android line.
6. The owner must keep at least two offline backups of the keystore and recovery credentials. Losing this key means future APKs cannot upgrade the installed application under the same Android identity.

## One-time owner key ceremony

Run this on a machine or trusted Termux/JDK environment controlled by the owner:

```bash
keytool -genkeypair -v \
  -keystore victor-owner-release.jks \
  -alias victor-owner \
  -keyalg RSA \
  -keysize 4096 \
  -validity 10000 \
  -dname "CN=VictorOS Owner, O=Massive Magnetics, C=US"
```

Use unique strong passwords and store them with the keystore in an owner-controlled password manager / offline recovery record.

Read the certificate fingerprint:

```bash
keytool -list -v -keystore victor-owner-release.jks -alias victor-owner
```

Record the certificate **SHA256** fingerprint. This fingerprint is public identity metadata; the keystore and passwords are private.

Encode the keystore for GitHub Actions:

```bash
base64 -w 0 victor-owner-release.jks > victor-owner-release.jks.b64
```

On systems whose `base64` command does not support `-w`, use the platform equivalent that emits a single uninterrupted Base64 string.

## GitHub Actions secrets

In repository **Settings → Secrets and variables → Actions**, create these repository secrets:

- `VICTOR_ANDROID_KEYSTORE_B64` — contents of `victor-owner-release.jks.b64`
- `VICTOR_ANDROID_STORE_PASSWORD` — keystore password
- `VICTOR_ANDROID_KEY_ALIAS` — normally `victor-owner`
- `VICTOR_ANDROID_KEY_PASSWORD` — private-key password
- `VICTOR_ANDROID_SIGNER_SHA256` — expected certificate SHA-256 fingerprint

The connected ChatGPT GitHub integration cannot write repository secrets; this step must be performed by the repository owner through GitHub's secret-management UI or another owner-authenticated secret-management channel.

## Release flow

After the five secrets exist, run **VictorOS Owner-Signed Android Release** from GitHub Actions, or push a tag matching `android-v*`.

The release workflow:

1. materializes the keystore only inside the ephemeral Actions runner,
2. runs Android/JVM tests,
3. invokes the fail-closed `assembleRelease` path,
4. verifies the APK cryptographic signature,
5. verifies the signer fingerprint equals `VICTOR_ANDROID_SIGNER_SHA256`,
6. re-verifies the exact Android permission allowlist and absence of `INTERNET`,
7. emits the APK SHA-256 and signer SHA-256,
8. uploads the owner-signed APK artifact.

## Continuity rule

Once the first owner-signed VictorOS build is installed, **all future production upgrades must use the same owner signing identity** unless Android's formally supported signing-key rotation mechanism is deliberately adopted and documented.

Do not uninstall a VictorOS installation containing local history merely to work around a signature mismatch. Resolve signing continuity first or explicitly export/migrate state before destructive replacement.
