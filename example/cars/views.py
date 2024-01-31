from django.db.models import Prefetch
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, CreateView, DeleteView
from pragmatic.mixins import DisplayListViewMixin, SortingListViewMixin

from cars.filters import CarFilter
from cars.forms import CarForm
from cars.models import Car, BrandModel


class CarListView(DisplayListViewMixin, SortingListViewMixin, ListView):
    model = Car
    permission_required = 'cars.list_car'
    back_url = None
    displays = ['list']
    sorting_options = {
        'brand': _('model__brand'),
        'model': _('model'),
    }

    def get_queryset(self):
        queryset = self.filter.qs.select_related(
            'model'
        )
        return queryset

    def dispatch(self, request, *args, **kwargs):
        self.filter = CarFilter(request.GET, queryset=self.get_whole_queryset())
        return super().dispatch(request, *args, **kwargs)

    def get_whole_queryset(self):
        return Car.objects.all()

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['filter'] = self.filter
        return context_data


class CarCreateView(CreateView):
    model = Car
    form_class = CarForm
    permission_required = 'cars.add_car'

    def form_valid(self, form):
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('cars:car_list')

    def get_back_url(self):
        url = self.request.GET.get('back_url', self.get_success_url())
        return url


class CarDeleteView(DeleteView):
    model = Car
    form_class = CarForm
    permission_required = 'cars.delete_car'

    def get_success_url(self):
        return reverse('cars:car_list')