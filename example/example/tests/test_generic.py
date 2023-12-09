import os

from django.test import TestCase

from example.models import Car
from kaskader.tests.generators import GenericBaseMixin, GenericTestMixin


class ExampleBaseMixin(GenericBaseMixin):
    PRINT_TEST_SUBJECT = True
    PRINT_SORTED_MODEL_DEPENDENCY = True
    CHECK_MODULES = ['example']
    EXCLUDE_MODULES = ['commands', 'migrations', 'settings', 'tests']
    TEST_PASSWORD = 'testpassword'
    IGNORE_MODEL_FIELDS = {
        Car: ['created', 'modified'], # specific model fields can be ignored when generating data
    }
    RUN_ONLY_THESE_URL_NAMES = [
    ]
    RUN_ONLY_URL_NAMES_CONTAINING = [
    ]
    IGNORE_URL_NAMES_CONTAINING = [
        'admin:',
        'rosetta-',
    ]
    GET_ONLY_URLS = [
    ]

    fixtures = ['initial_data.json']


class ExampleTestMixin(GenericTestMixin, ExampleBaseMixin, TestCase):
    def setUp(self):
        pass