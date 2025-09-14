# context_processors.py
from django.db.models import Sum
from .models import Wallet

def wallet_stats(request):
    if request.path.startswith('/admin-wallets/'):
        total_balance = Wallet.objects.aggregate(Sum('balance'))['balance__sum'] or 0
        total_bonus_balance = Wallet.objects.aggregate(Sum('bonus_balance'))['bonus_balance__sum'] or 0
        wallets_count = Wallet.objects.count()
        
        return {
            'total_balance': total_balance,
            'total_bonus_balance': total_bonus_balance,
            'wallets_count': wallets_count
        }
    return {}