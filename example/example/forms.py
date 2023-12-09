from django.forms import ModelForm
from django.utils.translation import gettext_lazy as _
from crispy_forms.bootstrap import FormActions, InlineRadios
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Row, Layout, Fieldset

from example.models import Car


class CarForm(ModelForm):
    class Meta:
        model = Car
        fields = ('model', 'engine', 'color', 'numberplate')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Fieldset(
                    _('Details'),
                    'numberplate',
                    'model',
                    'engine',
                    css_class='col-md-3'
                ),
                Fieldset(
                    _('Extra'),
                    InlineRadios('color'),
                    css_class='col-md-9'
                )
            ),
            FormActions(
                Submit('submit', _('Submit'), css_class='btn-lg')
            )
        )
