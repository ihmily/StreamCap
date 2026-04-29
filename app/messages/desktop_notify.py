def send_notification(title: str, message: str, app_icon: str = "", app_name: str = "StreamCap", timeout: int = 10):
    from plyer import notification

    notification.notify(title=title, message=message, app_icon=app_icon, app_name=app_name, timeout=timeout)


def should_push_notification(app) -> bool:
    is_window_hidden = app.page.window.minimized or not app.page.window.visible
    system_notification_enabled = app.settings.user_config.get("system_notification_enabled", True)
    return not app.page.web and system_notification_enabled and is_window_hidden
