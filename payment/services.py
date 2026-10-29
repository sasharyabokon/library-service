import stripe
from django.conf import settings


def create_stripe_session(payment, success_url, cancel_url):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    unit_amount = int(payment.money_to_pay * 100)
    session = stripe.checkout.Session.create(
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Library Payment #{payment.id} ({payment.get_type_display()})",
                    },
                    "unit_amount": unit_amount,
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
    )

    payment.session_id = session.id
    payment.session_url = session.url
    payment.save()

    return session
