import ast
import functools
import importlib
import inspect
import itertools
import os
import pkgutil
import random
import re
import traceback
from datetime import timedelta
from pprint import pformat, pprint

import sys
from collections import OrderedDict

from django import urls
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models as gis_models
from django.contrib.gis import forms as gis_forms
from django.contrib.gis.geos import Point, MultiPoint
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.postgres import fields as postgres_fields
from django.contrib.postgres import forms as postgres_forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import transaction, IntegrityError
from django.db.models import NOT_PROVIDED, BooleanField, TextField, CharField, SlugField, EmailField, DateTimeField, \
    DateField, FileField, PositiveSmallIntegerField, DecimalField, IntegerField, QuerySet, PositiveIntegerField, \
    SmallIntegerField, BigIntegerField, FloatField, ImageField, GenericIPAddressField, URLField
from django.db.models.fields.related import RelatedField, ManyToManyField, ForeignKey, OneToOneField
from django_filters import fields as django_filter_fields, FilterSet
from django.forms import fields as django_form_fields
from django.forms import models as django_form_models
from django.http import QueryDict
from django.test import RequestFactory
from django.urls import reverse, URLResolver, URLPattern, get_resolver
from django.utils.timezone import now
from requests import Response

try:
    from django.db.models import JSONField
except ImportError:
    # older django
    from django.contrib.postgres.fields import JSONField

try:
    # older Django
    from django.utils.translation import ugettext_lazy as _
except ImportError:
    # Django >= 3
    from django.utils.translation import gettext_lazy as _

from django.views.generic import CreateView, UpdateView, DeleteView

# TODO: refactor: apps below are optional
if 'internationalflavor' in getattr(settings, 'INSTALLED_APPS'):
    from internationalflavor import iban as intflavor_iban, countries as intflavor_countries, vat_number as intflavor_vat

if 'pragmatic' in getattr(settings, 'INSTALLED_APPS'):
    import pragmatic

if 'gm2m' in getattr(settings, 'INSTALLED_APPS'):
    from gm2m import GM2MField
    RELATED_FIELDS = (RelatedField, GM2MField)
else:
    RELATED_FIELDS = (RelatedField)

class InputMixin(object):
    # USER_MODEL = User # there is possibility to manualy specify user model to be used, see user_model()
    CHECK_MODULES = []  # list modules which should be included, eg [myapp], or more specifically [myapp.core, myapp.subapp1]
    EXCLUDE_MODULES = ['migrations', 'commands', 'tests', 'settings']    # list all modules that should be excluded from search for models, urls, ..
    TEST_PASSWORD = 'testpassword'  # login password for users
    IGNORE_MODEL_FIELDS = {}  # values for these model fields will not be generated, use for fields with automatically assigned values, for example {MPTTModel: ['lft', 'rght', 'tree_id', 'level']}
    PRINT_SORTED_MODEL_DEPENDENCY = False   # print models dependency for debug purposes
    PRINT_TEST_SUBJECT = False # print url params/filter class/queryset being tested

    # params for GenericTestMixin.test_urls
    RUN_ONLY_THESE_URL_NAMES = []  # if not empty will run tests only for provided urls, for debug purposes to save time
    RUN_ONLY_URL_NAMES_CONTAINING = []  # if not empty will run tests only for urls containing at least one of provided patterns
    IGNORE_URL_NAMES_CONTAINING = []  # contained urls will not be tested
    POST_ONLY_URLS = []  # run only post request tests for these urls
    GET_ONLY_URLS = []  # run only get request tests for these urls

    @classmethod
    def manual_model_dependency(cls):
        '''
        Use to manually specify model dependency which are not accounted for by default (check get_sorted_models_dependency output),
        for example if generating objs with provided m2m values, or otherwise required in model_field_values_map
        return {
            User: {Group}
        }
        '''

        return {}

    @classmethod
    def model_field_values_map(cls):
        '''
        Enables generate objects with specific values, for example for User model:

        {
            User: {
                'user_1': lambda cls: {
                    'username': f'user.{cls.next_id(User)}@example.com',
                    'email': f'user.{cls.next_id(User)}@example.com',
                    'password': 'testpassword',
                    'is_superuser': True,
                },
                'user_2': lambda cls: {
                    'username': f'user.{cls.next_id(User)}@example.com',
                    'email': f'user.{cls.next_id(User)}@example.com',
                    'password': 'testpassword',
                    'is_superuser': False,
                }
            },
        }
        '''
        return {}

    @classmethod
    def default_field_name_map(cls):
        '''
        field values by field name used to generate objects, this has priority before default_field_map,
        values can be callables with field variable, extend in subclass as needed
        '''
        return {
            'year': now().year,
            'month': now().month,
        }

    @classmethod
    def default_field_map(cls):
        '''
        field values by field class used to generate objects, values can be callables with field variable,
        extend in subclass as needed
        '''

        map = {
            ForeignKey: lambda f: cls.get_generated_obj(f.related_model),
            OneToOneField: lambda f: cls.get_generated_obj(f.related_model),
            BooleanField: False,
            TextField: lambda f: '{}_{}'.format(f.model._meta.label_lower, f.name),
            CharField: lambda f: list(f.choices)[0][0] if f.choices else '{}'.format(f.name)[:f.max_length],
            SlugField: lambda f: '{}_{}'.format(f.name, cls.next_id(f.model)),
            EmailField: lambda f: '{}.{}@example.com'.format(f.model._meta.label_lower, cls.next_id(f.model)),
            gis_models.PointField: Point(0.1276, 51.5072),
            gis_models.MultiPointField: MultiPoint(Point(0.1276, 51.5072), Point(0.1276, 51.5072)),
            DateTimeField: lambda f: now(),
            DateField: lambda f: now().date(),
            postgres_fields.DateTimeRangeField: (now(), now() + timedelta(days=1)),
            postgres_fields.DateRangeField: (now().date(), now() + timedelta(days=1)),
            FileField: lambda f: cls.get_pdf_file_mock(),
            IntegerField: lambda f: cls.get_num_field_mock_value(f),
            PositiveSmallIntegerField: lambda f: cls.get_num_field_mock_value(f),
            DecimalField: lambda f: cls.get_num_field_mock_value(f),
            PositiveIntegerField: lambda f: cls.get_num_field_mock_value(f),
            SmallIntegerField: lambda f: cls.get_num_field_mock_value(f),
            BigIntegerField: lambda f: cls.get_num_field_mock_value(f),
            FloatField: lambda f: cls.get_num_field_mock_value(f),
            ImageField: lambda f: cls.get_image_file_mock(),
            GenericIPAddressField: '127.0.0.1',
            postgres_fields.JSONField: {'key': 'value'},
            postgres_fields.HStoreField: {'key': 'value'},
            postgres_fields.ArrayField: lambda f: [cls.default_field_map()[f.base_field.__class__](f.base_field)],
            JSONField: {},
            URLField: lambda f: 'www.google.com',
        }

        try:
            map.update({
                intflavor_countries.CountryField: 'LU',
                intflavor_iban.IBANField: 'LU28 0019 4006 4475 0000',
                intflavor_vat.VATNumberField: lambda f: 'LU{}'.format(random.randint(10000000, 99999999)),  # 'GB904447273',
            })
        except NameError:
            pass

        return map

    @classmethod
    def default_form_field_map(cls):
        '''
        field values by form field class used to generate form values, values can be callables with field variable,
        extend in subclass as needed
        '''
        map = {
            django_filter_fields.ModelChoiceField: lambda f: f.queryset.first().id,
            django_filter_fields.ModelMultipleChoiceField: lambda f: f.queryset.first().id,
            django_filter_fields.MultipleChoiceField: lambda f: [list(f.choices)[-1][0]] if f.choices else ['{}'.format(f.label)],
            django_filter_fields.ChoiceField: lambda f: list(f.choices)[-1][0],
            django_filter_fields.RangeField: lambda f: [1, 100],
            django_filter_fields.DateRangeField: lambda f: (now().date(), now() + timedelta(days=1)),
            django_form_fields.EmailField: lambda f: cls.get_new_email(),
            django_form_fields.CharField: lambda f: '{}_{}'.format(f.label.encode('utf8') if f.label else f.label, random.randint(1, 999))[:f.max_length],
            django_form_fields.TypedChoiceField: lambda f: list(f.choices)[-1][1][0][0] if f.choices and isinstance(list(f.choices)[-1][1], list) else list(f.choices)[-1][0] if f.choices else '{}'.format(f.label)[:f.max_length],
            django_form_fields.ChoiceField: lambda f: list(f.choices)[-1][1][0][0] if f.choices and isinstance(list(f.choices)[-1][1], list) else list(f.choices)[-1][0] if f.choices else '{}'.format(f.label)[:f.max_length],
            django_form_fields.ImageField: lambda f: cls.get_image_file_mock(),
            django_form_fields.FileField: lambda f: cls.get_pdf_file_mock(),
            django_form_fields.DateTimeField: lambda f: now().strftime(list(f.input_formats)[-1]) if hasattr(f, 'input_formats') else now(),
            django_form_fields.DateField: now().date(),
            django_form_fields.IntegerField: lambda f: cls.get_num_field_mock_value(f),
            django_form_fields.DecimalField: lambda f: cls.get_num_field_mock_value(f),
            django_form_models.ModelMultipleChoiceField: lambda f: [f.queryset.first().id],
            django_form_models.ModelChoiceField: lambda f: f.queryset.first().id,
            django_form_fields.BooleanField: True,
            django_form_fields.NullBooleanField: True,
            django_form_fields.MultipleChoiceField: lambda f: [list(f.choices)[-1][0]] if f.choices else ['{}'.format(f.label)],
            django_form_fields.URLField: lambda f: 'www.google.com',
            django_form_fields.DurationField: 1,
            django_form_fields.SplitDateTimeField: lambda f: [now().date(), now().time()],
            django_form_fields.GenericIPAddressField: '127.0.0.1',
            django_form_fields.FloatField: lambda f: cls.get_num_field_mock_value(f),
            gis_forms.PointField: 'POINT (0.1276 51.5072)',
            postgres_forms.HStoreField: '',
            postgres_forms.SimpleArrayField: lambda f: [cls.default_form_field_map()[f.base_field.__class__](f.base_field)],
            postgres_forms.DateTimeRangeField: lambda f: [now().strftime(list(f.input_formats)[-1]) if hasattr(f, 'input_formats') else now(), now().strftime(list(f.input_formats)[-1]) if hasattr(f, 'input_formats') else now()],
        }

        try:
            map.update({
                intflavor_countries.CountryFormField: 'LU',  # random.choice(UN_RECOGNIZED_COUNTRIES),
                intflavor_iban.IBANFormField: 'LU28 0019 4006 4475 0000',
                intflavor_vat.VATNumberFormField: lambda f: 'LU{}'.format(random.randint(10000000, 99999999)),  # 'GB904447273',
            })
        except NameError:
            pass

        try:
            map.update({django_form_fields.JSONField: ''})
        except AttributeError:
            # older django
            pass

        try:
            map.update({
                pragmatic.fields.AlwaysValidChoiceField: lambda f: list(f.choices)[-1][0] if f.choices else '{}'.format(f.label),
                pragmatic.fields.AlwaysValidMultipleChoiceField: lambda f: str(list(f.choices)[-1][0]) if f.choices else str(f.label),
                pragmatic.fields.SliderField: lambda f: '{},{}'.format(f.min, f.max) if f.has_range else str(f.min),
            })
        except NameError:
            # pragmatic not installed
            pass
        except AttributeError:
            # older django
            pass


        return map

    @property
    def url_params_map(self):
        '''{
            'accounts:user_list':{
                'params_1: {
                    'args': [],
                    'kwargs': {},
                    'cookies: {}, # dict or cookie str
                    'data': {},
                    'init_form_kwargs': {},
                    'form_kwargs': {},
                },
                'params_2': {} # passing empty dict behaves as if no params were specified, use to check also default behaviour besides specified params (params_1)
        }
        '''
        return {}

    @property
    def queryset_params_map(self):
        '''{
            'UserQuerySet: {
                'restrict_user': {},
            },
        }
        '''
        return {}

    @property
    def filter_params_map(self):
        '''{
            'UserFilterSet: {
                'filter_kwargs': {},
                'data': {},
                'queryset': User.objects.all(), # optional
            },
        }
        '''
        return {}


