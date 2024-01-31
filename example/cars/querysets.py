from django.db.models import QuerySet

class CarQuerySet(QuerySet):
    def brand(self, brand):
        return self.filter(model__brand=brand)

    def model(self, model):
        return self.filter(model=model)