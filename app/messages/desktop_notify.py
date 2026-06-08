def send_notification(title: str, message: str, app_icon: str = "", app_name: str = "StreamCap", timeout: int = 10):
    from plyer import notification

    notification.notify(title=title, message=message, app_icon=app_icon, app_name=app_name, timeout=timeout)


def should_push_notification(app) -> bool:
    if app is None or getattr(app, "page", None) is None:
        return False
    page = app.page

    if page.web:
        return False
    settings = getattr(app, "settings", None)
    user_config = getattr(settings, "user_config", {}) if settings is not None else {}
    system_notification_enabled = user_config.get("system_notification_enabled", True)
    try:
        is_window_hidden = page.window.minimized or not page.window.visible
    except Exception:
        return False
    return system_notification_enabled and is_window_hidden