class BaseMixin(object):
    @classmethod
    def import_modules_if_needed(cls):
        '''
        import all modules encountered if some where not yet imported, for example when searching for models dependency or urls in source code
        '''
        module_names = cls.get_submodule_names(cls.CHECK_MODULES, cls.CHECK_MODULES, cls.EXCLUDE_MODULES)

        for module_name in module_names:
            try:
                if module_name not in sys.modules.keys():
                    importlib.import_module(module_name)
            except Exception as e:
                print('Failed to import module: {}'.format(module_name))
                raise e

    @classmethod
    def get_source_code(cls, modules, lines=True):
        module_names = sorted(cls.get_submodule_names(cls.CHECK_MODULES, modules, cls.EXCLUDE_MODULES))

        if lines:
            return OrderedDict(
                ((module_name, inspect.getsourcelines(sys.modules[module_name])) for module_name in module_names))

        return OrderedDict(((module_name, inspect.getsource(sys.modules[module_name])) for module_name in module_names))

    @classmethod
    def apps_to_check(cls):
        '''
        return all the apps to to be tested, or used to look for models dependency
        '''
        return [app for app in apps.get_app_configs() if app.name.startswith(tuple(cls.CHECK_MODULES))]

    @classmethod
    def get_module_class_methods(cls, module):
        classes = cls.get_module_classes(module)  # get not imported classes defined in module
        methods = set()

        for cls in classes:
            methods |= {value for value in cls.__dict__.values() if callable(value)}

        return methods

    @classmethod
    def get_module_classes(cls, module):
        '''
        returns only not imported classes defined in module
        '''
        return {m[1] for m in inspect.getmembers(module, inspect.isclass) if m[1].__module__ == module.__name__}

    @classmethod
    def get_module_functions(cls, module):
        '''
        returns only not imported functions defined in module
        '''
        return {m[1] for m in inspect.getmembers(module, inspect.isfunction) if m[1].__module__ == module.__name__}

    @classmethod
    def get_submodule_names(cls, parent_module_names, submodule_names, exclude_names=[]):
        '''
        looks for submodules of parent_module containing submodule_name and not containing any of exclude_names,
        which are not package (files, not dirs)
        '''
        module_names = set()

        if isinstance(parent_module_names, str):
            parent_module_names = [parent_module_names]

        if isinstance(submodule_names, str):
            submodule_names = [submodule_names]

        if isinstance(exclude_names, str):
            exclude_names = [exclude_names]

        for parent_module_name in parent_module_names:
            parent_module = sys.modules[parent_module_name]

            for importer, modname, ispkg in pkgutil.walk_packages(path=parent_module.__path__,
                                                                  prefix=parent_module.__name__ + '.',
                                                                  onerror=lambda x: None):

                for submodule_name in submodule_names:
                    if submodule_name in modname and not ispkg:
                        if not any([exclude_name in modname for exclude_name in exclude_names]):
                            module_names.add(modname)

        return (module_names)

    @classmethod
    def parse_args(cls, args, eval_args=True, eval_kwargs=True):
        '''
        parsing args and kwargs as specified
        '''
        args = 'f({})'.format(args)
        tree = ast.parse(args)
        funccall = tree.body[0].value

        if sys.version_info[0] >= 3:
            if eval_args:
                args = [ast.literal_eval(arg) for arg in funccall.args if ast.unparse(arg) != '*args']
            else:
                args = [ast.unparse(arg) for arg in funccall.args if ast.unparse(arg) != '*args']

            if eval_kwargs:
                kwargs = {arg.arg: ast.literal_eval(arg.value) for arg in funccall.keywords if arg.arg is not None}
            else:
                kwargs = {arg.arg: ast.unparse(arg.value) for arg in funccall.keywords if arg.arg is not None}
        else:
            if eval_args:
                args = [ast.literal_eval(arg) for arg in funccall.args if arg.id != '*args']
            else:
                args = [arg.elts if isinstance(arg, ast.List) else arg.id for arg in funccall.args if isinstance(arg, ast.List) or arg.id != '*args']

            if eval_kwargs:
                kwargs = {arg.arg: ast.literal_eval(arg.value) for arg in funccall.keywords if arg.arg is not None}
            else:
                kwargs = {arg.arg: arg.value.attr if isinstance(arg.value, ast.Attribute) else arg.value.s if isinstance(arg.value, ast.Str) else arg.value.id for arg in funccall.keywords if
                          arg.arg is not None}

        return args, kwargs

    @classmethod
    def generate_kwargs(cls, args=[], kwargs={}, func=None, default={}):
        # maching kwarg names with
        # 1. model names and assigns generated objs acordingly,
        # 2. field names of instance.model if exists such that instance.func
        models = {model._meta.label_lower.split('.')[-1]: model for model in cls.get_models()}
        result_kwargs = dict(default)

        try:
            for name, value in kwargs.items():
                if name in default:
                    # result_kwargs[name] = default[name]
                    pass
                elif name == 'email':
                    result_kwargs[name] = cls.get_generated_email()
                else:
                    matching_models = [model for model_name, model in models.items() if model_name == name]

                    if len(matching_models) == 1:
                        result_kwargs[name] = cls.get_generated_obj(matching_models[0])
                    elif not func is None:
                        model = None

                        if hasattr(func, 'im_self') and hasattr(func.im_self, 'model'):
                            model = func.im_self.model

                        if not model is None:
                            try:
                                result_kwargs[name] = getattr(cls.get_generated_obj(model), name)
                            except AttributeError:
                                pass

        except:
            raise
            kwargs = {}

        for arg in args:
            if arg in ['self', '*args', '**kwargs']:
                continue

            if arg in default:
                result_kwargs[arg] = default[arg]
            elif arg == 'email':
                result_kwargs[arg] = cls.get_generated_email()
            else:
                matching_models = [model for name, model in models.items() if name == arg]

                if len(matching_models) == 1:
                    result_kwargs[arg] = cls.get_generated_obj(matching_models[0])
                elif not func is None:
                    model = None

                    if hasattr(func, 'im_self') and hasattr(func.im_self, 'model'):
                        model = func.im_self.model

                    if not model is None:
                        try:
                            result_kwargs[arg] = getattr(cls.get_generated_obj(model), arg)
                        except AttributeError:
                            pass

        return result_kwargs

    @classmethod
    def generate_func_args(cls, func, default={}):
        source = inspect.getsource(func)
        args = r'([^\)]*)'
        args = re.findall('def {}\({}\):'.format(func.__name__, args), source)
        args = [args[0].replace(' *,', '')] # dont really get why would someone use this but it happened
        return cls.generate_kwargs(*cls.parse_args(args[0], eval_args=False, eval_kwargs=False), func=func, default=default)

    @classmethod
    def get_url_namespace_map(cls):
        resolver = urls.get_resolver(urls.get_urlconf())
        namespaces = {'': [key for key in resolver.reverse_dict.keys() if not callable(key)]}
        for key_1, resolver_1 in resolver.namespace_dict.items():
            namespaces[key_1] = [key for key in resolver_1[1].reverse_dict.keys() if not callable(key)]

            for key_2, resolver_2 in resolver_1[1].namespace_dict.items():
                namespaces['{}:{}'.format(key_1, key_2)] = [key for key in resolver_2[1].reverse_dict.keys() if not callable(key)]

                for key_3, resolver_3 in resolver_2[1].namespace_dict.items():
                    namespaces['{}:{}:{}'.format(key_1, key_2, key_3)] = [key for key in resolver_3[1].reverse_dict.keys() if
                                                              not callable(key)]

        return namespaces

    @classmethod
    def get_url_namespaces(cls):
        source_by_module = cls.get_source_code(['urls'], lines=False)
        namespace_map = OrderedDict()

        for module_name, source_code in source_by_module.items():
            regex_paths = re.findall(r'app_name=["\']([\w_]+)["\'], ?namespace=["\']([\w_]+)["\']', source_code)
            namespace_map.update({})


    @classmethod
    def get_url_views_by_module(cls):
        source_by_module = cls.get_source_code(['urls'], lines=False)
        paths_by_module = OrderedDict()

        skip_comments = r'([ \t]*#*[ \t]*)'
        pgettext_str = r'(?:pgettext_lazy\(["\']url["\'],)? ?'
        url_pattern_1 = r'["\'](.*)["\']'
        url_pattern_2 = r'r["\']\^(.*)\$["\']'
        url_pattern = '(?:{}|{})'.format(url_pattern_1, url_pattern_2)
        view_class = r'(\w+)'
        view_params = r'([^\)]*)'
        path_name = r'["\']([\w-]+)["\']'

        for module_name, source_code in source_by_module.items():
            regex_paths = re.findall(
                '{}(?:path|url)\({}{}\)?, ?{}.as_view\({}\), ?name={}'.format(skip_comments, pgettext_str, url_pattern, view_class, view_params, path_name),
                source_code)
            imported_classes = dict(inspect.getmembers(sys.modules[module_name], inspect.isclass))
            app_name = re.findall('app_name *= *\'(\w+)\'', source_code)

            if not app_name:
                app_name = [module_name.replace('.urls', '').split('.')[-1]]

            paths_by_module[module_name] = [{
                'app_name': app_name[0],
                'path_name': regex_path[5],
                'url_pattern': regex_path[1] if regex_path[1] else regex_path[2],
                'view_class': imported_classes.get(regex_path[3], None),
                'view_params': cls.parse_args(regex_path[4], eval_args=False, eval_kwargs=False),
            } for regex_path in regex_paths if '#' not in regex_path[0]]

        return paths_by_module

    @classmethod
    def get_apps_by_name(cls, app_name=[]):
        if isinstance(app_name, str):
            app_name = [app_name]

        return [app for app in apps.get_app_configs() if app.name.startswith(tuple(app_name))]

    @classmethod
    def get_models_from_app(cls, app):
        if isinstance(app, str):
            apps = cls.get_apps_by_name(app_name=app)

            if len(apps) > 1:
                raise ValueError('App name "{}" is ambiguous'.format(app))

            app = apps[0]

        return [model for model in app.get_models()]

    @classmethod
    def get_models(cls):
        models = [model for app in cls.apps_to_check() for model in app.get_models()]

        for module_name, module_params in cls.get_url_views_by_module().items():
            for path_params in module_params:
                model = getattr(path_params['view_class'], 'model', None)
                if model and model not in models:
                    models.append(model)

        proxied_models = [model._meta.concrete_model for model in models if model._meta.proxy]
        proxied_apps = {apps.get_app_config(model._meta.app_label) for model in proxied_models}

        for app in proxied_apps:
            models.extend([model for model in app.get_models() if model not in models])

        # add missing models manually provided
        if hasattr(cls, 'manual_model_dependency'):
            for model, dependencies in cls.manual_model_dependency().items():
                if model not in models:
                    models.append(model)

                for dependency in dependencies:
                    if dependency not in models:
                        models.append(dependency)

        return models

    @classmethod
    def get_models_with_required_fields(cls):
        return OrderedDict({
            model: [f for f in model._meta.get_fields() if
                    not getattr(f, 'blank', False) and f.concrete and not f.auto_created]
            for model in cls.get_models()
        })

    @classmethod
    def get_models_dependency(cls, required_only=True):
        models = cls.get_models()

        # find direct dependencies
        dependency = OrderedDict({
            model: {
                'required': {f.related_model for f in model._meta.get_fields()
                             if not getattr(f, 'blank', False) and isinstance(f,
                                                                              RelatedField) and f.concrete and not f.auto_created},
                'not_required': {} if required_only else {f.related_model for f in model._meta.get_fields()
                                                          if getattr(f, 'blank', False) and isinstance(f,
                                                                                                       RelatedField) and f.concrete and not f.auto_created},
            } for model in cls.get_models()
        })

        missing_models = set()

        for model, relations in dependency.items():
            missing_models |= relations['required']

        missing_models -= set(dependency.keys())
        missing_models -= {ContentType}

        # add missing models
        dependency.update({
            model: {
                'required': {f.related_model for f in model._meta.get_fields()
                             if not getattr(f, 'blank', False) and isinstance(f,
                                                                              RelatedField) and f.concrete and not f.auto_created},
                'not_required': {} if required_only else {f.related_model for f in model._meta.get_fields()
                                                          if getattr(f, 'blank', False) and isinstance(f,
                                                                                                       RelatedField) and f.concrete and not f.auto_created},
            } for model in missing_models
        })

        # add manualy set dependencies
        for model, relations in cls.manual_model_dependency().items():
            if relations:
                dependency[model]['required'] |= relations

        # add deeper level dependencies
        for i in range(2):
            # include 2nd and 3rd level dependencies, increase range to increase depth level
            for model in dependency.keys():
                for necesary_model in set(dependency[model]['required']):
                    if necesary_model in dependency.keys():
                        dependency[model]['required'] |= dependency[necesary_model]['required']

        return dependency

    @classmethod
    def get_sorted_models_dependency(cls, required_only=False, reverse=False):
        def compare_models_dependency(x, y):
            # less dependent first
            if x[0] in y[1]['required'] and y[0] in x[1]['required']:
                # circular required dependency should not happen
                raise ValueError('Circular dependency of models {}, {}'.format(x[0], y[0]))

            if x[0] in y[1]['required'] and y[0] not in x[1]['required']:
                # model y depends on x through required field, x < y
                return -1

            if x[0] not in y[1]['required'] and y[0] in x[1]['required']:
                # model x depends on y through required field, x > y
                return +1

            if x[0] in y[1]['not_required'] and y[0] not in x[1]['not_required']:
                # model y depends on x, x < y
                return -1

            if x[0] not in y[1]['not_required'] and y[0] in x[1]['not_required']:
                # model x depends on y, x > y
                return +1

            if len(x[1]['required']) < len(y[1]['required']):
                # model x doesnt require any model, y does
                return -1

            if len(x[1]['required']) > len(y[1]['required']):
                # model y doesnt require any model, x does
                return +1

            if len(x[1]['not_required']) < len(y[1]['not_required']):
                # model x  doesnt depend on any model, y does
                return -1

            if len(x[1]['not_required']) > len(y[1]['not_required']):
                # model y  doesnt depend on any model, x does
                return +1

            return 0

        # sort alphabetically for consistent initial order
        sorted_models = OrderedDict(sorted(cls.get_models_dependency(required_only).items(), key=lambda x: x[0]._meta.label, reverse=reverse))

        if sys.version_info[0] >= 3:
            # move manual dependencies to the beggining to force correct order (sort by dependencies is too ambiguous)
            for model, dependcies in cls.manual_model_dependency().items():
                for dependency in dependcies:
                    sorted_models.move_to_end(dependency, last=reverse)

        # sort by dependencies
        sorted_models = OrderedDict(sorted(sorted_models.items(), key=functools.cmp_to_key(compare_models_dependency), reverse=reverse))

        if cls.PRINT_SORTED_MODEL_DEPENDENCY:
            pprint(sorted_models)

        return sorted_models

    @classmethod
    def get_models_fields(cls, model, required=None, related=None):
        is_required = lambda f: not getattr(f, 'blank', False) if required is True else getattr(f, 'blank', False) if required is False else True
        is_related = lambda f: isinstance(f, RELATED_FIELDS) if related is True else not isinstance(f, RELATED_FIELDS) if related is False else True
        is_gm2m = lambda f: isinstance(f, GM2MField) if 'gm2m' in getattr(settings, 'INSTALLED_APPS') and related is True else False
        return [f for f in model._meta.get_fields() if (is_required(f) and is_related(f) and f.concrete and not f.auto_created) or (is_required(f) and is_gm2m(f))]


