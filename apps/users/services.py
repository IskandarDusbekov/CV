"""Onlayn to'lov tizimlari (Click/Payme) callback'lari uchun yordamchilar.

Hozircha to'lov Telegram bot orqali qo'lda qabul qilinadi (PaymentRequest). Click/Payme merchant
ulanganda PaymentTransaction yaratish shu modulga qaytadan qo'shiladi; callback endpoint tayyor turadi.
"""
from .models import PaymentTransaction, UserSubscription


def activate_transaction(transaction, payload=None):
    if transaction.status == PaymentTransaction.STATUS_PAID:
        return transaction

    transaction.raw_response = payload or transaction.raw_response
    transaction.mark_paid(save=True)

    if transaction.purpose == PaymentTransaction.PURPOSE_CV_UNLOCK:
        if transaction.cv_id and not transaction.cv.is_unlocked:
            transaction.cv.unlock(save=True)
    elif transaction.subscription and transaction.subscription.status != UserSubscription.STATUS_ACTIVE:
        transaction.subscription.activate(save=True)

    return transaction


def fail_transaction(transaction, payload=None):
    transaction.status = PaymentTransaction.STATUS_FAILED
    transaction.raw_response = payload or transaction.raw_response
    transaction.save(update_fields=["status", "raw_response", "updated_at"])
    return transaction
