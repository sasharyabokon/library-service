from django.urls import path, include
from rest_framework.routers import DefaultRouter

from payment.views import PaymentViewSet, StripeWebhookView

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("", include(router.urls)),
    path("webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
]

app_name = "payment"