class GenericBaseMixin(InputMixin, BaseMixin):
    objs = OrderedDict()

    @classmethod
    def setUpTestData(cls):
        super(GenericBaseMixin, cls).setUpTestData()

        cls.import_modules_if_needed()
        cls.generate_objs()

    def setUp(self):
        user = self.objs.get('superuser', self.get_generated_obj(self.user_model()))
        credentials = {'password': self.TEST_PASSWORD}

        if hasattr(user, 'email'):
            credentials['email'] = user.email

        if hasattr(user, 'username'):
            credentials['username'] = user.username

        logged_in = self.client.login(**credentials)
        self.assertTrue(logged_in)
        self.user = user

    @classmethod
    def user_model(cls):
        '''
        User model used for login and permissions
        '''
        try:
            return cls.USER_MODEL
        except:
            return get_user_model()

    @classmethod
    def get_generated_email(cls, model=None):
        '''
        shortuct to get genrated email
        '''
        if model is None:
            model = cls.user_model()

        return cls.get_generated_obj(model).email

    @classmethod
    def get_new_email(cls):
        return 'email.{}@example.com'.format(random.randint(1, 999))

    @classmethod
    def get_mock_request(cls, **kwargs):
        return cls.get_request('/', **kwargs)

    @classmethod
    def get_request(cls, path='/', **kwargs):
        request = RequestFactory().get(path)

        for key, value in kwargs.items():
            setattr(request, key, value)

        return request

    @classmethod
    def get_response(cls, **kwargs):
        # return view_class.as_view(**view_kwargs)(request) response for request=RequestFactory.get() with additional request_attributes
        path = kwargs.get('path', '/')
        view_class = kwargs.get('view_class', None)
        view_kwargs = kwargs.get('view_kwargs', {})
        request_kwargs = kwargs.get('request_atrributes', {})

        if view_class is None:
            # get from urls.py
            raise ValueError('view_class not specified')

        request = cls.get_request(path, **request_kwargs)
        return view_class.as_view(**view_kwargs)(request)

    @classmethod
    def get_response_view(cls, **kwargs):
        response = cls.get_response(**kwargs)
        try:
            return response.context_data['view']
        except AttributeError:
            pass

        return response.context['view']

    @classmethod
    def get_response_view_as_filter_function(cls, **kwargs):
        # returns function for specific response view as function of filter kwargs in url,
        def filter_function(**filter_kargs):
            kwargs['path'] = kwargs.get('path', '/') + '?' + '&'.join(['{}={}'.format(key, value) for key, value in filter_kargs.items()])
            return cls.get_response_view(**kwargs)

        return filter_function

    @classmethod
    def generate_form_data(cls, form, default_data):
        """
        form should be an instance, not class
        """
        if inspect.isclass(form):
            raise ValueError('form should be an instance not class')

        data = {}

        for name, field in default_data.items():
            value = default_data[name]
            data[name] = value(cls) if callable(value) else value

        for name, field in form.fields.items():
            if name not in data and not isinstance(field, django_form_models.InlineForeignKeyField): # inline fk is is sued in inline formsets
                value = cls.default_form_field_map()[field.__class__]
                data[name] = value(field) if callable(value) else value

        return data

    @classmethod
    def generate_objs(cls):
        models_hierarchy = cls.get_sorted_models_dependency(required_only=False)
        generated_objs = OrderedDict()
        models = models_hierarchy.keys()

        for model in models:
            if model._meta.proxy:
                continue

            generated_objs[model] = cls.generate_model_objs(model)

        return generated_objs

    @classmethod
    def delete_ojbs(cls):
        models_hierarchy = cls.get_sorted_models_dependency(required_only=False, reverse=True)

        for model in models_hierarchy.keys():
            model.objects.all().delete()


    @classmethod
    def generate_model_field_values(cls, model, field_values={}):
        not_related_fields = cls.get_models_fields(model, related=False)
        related_fields = cls.get_models_fields(model, related=True)
        ignore_model_fields = cls.IGNORE_MODEL_FIELDS.get(model, [])
        field_values = dict(field_values)
        m2m_values = {}
        unique_fields = list(itertools.chain(*model._meta.unique_together))

        for field in not_related_fields:
            if field.name not in ignore_model_fields and field.name not in field_values and (not isinstance(field, ManyToManyField)):
                field_value = field.default

                if inspect.isclass(field.default) and issubclass(field.default, NOT_PROVIDED) or field.default is None or field_value in [list]:
                    field_value = cls.default_field_name_map().get(field.name, None)

                    if field_value is None:
                        field_value = cls.default_field_map().get(field.__class__, None)

                    if callable(field_value):
                        field_value = field_value(field)

                else:
                    if callable(field_value):
                        field_value = field_value()

                if field_value is None:
                    raise ValueError(
                        'Don\'t know ho to generate {}.{} value {}'.format(model._meta.label, field.name, field_value))

                if isinstance(field, CharField) and (field.name in unique_fields or field.unique) and not field.choices:
                    field_value = '{}_{}'.format(field_value, cls.next_id(model))

                field_values[field.name] = field.to_python(field_value) # to save default lazy values correctly, should not be problem in any case

        m2m_classes = (ManyToManyField, GM2MField) if 'gm2m' in getattr(settings, 'INSTALLED_APPS') else ManyToManyField

        for field in related_fields:
            if isinstance(field, m2m_classes):
                if field.name in field_values:
                    m2m_values[field.name] = field_values[field.name]
                    del field_values[field.name]
            elif field.name not in ignore_model_fields and field.name not in field_values and field.related_model.objects.exists():
                field_value = field.default

                if inspect.isclass(field.default) and issubclass(field.default,
                                                                 NOT_PROVIDED) or field.default is None:
                    field_value = cls.default_field_map().get(field.__class__, None)

                    if callable(field_value):
                        field_value = field_value(field)

                else:
                    if callable(field_value):
                        field_value = field_value()

                if field_value is None:
                    raise ValueError(
                        'Don\'t know ho to generate {}.{} value {}'.format(model._meta.label, field.name, field_value))

                field_values[field.name] = field_value

        return field_values, m2m_values

    @classmethod
    def generate_model_objs(cls, model):
        # required_fields = cls.get_models_fields(model, required_only=True)
        # related_fields = cls.get_models_fields(model, related_only=True)
        model_obj_values_map = cls.model_field_values_map().get(model, {cls.default_object_name(model): {}})
        new_objs = []

        for obj_name, obj_values in model_obj_values_map.items():
            obj = cls.objs.get(obj_name, None)

            if obj and obj._meta.model != model:
                obj_name = model._meta.label_lower
                obj = cls.objs.get(obj_name, None)

            if obj:
                try:
                    obj.refresh_from_db()
                except model.DoesNotExist:
                    obj = None

            if not obj:
                obj = cls.generate_obj(model, obj_values)
                new_objs.append(obj)
                cls.objs[obj_name] = obj

        return new_objs

    @classmethod
    def generate_obj(cls, model, field_values=None, **kwargs):
        '''
        generates and returns object for given model and field values,
        this method is used to generate every single object
        '''
        if field_values is None:
            # use kwargs for values if dict is not passed
            if not kwargs:
                field_values = {}
            else:
                field_values = kwargs

        field_values = field_values(cls) if callable(field_values) else field_values
        field_values, m2m_values = cls.generate_model_field_values(model, field_values)
        post_save = field_values.pop('post_save', [])

        if model == cls.user_model():
            if hasattr(cls, 'create_user'):
                obj = cls.create_user(**field_values)
            else:
                obj = getattr(model._default_manager, 'create_user')(**field_values)
        else:

            try:
                with transaction.atomic():
                    obj = getattr(model._default_manager, 'create')(**field_values)
            except Exception as e:
                obj = model(**field_values)
                obj.save()

        for m2m_attr, m2m_value in m2m_values.items():
            getattr(obj, m2m_attr).set(m2m_value)

        for action in post_save:
            action(obj)

        return obj

    @classmethod
    def default_object_name(cls, model):
        # app_name, default_name = model._meta.label.split('.')
        # default_name = re.findall(r'.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', default_name)
        # default_name = '_'.join(default_name).lower()
        return model._meta.label_lower.split('.')[-1]

    @classmethod
    def get_generated_obj(cls, model=None, obj_name=None):
        '''
        returns already generated object of given model and/or obj_name if exists otherwise generates first
        '''
        if model is None and obj_name is None:
            raise Exception('At least one argument is necessary')

        if obj_name is None:
            if model._meta.proxy:
                model = model._meta.concrete_model

            if model in cls.model_field_values_map().keys():
                if model == cls.user_model() and 'superuser' in cls.model_field_values_map()[model].keys():
                    obj_name = 'superuser'
                elif isinstance(cls.model_field_values_map()[model], OrderedDict):
                    obj_name = list(cls.model_field_values_map()[model].keys())[0]
                else:
                    obj_name = sorted(list(cls.model_field_values_map()[model].keys()))[0]

            if obj_name not in cls.objs.keys():
                obj_name = cls.default_object_name(model)

        obj = cls.objs.get(obj_name, None)

        if obj:
            model = obj._meta.model

            try:
                obj.refresh_from_db()
            except model.DoesNotExist:
                obj = None

        if not obj:
            if model is None:
                for obj_model, objs in cls.model_field_values_map().items():
                    if obj_name in objs.keys():
                        model = obj_model
                        break

            cls.generate_model_objs(model)
            obj = cls.objs.get(obj_name, None)

        if not obj:
            if obj_name:
                raise Exception('{} object with name {} doesn\'t exist'.format(model, obj_name))

            raise Exception('Something\'s fucked')

        return obj
        # return cls.objs.get(obj_name, model.objects.first())

    @classmethod
    def next_id(cls, model):
        '''
        returns last existing id + 1
        '''
        last = model.objects.order_by('id').last()
        return last.id + 1 if last else 0

    @classmethod
    def get_pdf_file_mock(cls, name='test.pdf'):
        file_path = os.path.join(os.path.dirname(__file__), 'blank.pdf')
        file = open(file_path, 'rb')
        file_mock = SimpleUploadedFile(
            name,
            file.read(),
            content_type='application/pdf'
        )
        return file_mock

    @classmethod
    def get_image_file_mock(cls, name='test.jpg', file_path=None):
        if file_path is None:
            file_path = os.path.join(os.path.dirname(__file__), 'blank.jpg')
        file = open(file_path, 'rb')
        file_mock = SimpleUploadedFile(
            name,
            file.read(),
            content_type='image/png'
        )
        return file_mock

    @classmethod
    def get_num_field_mock_value(cls, field):
        if field.validators:
            if len(field.validators) == 2 \
                    and isinstance(field.validators[0], (MinValueValidator, MaxValueValidator)) \
                    and isinstance(field.validators[1], (MinValueValidator, MaxValueValidator)):
                # value = (field.validators[0].limit_value + field.validators[1].limit_value) / 2
                value = random.randint(*sorted([validator.limit_value for validator in field.validators]))
                if isinstance(field, IntegerField):
                    return int(value)

                return value

            validator = field.validators[0]

            if isinstance(validator, MinValueValidator):
                # return validator.limit_value + 1
                limit_value = int(validator.limit_value)
                return random.randint(limit_value, limit_value + 9)

            if isinstance(validator, MaxValueValidator):
                # return validator.limit_value - 1
                limit_value = int(validator.limit_value)
                return random.randint(1, limit_value)

        return random.randint(1, 9)

    @classmethod
    def print_last_fail(cls, failed):
        for k, v in failed[-1].items():
            print(k)
            print(v)

    @classmethod
    def create_formset_post_data(cls, response, post_data={}):
        post_data = dict(**post_data)

        if not hasattr(response, 'context'):
            return post_data

        formset_keys = [key for key in response.context.keys() if 'formset' in key and response.context[key]]

        for formset_key in formset_keys:
            formset = response.context[formset_key]
            # prefix_template = formset.empty_form.prefix # default is 'form-__prefix__'
            prefix = '{}-'.format(formset.prefix)
            # extract initial formset data
            management_form_data = formset.management_form.initial

            # add properly prefixed management form fields
            for key, value in management_form_data.items():
                # prefix = prefix_template.replace('__prefix__', '')
                post_data[prefix + key] = value

            # generate individual forms data
            for index, form in enumerate(formset.forms):
                form_prefix = '{}{}-'.format(prefix, index)
                default_form_data = {key.replace(form_prefix, ''): value for key, value in post_data.items() if key.startswith(form_prefix)}
                post_data.update({'{}{}'.format(form_prefix, key): value for key, value in cls.generate_form_data(form, default_form_data).items()})

        return post_data


