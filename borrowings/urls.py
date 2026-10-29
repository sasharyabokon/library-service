from rest_framework.routers import DefaultRouter

from borrowings.views import BorrowingViewSet

router = DefaultRouter()
router.register("", BorrowingViewSet, basename="borrowing")

urlpatterns = router.urls

app_name = "borrowings"
