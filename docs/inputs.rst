Inputs
======

All variables and methods for input purposes are in *InputMixin* class

Attributes
----------

**CHECK_MODULES** - list of modules which should be included, eg *[myapp]*, or more specifically *[myapp.core, myapp.subapp1]*

**EXCLUDE_MODULES** - list of all modules that should be excluded from search for models, urls, etc., for example *['migrations', 'commands', 'tests', 'settings']*

**TEST_PASSWORD** - login password for users

**IGNORE_MODEL_FIELDS** - dictionary of fields per model that should not be generated, use for fields with automatically assigned values, for example *{MPTTModel: ['lft', 'rght', 'tree_id', 'level']}*

**PRINT_SORTED_MODEL_DEPENDENCY** - flag for printing out generated models dependency (for debug purposes)

**PRINT_TEST_SUBJECT** = flag for printing out tested subject like url params/filter class/queryset

test_urls specific
^^^^^^^^^^^^^^^^^^

**RUN_ONLY_THESE_URL_NAMES** - optional list of url names, if provided will run tests only for given urls (for debug purposes to save time), for example ['accounts:user_detail']

**RUN_ONLY_URL_NAMES_CONTAINING** - optional list of url name patterns, if not empty will run tests only for urls containing at least one of provided patterns

**IGNORE_URL_NAMES_CONTAINING** - list of url names to skip in tests

**POST_ONLY_URLS** - list of url names to run only post request tests for

**GET_ONLY_URLS** - list of url names to run only get request tests for

Input methods
-------------

Following methods are simplified examples just for completeness of inputs, see *InputMixin* for details

Model dependencies
^^^^^^^^^^^^^^^^^^
.. code-block:: python

    @classmethod
    def manual_model_dependency(cls):
        '''
        Use to manually specify model dependency which are not accounted for by default (check get_sorted_models_dependency output),
        for example if generating objs with provided m2m values, or otherwise required in model_field_values_map
        '''
        return {
            User: {Group}
        }

Field Values
^^^^^^^^^^^^
.. code-block:: python

    @classmethod
    def model_field_values_map(cls):
        '''
        Enables generate objects with specific values, for example for User model:
        '''
        return {
            User: {
                'user_1': lambda cls: {
                'username': f'user.{cls.next_id(User)}@example.com',
                'email': f'user.{cls.next_id(User)}@example.com',
                'password': 'testpassword',
                'is_superuser': True,
            },
        }

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
        map = { ... }
        return map


    @classmethod
    def default_form_field_map(cls):
        '''
        field values by form field class used to generate form values, values can be callables with field variable,
        extend in subclass as needed
        '''
        map = { ... }
        return map

Test values
^^^^^^^^^^^
.. code-block:: python

    @property
    def url_params_map(self):
        return {
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

    @property
    def queryset_params_map(self):
        return {
            'UserQuerySet: {
                'restrict_user': {},
            },
        }

    @property
    def filter_params_map(self):
        return {
            'UserFilterSet: {
                'filter_kwargs': {},
                'data': {},
                'queryset': User.objects.all(), # optional
            },
        }