class QuerysetTestMixin(object):
    def test_querysets(self):
        models_querysets = [model._default_manager.all() for model in self.get_models()]
        failed = []

        for qs in models_querysets:
            qs_class = qs.__class__

            if not qs_class == QuerySet and not any([exclude_module in qs_class.__module__ for exclude_module in self.EXCLUDE_MODULES]):
                qs_class_label = qs_class.__name__
                queryset_methods = [(name, func) for name, func in qs_class.__dict__.items()
                                    if not name.startswith('_')
                                    and name != 'mro'
                                    and inspect.isfunction(func)]

                params_map = self.queryset_params_map.get(qs_class, {})

                for name, func in queryset_methods:
                    if self.PRINT_TEST_SUBJECT:
                        print('{}.{}'.format(qs_class_label, name))

                    result = None
                    kwargs = {}

                    if name in params_map:
                        # provided arguments
                        kwargs = params_map[name]

                        try:
                            result = getattr(qs, name)(**kwargs)
                        except Exception as e:
                            failed.append([{
                                'location': 'DEFAULT KWARGS',
                                'model': qs.model,
                                'queryset method': '{}.{}'.format(qs_class_label, name),
                                'kwargs': kwargs,
                                'traceback': traceback.format_exc(),
                            }])
                    elif func.__code__.co_argcount == 1:
                        # no arguments except self
                        try:
                            result = getattr(qs, name)()
                        except Exception as e:
                            failed.append([{
                                'location': 'NO KWARGS',
                                'model': qs.model,
                                'queryset method': '{}.{}'.format(qs_class_label, name),
                                'traceback': traceback.format_exc(),
                            }])
                    else:
                        func = getattr(qs, name)

                        try:
                            kwargs = self.generate_func_args(func)
                        except Exception as e:
                            failed.append([{
                                'location': 'GENERATING KWARGS',
                                'model': qs.model,
                                'queryset method': '{}.{}'.format(qs_class_label, name),
                                'traceback': traceback.format_exc(),
                            }])
                        else:
                            try:
                                result = getattr(qs, name)(**kwargs)
                            except Exception as e:
                                failed.append([{
                                    'location': 'GENERATED KWARGS',
                                    'model': qs.model,
                                    'queryset method': '{}.{}'.format(qs_class_label, name),
                                    'kwargs': kwargs,
                                    'traceback': traceback.format_exc(),
                                }])

        if failed:
            failed.append('{} qeuryset methods FAILED'.format(len(failed)))

        self.assertFalse(failed, msg=pformat(failed, indent=4))


