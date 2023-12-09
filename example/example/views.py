from django.db.models import Prefetch
from django.urls import reverse
from django.views.generic import ListView, CreateView

from example.filters import CarFilter
from example.forms import CarForm
from example.models import Car, BrandModel


class CarListView(ListView):
    model = Car
    permission_required = 'cars.list_car'

    def get_queryset(self):
        queryset = self.filter.qs.select_related(
            'model'
        ).prefetch_related(
            Prefetch('brand', queryset=BrandModel.objects.all())
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
        return reverse('car_list')