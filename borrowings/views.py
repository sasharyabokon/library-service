from rest_framework import viewsets, request
from rest_framework.permissions import IsAuthenticated

from borrowings.models import Borrowing
from borrowings.serializers import BorrowingSerializer


class BorrowingViewSet(viewsets.ModelViewSet):
    serializer_class = BorrowingSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        queryset = Borrowing.objects.select_related("user", "book")

        if user.is_staff:
            queryset = queryset.filter(user=user)

        user_id = self.request.query_params.get("user_id")
        if user.is_staff and user_id:
            queryset = queryset.filter(user_id=user_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            is_active_bool = is_active.lower() == "true"
            if is_active_bool:
                queryset = queryset.filter(actual_return_date__isnull=True)
            queryset = queryset.filter(actual_return_date__isnull=False)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
