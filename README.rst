django-kaskader
================

Tool for generating simple Django tests

Requirements
------------
- Django

Some utilities require additional libraries as:

- django-pragmatic
- djnago-filter
- better-exceptions

Installation
------------

1. Install python library using pip: pip install django-kaskader

2. Add ``kaskader`` to ``INSTALLED_APPS`` in your Django settings file


Usage
-----
Subclass GenericBaseMixin and GenericTestMixin in your TestCase class, setup inputs from InputMixin as needed and run test command, generic tests for discovered urls, filters and querysets will be included.

generators.py
^^^^^^^^^^^^^

Providing data
''''''''''''''
``class InputMixin(object)``
    Contains all attributes and methods used to specify what objects to create, which apps to test, what to skip.
    Set attributes as needed and override following methods to modify default behavior.

    Providing obj data

    ``def manual_model_dependency(cls)``
        Use to add explicit models dependencies based on realtions used for ordering models for generating objects.

    ``def model_field_values_map(cls)``
        Use to specify objects with predefined values to generate.

    ``def model_field_name_map(cls)``
        Use to specify default model field values by field name.

    ``def default_field_map(cls)``
        Use to specify default model field values by field class.

    ``def default_form_field_map(cls)``
        Use to specify default form field values by field class.

    Providing test data

    ``def url_params_map(self)``
        use to provide specific test values per url for test_urls

    ``def queryset_params_map(self)``
        use to provide specific test args/kwargs values per queryset method for test_querysets

    ``def filter_params_map(self)``
        use to provide specific test values per filter for test_filters

Discovery
'''''''''
``class BaseMixin(object)``
    Contains methods use to search relevant apps, models, urls, parsing args and other basic necessary functionalities.

Generating test objects
'''''''''''''''''''''''
``class GenericBaseMixin(InputMixin, BaseMixin)``
    Provides a number of helper methods for generating and working with objects populated with test data.
    Besides following important functions contains also other potentially useful methods for generating specific mock values, etc.

    Retrieving objects and data

    ``def get_generated_obj(cls, model=None, obj_name=None)``
        returns object matching model and obj_name, better use both parameters to avoid ambiguity

    ``def next_id(cls, model)``
        returns next id for given model, meaning last existing + 1

    Generating objects

    ``def setUpTestData(cls)``
        Appends object generation to TestCase.setUpTestData() when a test class is loaded.

    ``def generate_objs(cls)``
        Sorts order of models to generate objects for and creates objects for model in that.

    ``def get_sorted_models_dependency(cls, required_only=False, reverse=False)``
        Orders models by relations.

    ``def generate_model_objs(cls, model)``
        Generates objects for given model.

    ``def generate_obj(cls, model, field_values=None, **kwargs)``
        Generates obj for given model with values given in kwargs, field values are deprecated.

Generic tests
'''''''''''''
``class GenericTestMixin(Object)``
    Provides basic tests for urls, filters and querysets

    ``def test_urls(self)``
        looks up and tests all found urls checking get request (including sorting and display), response code, post request with generated form data, form validity, verifies creation/deletion for detected Create/DeleteView

    ``def test_querysets(self)``
        finds QuerySet subclasses and calls every method with generated args/kwargs

    ``def test_filters(self)``
        finds subclasses of FilterSet and calls filtered queryset for generated form data

missing_tests.py
^^^^^^^^^^^^^^^^
``class MissingTestMixin(GenericBaseMixin)``
    Checks missing tests for signals, permissions, custom filter methods and managers. Test names must use specific pattern to be recognised.

mixins.py
^^^^^^^^^
Contains potentailly helpful mixins for various manual tests.

``class RqMixin(object)``
    Testing rq jobs and scheduling.

``class UrlTestMixin(object)``
    Testing urls.

``class FilterTestMixin(object)``
    Testing filters.

``class ManagerTestMixin(object)``
    Testing managers.

``class PermissionTestMixin(object)``
    Testing permissions.

