from django.urls import path
from .views import generate_item_details

urlpatterns = [
    path("generate-item-details/", generate_item_details, name="generate_item_details"),
]