class FilterTestMixin(object):
    def test_filters(self):
        module_names = self.get_submodule_names(self.CHECK_MODULES, ['filters', 'forms'], self.EXCLUDE_MODULES)
        filter_classes = set()
        failed = []

        # get filter classes
        for module_name in module_names:
            module = sys.modules[module_name]

            filter_classes |= {
                cls for cls in self.get_module_classes(module) if issubclass(cls, (FilterSet,))
            }

        filter_classes = sorted(filter_classes, key=lambda x: x.__name__)

        for i, filter_class in enumerate(filter_classes):
            if self.PRINT_TEST_SUBJECT:
                print(filter_class)

            params_maps = self.filter_params_map.get(filter_class, {'default': {}})

            for map_name, params_map in params_maps.items():
                filter_kwargs = self.generate_func_args(filter_class.__init__, params_map.get('filter_kwargs', {}))

                try:
                    filter = filter_class(**filter_kwargs)
                except:
                    failed.append(OrderedDict({
                        'location': 'FILTER INIT',
                        'filter class': filter_class,
                        'filter_kwargs': filter_kwargs,
                        'params map': params_map,
                        'traceback': traceback.format_exc()
                    }))
                    continue

                query_dict_data = QueryDict('', mutable=True)

                try:
                    query_dict_data.update(self.generate_form_data(filter.form, params_map.get('data', {})))
                except:
                    failed.append(OrderedDict({
                        'location': 'FILTER DATA',
                        'filter class': filter_class,
                        'data': query_dict_data,
                        'params map': params_map,
                        'traceback': traceback.format_exc()
                    }))

                try:
                    queryset = filter_kwargs.get('queryset', filter_class._meta.model._default_manager.all() if filter_class._meta.model else None)
                except Exception as e:
                    failed.append(OrderedDict({
                        'location': 'FILTER QUERYSET',
                        'filter class': filter_class,
                        'params map': params_map,
                        'traceback': traceback.format_exc()
                    }))
                    continue

                if queryset:
                    filter_kwargs['queryset'] = queryset

                try:
                    filter = filter_class(data=query_dict_data, **filter_kwargs)
                    qs = filter.qs.all().values()
                except Exception as e:
                    failed.append(OrderedDict({
                        'location': 'FILTER',
                        'filter class': filter_class,
                        'data': query_dict_data,
                        'queryset': queryset,
                        'params map': params_map,
                        'traceback': traceback.format_exc()
                    }))
                    continue

        if failed:
            failed.append('{} filters FAILED'.format(len(failed)))

        self.assertFalse(failed, msg=pformat(failed, indent=4))


