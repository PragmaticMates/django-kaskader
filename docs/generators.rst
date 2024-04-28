Generators
==========

Discovery
---------

**BaseMixin** contains methods used to search relevant apps, models, urls, parsing args and other basic necessary functionalities.

Test objects
------------

**GenericBaseMixin(InputMixin, BaseMixin)** provides a number of helper methods for generating and working with objects populated with test data. Besides following important functions contains also other potentially useful methods for generating specific mock values, etc.

Retrieving objects and data
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**get_generated_obj(model=None, obj_name=None)** returns object matching model and obj_name, better use both parameters to avoid ambiguity

**next_id(model)** returns next id for given model, meaning last existing + 1

Generating objects
^^^^^^^^^^^^^^^^^^

**setUpTestData()** appends object generation to TestCase.setUpTestData() when a test class is loaded.

**generate_objs()** sorts order of models to generate objects for and creates objects for model in that.

**get_sorted_models_dependency(required_only=False, reverse=False)** orders models by relations.

**generate_model_objs(model)** generates objects for given model.

:strong:`generate_obj(model, field_values=None, **kwargs)` generates obj for given model with values given in kwargs, field values are deprecated.

Generic tests
^^^^^^^^^^^^^

**GenericTestMixin** provides basic tests for urls, filters and querysets:

    **test_urls()** looks up and tests all found urls checking get request (including sorting and display), response code, post request with generated form data, form validity, verifies creation/deletion for detected Create/DeleteView

    **test_querysets()** finds QuerySet subclasses and calls every method with generated args/kwargs

    **def test_filters()** finds subclasses of FilterSet and calls filtered queryset for generated form data

Miscellaneous
^^^^^^^^^^^^^

missing_tests.py
""""""""""""""""

**class MissingTestMixin(GenericBaseMixin)** checks missing tests for signals, permissions, custom filter methods and managers. Test names must use specific pattern to be recognised.

mixins.py
"""""""""

Contains potentially helpful mixins for various manual tests.

**RqMixin** - testing rq jobs and scheduling

**UrlTestMixin** - testing urls

**FilterTestMixin** - testing filters

**ManagerTestMixin** - testing managers

**PermissionTestMixin** - testing permissions.
