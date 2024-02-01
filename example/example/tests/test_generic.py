import os

from django.test import TestCase
from django.urls import reverse

from cars.filters import CarFilter
from cars.models import Car, BrandModel, CarBrand
from cars.querysets import CarQuerySet
from kaskader.tests.generators import GenericBaseMixin, GenericTestMixin


class ExampleBaseMixin(GenericBaseMixin):
    PRINT_TEST_SUBJECT = True
    PRINT_SORTED_MODEL_DEPENDENCY = True
    CHECK_MODULES = ['cars', 'cars']
    EXCLUDE_MODULES = ['commands', 'migrations', 'settings', 'tests', 'cars.kaskader']
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
    ] # ulrs that should only be tested on get request

    # fixtures = ['initial_data.json']

    @classmethod
    def setUpTestData(cls):
        # before generating objects

        # generate objects
        super(GenericBaseMixin, cls).setUpTestData()

        # after generating objects

    @classmethod
    def generate_obj(cls, model, field_values=None, **kwargs):
        # this method is used to generate every single object, can be used for setting model-wide default values as follows

        model_default_kwargs = {
            Car: lambda cls: {
                'color': 'BLACK',
            },
        }.get(model, lambda cls: {})(cls)

        model_default_kwargs.update(kwargs if field_values is None else field_values(cls) if callable(field_values) else field_values)
        return super().generate_obj(model, field_values=None, **model_default_kwargs)

    @classmethod
    def manual_model_dependency(cls):
        # use to manually force dependency, useful especially with complex m2m relations
        return {
            BrandModel: {CarBrand},
        }

    @classmethod
    def model_field_values_map(cls):
        # default objects to genrate with specific values
        return {
            CarBrand: {
                'mercedes': {
                    'title': 'Mercedes',
                },
            },
            BrandModel: {
                'sls_amg': lambda cls: {
                    'brand': cls.get_generated_obj(CarBrand, 'mercedes'),
                    'title': 'SLS AMG',
                },
                'sprinter': lambda cls: {
                    'brand': cls.get_generated_obj(CarBrand, 'mercedes'),
                    'title': 'Sprinter',
                }
            }

        }

    @property
    def url_params_map(self):
        # default test values for specific urls
        return {
            'cars:car_create': {
                'data': {'data': {'model': self.get_generated_obj(BrandModel, 'sls_amg').id}},
                'form_kwargs': {
                    'brand': self.get_generated_obj(CarBrand, 'mercedes'),
                    'data': {'model': self.get_generated_obj(BrandModel, 'sls_amg').id},
                },
            },
            'cars:car_delete': {
                'url_args': {'args': [self.get_generated_obj(Car).id]},
                'url_kwargs': {'url_kwargs': {'pk': self.get_generated_obj(Car).id}},
                'request_kwargs': {'request_kwargs': {'back_url': reverse('cars:car_create')}},
            },
            'cars:car_list': {
                'sorting_options': {'sorting': 'model__brand'},
                'display_option': {'display': 'list'},
            }
        }

    @property
    def queryset_params_map(self):
        return {
            CarQuerySet: {
                'brand': {'brand': self.get_generated_obj(CarBrand, 'mercedes')},
                'model': {'model': self.get_generated_obj(BrandModel, 'sls_amg')},
            }
        }

    @property
    def filter_params_map(self):
        return {
            CarFilter: {
                'data': {'data': { # data is used to provide specific filter data
                    'model__brand': self.get_generated_obj(CarBrand, 'mercedes').id,
                    'model': self.get_generated_obj(BrandModel, 'sls_amg').id,
                }},
                'filter_kwargs': {'filter_kwargs': {'queryset': Car.objects.all()}}, # filter_kwargs are used to get Filter instance before generating field values
            },
        }


class ExampleTest(GenericTestMixin, ExampleBaseMixin, TestCase):
    def setUp(self):
        pass
