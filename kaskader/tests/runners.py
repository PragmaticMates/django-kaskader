from unittest import TextTestResult, TextTestRunner

from django.db import connections, DEFAULT_DB_ALIAS
from django.test.runner import DiscoverRunner


class ExtensionDiscoverRunner(DiscoverRunner):
    pass
