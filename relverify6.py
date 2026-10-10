import sys, tempfile, traceback
from pathlib import Path
sys.path.insert(0, r"D:\data\camfrog")
import importlib
ca = importlib.import_module("camfrog_auto")
log = []
try:
    log.append("running version: " + ca.APP_VERSION)
    tag, notes, assets = ca.github_latest_release()
    log.append("latest release : " + tag + " | assets: " + str(len(assets)))
    url, sums = assets["room-control.exe"], assets["SHA256SUMS.txt"]
    log.append("asset url host: " + url.split("/")[2])
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "room-control.exe"
        size = ca.download_update(url, str(target))
        ok = ca.verify_against_sums(sums, "room-control.exe", target)
        log.append("downloaded: " + str(size) + " bytes")
        log.append("verified: " + str(ok))
except Exception:
    log.append(traceback.format_exc()[-800:])
Path(r"D:\data\camfrog\relverify6.log").write_text("\n".join(log), encoding="utf-8")
print("wrote log")
