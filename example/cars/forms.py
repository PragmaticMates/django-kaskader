from django.forms import ModelForm, ModelChoiceField
from django.utils.translation import gettext_lazy as _
from crispy_forms.bootstrap import FormActions, InlineRadios
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Row, Layout, Fieldset

from cars.models import Car, CarBrand, BrandModel


class CarForm(ModelForm):
    brand = ModelChoiceField(label=_('User'), queryset=CarBrand.objects.all())

    class Meta:
        model = Car
        fields = ('model', 'engine', 'color', 'numberplate')

    def __init__(self, brand=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if brand:
            self.fields['model'].queryset = BrandModel.objects.filter(brand=brand)

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
