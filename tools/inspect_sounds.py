import winreg

for sub in [".Default", "SystemAsterisk", "SystemExclamation", "SystemHand", "SystemNotification"]:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"AppEvents\\Schemes\\Apps\\.Default\\{sub}\\.Current")
        val, _ = winreg.QueryValueEx(k, "")
        print(f"{sub}\\.Current -> {val!r}")
    except Exception as e:
        print(f"{sub} error: {e}")
