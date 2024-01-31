from django.urls import path
from django.utils.translation import pgettext_lazy

from cars.views import CarCreateView, CarListView, CarDeleteView

app_name = 'cars'

urlpatterns = [
    path(pgettext_lazy("url", 'cars/create/'), CarCreateView.as_view(), name='car_create'),
    path(pgettext_lazy("url", 'cars/<pk>/delete/'), CarDeleteView.as_view(), name='car_delete'),
    path(pgettext_lazy("url", 'cars/'), CarListView.as_view(), name='car_list'),
]