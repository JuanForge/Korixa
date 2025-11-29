from typing import Literal

class notification:
    def __init__(self, enable: bool = True):
        self.enable = enable
        if self.enable:
            from notifypy import Notify # type: ignore
            self.Notify = Notify

    def send(self, message: str, title: str = "Korixa", level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'DEBUG'):
        if self.enable:
            notification = self.Notify(#default_notification_icon="./Assets/icon.ico", # type: ignore
                                    default_notification_title=title,
                                    #default_notification_audio="./Assets/0.wav",
                                    default_notification_application_name="Korixa"
                                )
            notification.message = message
            notification.send()
