from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Fieldset, Div, Field, Submit
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_filters import FilterSet, CharFilter

from cars.models import Car


class CarFilter(FilterSet):

    class Meta:
        model = Car
        fields = [
            'model__brand', 'model', 'engine', 'color', 'numberplate', 'created', 'modified'
        ]
        filter_overrides = {
            models.CharField: {
                'filter_class': CharFilter,
                'extra': lambda f: {
                    'lookup_expr': 'icontains',
                },
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Fieldset(
                    _('Car Model'),
                    Row(
                        Div('model__brand', css_class='col-md-6'),
                        Div(Field('model', css_class='col-md-6'), css_class='col-md-6'),
                    ), css_class='col-md-12'
                ),
                Fieldset(
                    _('Details'),
                    Row(
                        Div(Field('engine', css_class='col-md-6'), css_class='col-md-6'),
                        Div(Field('color', css_class='col-md-6'), css_class='col-md-6'),
                    ), css_class='col-md-12'
                ),
                Fieldset(
                    _('Dates'),
                    Row(
                        Div(Field('created', css_class='date-picker form-control'), css_class='col-md-6 range-filter'),
                        Div(Field('modified', css_class='date-picker form-control'), css_class='col-md-6 range-filter'),
                    ), css_class='col-md-12'
                ),
                Fieldset(
                    _('Additional'),
                    Row(
                        Div(Field('numberplate', css_class='col-md-12'), css_class='col-md-12'),
                    ), css_class='col-md-12'
                )
            ),
            Submit('submit', 'Submit', css_class='button white'),
        )
