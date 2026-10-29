from datetime import date

from celery import shared_task

from borrowings.models import Borrowing
from borrowings.telegram import send_telegram_message


@shared_task
def check_overdue_borrowings():
    today = date.today()

    overdue_borrowings = Borrowing.objects.filter(
        expected_return_date__lte=today, actual_return_date__isnull=True
    ).select_related("book", "user")
    if not overdue_borrowings.exists():
        send_telegram_message("No borrowings overdue today")
    else:
        for borrowing in overdue_borrowings:
            message = (
                f"⚠️ **OVERDUE BORROWING**\n"
                f"• User: {borrowing.user.email}\n"
                f"• Book: {borrowing.book.title}\n"
                f"• Borrow date: {borrowing.borrow_date}\n"
                f"• Expected return: {borrowing.expected_return_date}"
            )
            send_telegram_message(message)
