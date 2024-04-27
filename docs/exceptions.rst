Exceptions
==========

Failure of generic test will produce message in form of list of submessages for every tested subject (url/filter/queryset),
for example failed get request in test_urls:::

    OrderedDict([
        ('location', 'GET'),
        ('url name', 'accounts:user_update'),
        ('url', '/en/users/1/update'),
        ('url pattern', 'en/^users/<int:pk>/update'),
        ('parsed args', dict_values([1])),
        ('view class', <class 'accounts.views.users.UserUpdateView'>),
        ('traceback', ...)])

**location** is universal key shared by all messages referencing specfic location in *generators.py* where exception happened, searching 'GET' from example will lead to relevant part of code, other keys/values provide additional info/data relevant to failure depending on test and location. Below are exception locations with examples and suggestions for fix

test_urls
---------

**URL ARG TYPE** - url argument type was not recognized automatically for specified argument in order to generate it, provide value manually using *url_args/url_kwargs* in *url_params_map*

**URL ARG MATCH** - url argument failed to be matched with model field and need to be provided manually using *url_args/url_kwargs* in *url_params_map*::

      OrderedDict([
        ('location', 'URL ARG MATCH'),
        ('url name', 'comments:article_comments'),
        ('url pattern', 'en/^comments/<slug:article>/'),
        ('arg', 'slug:article'),
        ('matching fields', []),
        ('traceback', 'Url arg matching failed')]),

**URL ARG PARSE** - most likely value of argument for matched model field of generated object is None, make sure generated obj has not None field value or provide it manually using *url_args/url_kwargs* in *url_params_map*::

    OrderedDict([
        ('location', 'URL ARG PARSE'),
        ('url name', 'comments:article_comments'),
        ('url pattern', 'en/^comments/<slug:article>/<slug:slug>/comments/'),
        ('arg', 'slug:article',),
        ('parsed arg', None),
        ('traceback', 'Url arg parsing failed')]),

**URL ARGS PARSED** - one of url arguments failed to be parsed (see **URL ARG MATCH/URL ARG PARSE**), provide it manually using *url_args/url_kwargs* in *url_params_map*

**GET** - get request failed, often its missing request kwarg required by view, in that case provide *request_kwargs* in *url_params_map*, but it can have many different reasons, follow traceback::

    OrderedDict([
        ('location', 'GET'),
        ('url name', 'accounts:user_export'),
        ('url', '/en/accounts/users/export/'),
        ('url pattern', 'en/^accounts/users/export/'),
        ('parsed args', dict_values([])),
        ('view class', <class 'accounts.views.users.UserExportView'>),
        ('traceback', ...)])


**SORTING** - same as **GET** for specific sorting

**DISPLAY** - same as **GET** for specific display

**TEMPLATE** - response template doesnt match one defined by view or default name

**POST FORM INIT** - failed to get form instance with generated *form_kwargs*, *form_class* is retrieved from get response if possible, provide *form_kwargs* manually in *url_params_map*

**POST GENERATING FORM DATA** - generating form data for given form have failed, provide manually using *data* in *url_params_map*

**POST** - post request failed, see traceback

**POST COUNT** - post request succeded but object wasnt created/deleted depoending on view class, most likely caused by invalid form as in example below (see: 'form_valid', [False])
or redirection in *dispatch*, for example due to missing permission::

    OrderedDict([
        ('location', 'POST COUNT'),
        ('url name', 'accounts:user_delete'),
        ('url', '/en/accounts/users/1/delete/'),
        ('url pattern', 'en/^accounts/users/<int:pk>/delete/'),
        ('parsed args', dict_values(['1'])),
        ('view model', <class 'accounts.models.User'>),
        ('form class', <class 'django.forms.forms.Form'>),
        ('form valid', [False]),
        ('form errors', [{}]),
        ('data', <QueryDict: {]>),
        ('traceback', ...)]),

test_querysets
--------------

**DEFAULT KWARGS** - query method failed with kwargs provided using *queryset_params_map*, update provided kwargs

**NO KWARGS** - query method with no arguments failed, fix the method

**GENERATING KWARGS** - generating kwargs failed, provide them manually using *queryset_params_map*::

    {'location': 'GENERATING KWARGS',
    'model': <class 'messages.Message'>,
    'queryset method': 'MessageQuerySet.from_user',
    'traceback': ...}

**GENERATED KWARGS** - query method failed using generated kwargs, provide kwargs manually using *queryset_params_map*::

    {'kwargs': {},
    'location': 'GENERATED KWARGS',
    'model': <class 'messages.Message'>,
    'queryset method': 'MessageQuerySet.from_user',
    'traceback': ...}

test_filters
------------

**FILTER INIT** - failed to get filter instance with generated *filter_kwargs*, provide *filter_kwargs* manually in *filter_params_map*::

    OrderedDict([
        ('location', 'FILTER INIT'),
        ('filter class', <class 'accounts.UserFilter'>),
        ('filter_kwargs', {}),
        ('params map', {}),
        ('traceback', ...)])

**FILTER DATA** - failed to generate data for filter, provide manually using *data* in *filter_params_map*

**FILTER QUERYSET** - failed to generate queryset for filter, provide manually using *queryset* in *filter_params_map*

**FILTER** - actual filtering using generated and/or provided values failed, see traceback for details::

    OrderedDict([
        ('location', 'FILTER'),
        ('filter class', <class 'accounts.UserFilter'>),
        ('data', ...),
        ('queryset', <UserQuerySet [<User: user1>,  ...]>),
        ('params map', {}),
        ('traceback', ...)])
