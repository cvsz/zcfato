import sys, tempfile
from pathlib import Path
sys.path.insert(0, r"D:\data\camfrog")
import importlib
ca = importlib.import_module("camfrog_auto")
log = []
try:
    tag, notes, assets = ca.github_latest_release()
    log.append("latest release : " + tag + " | assets: " + str(len(assets)))
    found = ca.check_release_assets("room-control.exe")
    log.append("sums url: " + (found[2].split("?")[0][-40:] if found else "NONE"))
    url, sums = assets["room-control.exe"], found[2]
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "room-control.exe"
        size = ca.download_update(url, str(target))
        ok = ca.verify_against_sums(sums, "room-control.exe", target)
        log.append("downloaded: " + str(size) + " bytes")
        log.append("verified: " + str(ok))
except Exception:
    import traceback
    log.append(traceback.format_exc()[-600:])
Path(r"D:\data\camfrog\relverify7.log").write_text("\n".join(log), encoding="utf-8")
print("wrote log")
