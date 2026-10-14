# Camfrog Public Presence Evidence

`camfrog_presence.py` is a read-only first-stage provider for the public Camfrog status widget. It sends one HTTPS GET to `https://www.camfrog.com/getstatus.php?nick=...` without cookies, session state, account credentials, or payment data.

## Evidence and classification

Every saved observation has `state=unknown` and `entity_kind=unknown`. An HTTP 200 response with `Content-Type: image/gif` proves only that Camfrog returned a status image. It does not prove that the nickname is online, identify a user versus a room, show room membership, validate a Give Gift recipient, or reveal a subscription entitlement.

For bounded `image/gif` responses the provider records:

- HTTP status, content type, declared content length, bytes received, `Cache-Control`, parsed `max-age`, `ETag`, `Last-Modified`, and `Retry-After`;
- raw GIF SHA-256 and normalized RGBA pixel SHA-256 across every frame;
- width, height, frame count, probe outcome, attempt count, and UTC observation time.

The client caps responses at 256 KiB, GIFs at 128 frames and 16 million total frame pixels, uses a 5-second timeout, retries transport/selected server errors at most twice with backoff, and does not retry rate-limit responses or server responses with `Retry-After`. Redirects must remain on `https://www.camfrog.com`. Parsed cache ages are capped at one year. Pillow is used only to decode bounded GIFs; unknown or invalid content never becomes an online/offline classification. The provider is one-shot and does not schedule polling; its caller must respect the returned origin cache age and spread multi-account requests with jitter.

## Local evidence store

The SQLite database stores each observation and deduplicates raw GIF bodies by SHA-256. It is local to the current user and stores no cookies or tokens. The default location is `%LOCALAPPDATA%\Camfrog\Presence\presence-evidence.sqlite3` on Windows or `$XDG_DATA_HOME/camfrog/presence/presence-evidence.sqlite3` on Linux when `XDG_DATA_HOME` is set; otherwise it uses `~/.local/share/camfrog/presence/presence-evidence.sqlite3`. Set `CAMFROG_PRESENCE_DATA_DIR` to override the data directory. On POSIX, the provider requests mode `0700` for the data directory and `0600` for the database file.

Evidence is retained until explicitly pruned. Use the API `EvidenceStore.prune_before(iso_timestamp)` or the CLI prune command after exporting any samples that must be retained.

## CLI

The CLI performs one request only when `probe` is called:

```console
python camfrog_presence.py probe cf_test_01
python camfrog_presence.py recent --nickname cf_test_01 --limit 20
python camfrog_presence.py export-gif RAW_SHA256 samples/cf_test_01.gif
python camfrog_presence.py prune --before 2026-01-01T00:00:00Z
```

Pass `--database PATH` before the subcommand to select a database. `probe` prints the observation as JSON and stores the GIF in SQLite when Camfrog returns a bounded `image/gif` response. The `export-gif` command refuses to overwrite an existing file.

## Controlled comparison before adding labels

Use accounts you control. Capture an offline sample only after the reported cache lifetime has elapsed, then capture the same account while online. If useful, capture it again after joining a known room. Also capture one generated nonexistent nickname. Export the stored GIFs and compare both raw and normalized hashes, dimensions, and frame counts.

Do not map a fingerprint to ONLINE, OFFLINE, INVALID, USER, or ROOM until controlled observations establish what that response means. Unknown fingerprints and malformed responses remain unclassified. Room membership and client process state are separate future providers and are not implemented here.

The Give Gift recipient resolver remains a separate subsystem and still requires an authorized, sanitized capture of its own UI validation request to establish its exact contract.