class UrlMixin(object):
    default_url_params = {}

    @classmethod
    def crawl_urls_with_action(cls, urls, action, parent_pattern='', parent_namespace='', parent_app_name='', filter_namespace=None, exclude_namespace=None, filter_app_name=None, exclude_app_name=None, target_attr='_urls'):
        if isinstance(urls, URLResolver):
            urls = urls.url_patterns

        for url in urls:
            if isinstance(url, URLResolver):
                if (exclude_namespace is not None and exclude_namespace == url.namespace) or (
                        exclude_app_name is not None and exclude_app_name == url.app_name):
                    continue

                # if cls.PRINT_TEST_SUBJECT and (filter_namespace is None or filter_namespace == url.namespace) and (
                #         filter_app_name is None or filter_app_name == url.app_name):
                #     print('NAMESPACE', url.namespace, type(url.namespace), 'APP_NAME', url.app_name)

                cls.crawl_urls_with_action(url, action, f'{parent_pattern}{url.pattern}',
                                           f"{parent_namespace}:{url.namespace or ''}",
                                           f"{parent_app_name}:{url.app_name or ''}",
                                           filter_namespace, exclude_namespace, filter_app_name, exclude_app_name, target_attr)

            elif isinstance(url, URLPattern):
                # print(if_none(parent_pattern) + str(url.pattern))
                if (filter_namespace is None or filter_namespace in parent_namespace) and (
                        filter_app_name is None or filter_app_name in parent_app_name):
                    # print(url.__dict__.keys(), url.callback.__dict__)
                    action(
                        url=url,
                        pattern=f'{parent_pattern}{url.pattern}',
                        url_name=cls.get_url_name(url, parent_namespace.strip(':')),
                        target_attr=target_attr,
                    )

    @classmethod
    def get_url_name(cls, url, parent_namespace):
        url_name = f"{parent_namespace}:{url.name or ''}"
        url_name = url_name.strip(':')
        return url_name

    @classmethod
    def get_urls_from_excluded_modules(cls):
        for module_name in cls.EXCLUDE_MODULES:
            module_urls_name = f"{module_name}.urls"
            try:
                if module_urls_name not in sys.modules.keys():
                    urls_module = importlib.import_module(module_urls_name)
                else:
                    urls_module = sys.modules[module_urls_name]

            except ModuleNotFoundError:
                print(f"No urls.py found for app '{module_name}'")
            else:
                urlpatterns = getattr(urls_module, "urlpatterns", [])
                cls.crawl_urls_with_action(urlpatterns, cls.collect_url_name, target_attr='_exclude_urls')

        return cls._exclude_urls

    @classmethod
    def collect_url_name(cls, **kwargs):
        url_name = kwargs['url_name']
        target_attr = kwargs['target_attr']

        getattr(cls, target_attr).append(url_name)

    def crawl_urls(self, urls, parent_pattern='', parent_namespace='', parent_app_name='', filter_namespace=None, exclude_namespace=None, filter_app_name=None, exclude_app_name=None):
        return self.crawl_urls_with_action(urls, self.crawl_test_url, parent_pattern, parent_namespace, parent_app_name, filter_namespace, exclude_namespace, filter_app_name, exclude_app_name)

    def crawl_test_url(self, **kwargs):
        url = kwargs['url']
        url_name = kwargs['url_name']
        pattern = kwargs['pattern']

        args = re.findall(r'<([:\w]+)>', pattern)

        if hasattr(url.callback, 'view_class'):
            view_class = url.callback.view_class
            view_initkwargs = url.callback.view_initkwargs
        elif hasattr(url.callback, 'cls'):
            # rest api generated views
            view_class = url.callback.cls
            view_initkwargs = {}
        else:
            # api root
            # print(f'{if_none(pattern)}:{if_none(url.name)}', url.callback.__dict__)
            return

        if not url_name or self.skip_url(url_name):
            return

        path_params = {
            'path_name': url_name,
            'args': args,
            'url_pattern': pattern,
            'view_class': view_class,
            'view_params': ([], view_initkwargs),  # self.parse_args(view_initkwargs, eval_args=False, eval_kwargs=False),
        }

        if self.PRINT_TEST_SUBJECT:
            print(path_params)

        self.tested.append(path_params)
        params_maps = self.url_params_map.get(url_name, {'default': self.default_url_params})

        for map_name, params_map in params_maps.items():
            parsed_args = params_map.get('args', None)

            if len(params_maps) > 1 and parsed_args is not None and len(args) != len(parsed_args):
                # when there are mmultiple params maps provided match by arguments length
                continue

            path, parsed_kwargs, fails = self.prepare_url(url_name, path_params, params_map, self.models, self.model_fields)
            parsed_args = parsed_kwargs.values()

            if fails:
                self.failed.extend(fails)
                continue

            # set cookies
            cookies = params_map.get('cookies', None)

            if cookies is not None:
                initial_cookies = self.client.cookies
                self.client.cookies.load(cookies)

            # set permissions
            permissions = params_map.get('permissions', None)

            if permissions is not None:
                initial_permissions = self.user.user_permissions.all().values('id')

                for permission in permissions:
                    if permission == 'is_superuser':
                        self.user.is_superuser = True
                        self.user.save(update_fields=['is_superuser'])
                    else:
                        app_label, codename = permission.split('.')
                        permission = Permission.objects.get(content_type__app_label=app_label, codename=codename)
                        self.user.user_permissions.add(permission)

            # GET url
            if hasattr(view_class, 'get') and not url_name in self.POST_ONLY_URLS:
                get_response, fails = self.get_url_test(url_name, path, parsed_args, pattern, view_class, params_map)

                if fails:
                    self.failed.extend(fails)
                    continue
            else:
                get_response = Response()

            # POST url
            if hasattr(view_class, 'post') and url_name not in self.GET_ONLY_URLS and getattr(view_class, 'form_class', None):
                fails = self.post_url_test(url_name, path, parsed_args, pattern, view_class, params_map, get_response)

                if fails:
                    self.failed.extend(fails)
                    continue

            # reset cookies
            if cookies is not None:
                self.client.cookies = initial_cookies

            # reset permissions
            if permissions is not None:
                self.user.user_permissions.set(Permission.objects.filter(id__in=initial_permissions))

    def prepare_url(self, path_name, path_params, params_map, models, fields):
        '''
        generates url arguments if not provided, saves them in params_map['parsed'],
        returns url with args and list of fail messages
        '''
        fails = []
        path = path_name
        url_pattern = path_params['url_pattern']
        args = path_params['args']
        arg_names = [arg.split(':')[1] if ':' in arg else arg for arg in args]
        view_class = path_params['view_class']
        parsed_args = params_map.get('args', None)
        parsed_kwargs = params_map.get('url_kwargs', None)

        if parsed_args is None or not args:
            parsed_args = []

        if parsed_kwargs is None:
            parsed_kwargs = {arg: value for arg, value in zip(arg_names, parsed_args)}
        else:
            parsed_kwargs = {key: value for key, value in parsed_kwargs.items() if key in arg_names}

        if args and set(parsed_kwargs.keys()) != set(arg_names):
            params_map['parsed'] = []
            # parse args from path params
            view_model = None

            if getattr(view_class, 'model', None):
                view_model = view_class.model
            elif getattr(view_class, 'queryset', None):
                view_model = view_class.queryset.model
            else:
                matching_models = [model for model in models if path_name.split(':')[-1].startswith(model._meta.label_lower.split(".")[-1])]

                if len(matching_models) == 1:
                    view_model = matching_models[0]

            for arg in args:
                arg_type, arg_name = arg.split(':') if ':' in arg else ('int', arg)

                if arg_name in parsed_kwargs:
                    continue

                matching_fields = []

                if arg in ['int:pk', 'pk']:
                    matching_fields = [('pk', view_model)]
                else:
                    if arg_type not in ['int', 'str', 'slug']:
                        fails.append(OrderedDict({
                            'location': 'URL ARG TYPE',
                            'url name': path_name,
                            'url pattern': url_pattern,
                            'arg': arg,
                            'traceback': 'Cant handle this arg type'
                        }))
                        continue

                    if arg_name.endswith('_pk'):
                        # model name
                        matching_fields = [('pk', model) for model in models if
                                           arg_name == '{}_pk'.format(model._meta.label_lower.split(".")[-1])]

                        if len(matching_fields) != 1:
                            # match field  model
                            matching_fields = [('pk', model) for model in models if arg_name == '{}_pk'.format(
                                model._meta.verbose_name.lower().replace(' ', '_'))]

                    else:
                        # full name and type match
                        matching_fields = [(field, model) for field, model in fields if
                                           field.name == arg_name and isinstance(field, IntegerField if arg_type == 'int' else (
                                           CharField, BooleanField))]

                        if len(matching_fields) > 1:
                            # match field  model
                            matching_fields = [(field, model) for field, model in matching_fields if
                                               model == view_model]

                        elif not matching_fields:
                            # full name match
                            matching_fields = [(field, model) for field, model in fields if
                                               field.name == arg_name and not model._meta.proxy]

                            if not matching_fields:
                                # match name in form model_field to model and field
                                matching_fields = [(field, model) for field, model in fields if
                                                   arg_name == '{}_{}'.format(model._meta.label_lower.split(".")[-1],
                                                                          field.name)]

                            if not matching_fields:
                                # this might make problems as only partial match is made
                                matching_fields = [(p[0], view_model) for p in
                                                   inspect.getmembers(view_model, lambda o: isinstance(o, property)) if
                                                   p[0].startswith(arg_name)]

                            if not matching_fields:
                                # name is contained in field.name of view model
                                matching_fields = [(field, model) for field, model in fields if
                                                   model == view_model and arg_name in field.name]

                if len(matching_fields) != 1 or matching_fields[0][1] is None:
                    fails.append(OrderedDict({
                        'location': 'URL ARG MATCH',
                        'url name': path_name,
                        'url pattern': url_pattern,
                        'arg': arg,
                        'matching fields': matching_fields,
                        'traceback': 'Url arg mathcing failed'
                    }))
                    continue

                attr_name, model = matching_fields[0]

                if not isinstance(attr_name, str):
                    # its Field object
                    attr_name = attr_name.name

                obj = self.get_generated_obj(model)

                if obj is None:
                    obj = self.generate_model_objs(model)

                obj = self.get_generated_obj(model)
                arg_value = getattr(obj, attr_name, None)

                if arg_value in [True, False]:
                    arg_value = str(arg_value)

                if arg_value is None:
                    fails.append(OrderedDict({
                        'location': 'URL ARG PARSE',
                        'url name': path_name,
                        'url pattern': url_pattern,
                        'arg': arg,
                        'parsed arg': arg_value,
                        'traceback': 'Url arg parsing failed'
                    }))
                    continue

                parsed_kwargs[arg_name] = arg_value
                params_map['parsed'].append({'obj': obj, 'attr_name': attr_name, 'value': arg_value})


        if set(arg_names) != set(parsed_kwargs.keys()):
            fails.append(OrderedDict({
                'location': 'URL ARGS PARSED',
                'url name': path_name,
                'url pattern': url_pattern,
                'args': args,
                'parsed args': parsed_kwargs,
                'traceback': 'Url args parsing failed'
            }))
        else:
            path = reverse(path_name, kwargs=parsed_kwargs)
            request_kwargs = params_map.get('request_kwargs', {})

            if request_kwargs:
                request_kwargs = '&'.join([f'{key}={value}' for key, value in request_kwargs.items()])
                path = f'{path}?{request_kwargs}'

        return path, parsed_kwargs, fails

    @classmethod
    def skip_url(cls, url_name):
        if cls.RUN_ONLY_THESE_URL_NAMES and url_name not in cls.RUN_ONLY_THESE_URL_NAMES:
            # print('SKIP')
            return True

        if cls.RUN_ONLY_URL_NAMES_CONTAINING and not any(
                (substr in url_name for substr in cls.RUN_ONLY_URL_NAMES_CONTAINING)):
            # print('SKIP')
            return True

        if cls.IGNORE_URL_NAMES_CONTAINING and any((substr in url_name for substr in cls.IGNORE_URL_NAMES_CONTAINING)):
            # print('SKIP')
            return True

        return False

    def get_url_test(self, path_name, path, parsed_args, url_pattern, view_class, params_map):
        fails = []
        data = params_map.get('data', {})

        try:
            get_response = self.client.get(path=path, data=data, follow=True)
            self.assertEqual(get_response.status_code, 200)
        except Exception as e:
            fails.append(OrderedDict({
                'location': 'GET',
                'url name': path_name,
                'url': path,
                'url pattern': url_pattern,
                'parsed args': parsed_args,
                'view class': view_class,
                'traceback': traceback.format_exc()
            }))
            return None, fails

        if hasattr(view_class, 'sorting_options'):  # and isinstance(view_class.sorting_options, dict):
            sorting_options = params_map.get('sorting_options', [])

            if not sorting_options:
                sorting_options = view_class.sorting_options.keys()

            for sorting in sorting_options:
                data['sorting'] = sorting

                try:
                    response = self.client.get(path=path, data=data, follow=True)
                    self.assertEqual(response.status_code, 200)
                except Exception as e:
                    fails.append(OrderedDict({
                        'location': 'SORTING',
                        'url name': path_name,
                        'url': path,
                        'url pattern': url_pattern,
                        'parsed args': parsed_args,
                        'data': data,
                        'traceback': traceback.format_exc()
                    }))

        if hasattr(view_class, 'displays'):
            displays = params_map.get('displays', view_class.displays)

            for display in displays:
                data['display'] = display

                try:
                    response = self.client.get(path=path, data=data, follow=True)
                    self.assertEqual(response.status_code, 200)
                except Exception as e:
                    fails.append(OrderedDict({
                        'location': 'DISPLAY',
                        'url name': path_name,
                        'url': path,
                        'url pattern': url_pattern,
                        'parsed args': parsed_args,
                        'data': data,
                        'traceback': traceback.format_exc()
                    }))
                else:
                    if not hasattr(view_class, 'template_name') and hasattr(response, 'template_name'):
                        template = response.template_name[-1] if isinstance(response.template_name,
                                                                            list) else response.template_name

                        try:
                            self.assertTrue(template.endswith('{}.html'.format(display)))
                        except Exception as e:
                            fails.append(OrderedDict({
                                'location': 'TEMPLATE',
                                'url name': path_name,
                                'url': path,
                                'url pattern': url_pattern,
                                'parsed args': parsed_args,
                                'data': data,
                                'template': template,
                                'traceback': traceback.format_exc()
                            }))
        return get_response, fails

    def post_url_test(self, path_name, path, parsed_args, url_pattern, view_class, params_map, get_response):
        fails = []
        data = params_map.get('data', {})

        try:
            with transaction.atomic():
                form_class = view_class.form_class
                view_model = None

                if hasattr(form_class, '_meta') and getattr(form_class._meta, 'model', None):
                    view_model = form_class._meta.model
                elif getattr(form_class, 'model', None):
                    view_model = form_class.model
                elif getattr(view_class, 'model', None):
                    view_model = view_class.model
                elif getattr(view_class, 'queryset', None):
                    view_model = view_class.queryset.model

                # view_model = view_class.model if hasattr(view_class, 'model') else form_class.model if hasattr(
                #     form_class, 'model') else None
                # refactor form kwargs?
                form_kwargs = self.generate_func_args(form_class.__init__, params_map.get('form_kwargs', {}))
                form_kwargs = {key: value(self) if callable(value) else value for key, value in form_kwargs.items()}
                form_kwargs['data'] = data
                form = None

                if path_name not in self.POST_ONLY_URLS and hasattr(get_response, 'context') and 'form' in get_response.context:
                    form = get_response.context['form']
                else:
                    try:
                        form = form_class(**form_kwargs)
                    except Exception as e:
                        if not isinstance(form, form_class) or not hasattr(form, 'fields'):
                            # as long as there is form instance with fields its enough to generate data
                            fails.append(OrderedDict({
                                'location': 'POST FORM INIT',
                                'url name': path_name,
                                'url': path,
                                'url pattern': url_pattern,
                                'parsed args': parsed_args,
                                'form class': form_class,
                                'form kwargs': form_kwargs,
                                'traceback': traceback.format_exc()
                            }))
                            return fails

                query_dict_data = QueryDict('', mutable=True)

                try:
                    query_dict_data.update(self.generate_form_data(form, data))
                except Exception as e:
                    fails.append(OrderedDict({
                        'location': 'POST GENERATING FORM DATA',
                        'url name': path_name,
                        'url': path,
                        'url pattern': url_pattern,
                        'parsed args': parsed_args,
                        'form class': form_class,
                        'default form data': data,
                        'traceback': traceback.format_exc()
                    }))
                    return fails

                if not view_model:
                    return fails

                form_kwargs['data'] = query_dict_data
                obj_count_before = 0

                if issubclass(view_class, (CreateView, UpdateView, DeleteView)):
                    obj_count_before = view_model.objects.all().count()

                try:
                    response = self.client.post(path=path, data=form_kwargs['data'], follow=True)
                    self.assertEqual(response.status_code, 200)
                except ValidationError as e:
                    if e.message == _('ManagementForm data is missing or has been tampered with'):
                        post_data = QueryDict('', mutable=True)

                        try:
                            post_data.update(self.create_formset_post_data(get_response, data))
                        except Exception as e:
                            fails.append(OrderedDict({
                                'location': 'POST GENERATING FORMSET DATA',
                                'url name': path_name,
                                'url': path,
                                'url pattern': url_pattern,
                                'parsed args': parsed_args,
                                'form class': form_class,
                                'default form data': data,
                                'post data': post_data,
                                'traceback': traceback.format_exc()
                            }))
                            return fails

                        try:
                            response = self.client.post(path=path, data=post_data, follow=True)
                            self.assertEqual(response.status_code, 200)
                        except Exception as e:
                            fails.append(OrderedDict({
                                'location': 'POST FORMSET',
                                'url name': path_name,
                                'url': path,
                                'url pattern': url_pattern,
                                'parsed args': parsed_args,
                                'form class': form_class,
                                'data': form_kwargs['data'],
                                'post data': post_data,
                                'form': form,
                                'traceback': traceback.format_exc()
                            }))
                            return fails
                    else:
                        fails.append(OrderedDict({
                            'location': 'POST',
                            'url name': path_name,
                            'url': path,
                            'url pattern': url_pattern,
                            'parsed args': parsed_args,
                            'form class': form_class,
                            'data': form_kwargs['data'],
                            'form': form,
                            'traceback': traceback.format_exc()
                        }))
                        return fails

                except Exception as e:
                    fails.append(OrderedDict({
                        'location': 'POST',
                        'url name': path_name,
                        'url': path,
                        'url pattern': url_pattern,
                        'parsed args': parsed_args,
                        'form class': form_class,
                        'data': form_kwargs['data'],
                        'form': form,
                        'traceback': traceback.format_exc()
                    }))
                    return fails

                if issubclass(view_class, (CreateView, UpdateView, DeleteView)):
                    obj_count_after = view_model.objects.all().count()

                    try:
                        if issubclass(view_class, CreateView):
                            self.assertEqual(obj_count_after, obj_count_before + 1)
                        elif issubclass(view_class, UpdateView):
                            self.assertEqual(obj_count_after, obj_count_before)
                        elif issubclass(view_class, DeleteView):
                            self.assertEqual(obj_count_after, obj_count_before - 1)
                            # recreate obj is not necessary because of transaction rollback

                    except Exception as e:
                        form = response.context.get('form', None)
                        errors = [form.errors if form else None]
                        is_valid = [form.is_valid() if form else None]
                        formset_keys = [key for key in response.context.keys() if 'formset' in key and response.context[key]]

                        for formset_key in formset_keys:
                            formset = response.context[formset_key]

                            if hasattr(formset, 'is_valid'):
                                is_valid.append((formset_key, formset.is_valid()))

                                for extra_form in formset.forms:
                                    errors.append(extra_form.errors)

                        fails.append(OrderedDict({
                            'location': 'POST COUNT',
                            'url name': path_name,
                            'url': path,
                            'url pattern': url_pattern,
                            'parsed args': parsed_args,
                            'view model': view_model,
                            'form class': form_class,
                            # 'form': form,
                            'form valid': is_valid,
                            'form errors': errors,
                            'data': form_kwargs['data'],
                            'traceback': traceback.format_exc()
                        }))
                        return fails

                # rollback post action
                raise IntegrityError('No problem')

        except IntegrityError as e:
            if e.args[0] != 'No problem':
                raise
        except Exception:
            raise

        return fails


