from rest_framework import routers

from book.views import BookViewSet

router = routers.DefaultRouter()
router.register("", BookViewSet, basename="book")

urlpatterns = router.urls

app_name = "book"
