from typing import Literal
class VERSION:
    VERSION = "0.0.2-alpha"
    BUILD = "2025.12.07:23.40"
    RELEASE = 'DEV'

    @staticmethod
    def version() -> str:
        return VERSION.VERSION

    @staticmethod
    def build() -> str:
        return VERSION.BUILD

    @staticmethod
    def release() -> Literal['DEBUG', 'BETA', 'RELEASE', 'ALPHA', "DEV"]:
        return VERSION.RELEASE