.. django-kaskader documentation master file, created by
   sphinx-quickstart on Mon Apr 22 19:47:44 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

django-kaskader
===========================================

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
Subclass *GenericBaseMixin* and *GenericTestMixin* in your *TestCase* class, setup inputs from InputMixin as needed and run test command, generic tests for discovered urls, filters and querysets will be included.


.. toctree::
   :hidden:

   Home <self>
   inputs
   exceptions
   generators