class UrlTestMixin(UrlMixin):
    def test_urls(self):
        self.models = self.get_models()
        self.model_fields = [(f, model) for model in self.models for f in model._meta.get_fields() if f.concrete and not f.auto_created]
        self.failed = []
        self.tested = []

        urls = get_resolver()
        self.crawl_urls(urls)

        if self.failed:
            # append failed count at the end of error list
            self.failed.append('{}/{} urls FAILED: {}'.format(len(self.failed), len(self.tested), ', '.join([f['url name'] for f in self.failed])))

        self.assertFalse(self.failed, msg=pformat(self.failed, indent=4))


class DynamicUrlTestMixin(UrlMixin):
    # uses dynamic urls splitting and tests need to be generated with generate_url_tests
    _urls=[]
    _exclude_urls=[]

    @classmethod
    def collect_urls_in_chunks(cls, num_tests=3, urls=None, *args, **kwargs):
        if urls is None:
            urls = get_resolver()

        cls.collect_urls(urls, *args, **kwargs)
        return cls.chunkify(cls._urls, num_tests)

    @staticmethod
    def chunkify(lst, num_chunks):
        """
        Split a list into `num_chunks` parts as evenly as possible.
        """
        chunk_length = - (len(lst) // - float(num_chunks))  # Round up division
        chunks = []
        last = 0

        while last < len(lst):
            chunks.append(lst[int(last):int(last + chunk_length)])
            last += chunk_length

        return chunks

    @classmethod
    def collect_urls(cls, urls, parent_pattern='', parent_namespace='', parent_app_name='', filter_namespace=None, exclude_namespace=None, filter_app_name=None, exclude_app_name=None, target_attr='_urls'):
        if cls.EXCLUDE_MODULES and not cls._exclude_urls:
            cls.get_urls_from_excluded_modules()

        cls.crawl_urls_with_action(urls, cls.collect_url, parent_pattern, parent_namespace, parent_app_name, filter_namespace, exclude_namespace, filter_app_name, exclude_app_name, target_attr)
        return getattr(cls, target_attr)

    @classmethod
    def collect_url(cls, **kwargs):
        url = kwargs['url']
        url_name = kwargs['url_name']
        pattern = kwargs['pattern']
        target_attr = kwargs['target_attr']

        if not hasattr(cls, target_attr):
            setattr(cls, target_attr, [])

        if hasattr(url.callback, 'view_class'):
            view_class = url.callback.view_class
            view_initkwargs = url.callback.view_initkwargs
        elif hasattr(url.callback, 'cls'):
            # rest api generated views
            view_class = url.callback.cls
            view_initkwargs = {}
        else:
            # api root
            # print(f'{if_none(pattern)}:{if_none(url.name)}', url.callback.__dict__)
            return

        if not url_name or cls.skip_url(url_name):
            return

        if url_name in cls._exclude_urls:
            return

        target = getattr(cls, target_attr)
        target.append(
            {'url': url, 'url_name': url_name, 'pattern': pattern}
        )


class GenericTestMixin(UrlTestMixin, FilterTestMixin, QuerysetTestMixin):
    '''
    Only containing generic tests
    eveything else, setup methods etc., is in GenericBaseMixin
    '''
    pass


class GenericDynamicTestMixin(DynamicUrlTestMixin, FilterTestMixin, QuerysetTestMixin):
    '''
    Similar to GenericTestMixin except uses dynamic urls splitting and url tests need to be generated with generate_url_tests
    '''
    pass


def generate_url_tests(test_case, num_tests, urls, *args, **kwargs):
    '''
    # generates num_tests number of tests for test_case subclass and urls
    :param test_case: needs to be subclass of DynamicUrlTestMixin and GenericBaseMixin
    :param num_tests: number of tests to split urls into
    :param args: see DynamicUrlTestMixin.collect_urls
    :param kwargs: see DynamicUrlTestMixin.collect_urls
    :return: None
    '''
    if not issubclass(test_case, DynamicUrlTestMixin):
        raise ValueError('test_case needs to be subclass of DynamicUrlTestMixin')

    for index, url_chunk in enumerate(test_case.collect_urls_in_chunks(num_tests, urls, *args, **kwargs)):
        def make_test(url_list):
            def test_urls(self):
                self.models = self.get_models()
                self.model_fields = [(f, model) for model in self.models for f in model._meta.get_fields() if
                                     f.concrete and not f.auto_created]
                self.failed = []
                self.tested = []

                for url in url_list:
                    self.crawl_test_url(**url)

                if self.failed:
                    # append failed count at the end of error list
                    self.failed.append('{}/{} urls FAILED: {}'.format(len(self.failed), len(self.tested), ', '.join(
                        [f['url name'] for f in self.failed])))

                self.assertFalse(self.failed, msg=pformat(self.failed, indent=4))

            return test_urls

        # Attach dynamically generated test method to the class
        setattr(test_case, f"test_urls_chunk_{index + 1}", make_test(url_chunk))
