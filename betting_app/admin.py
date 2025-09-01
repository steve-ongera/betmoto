from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count
from django.utils import timezone
from .models import (
    User, Wallet, Transaction, AviatorGame, AviatorBet, GameStatistics,
    UserGameStatistics, PaymentMethod, Deposit, Withdrawal, Bonus,
    UserBonus, GameSession, BetLimits, Notification, ReferralProgram,
    SystemConfiguration, GameHistory, Leaderboard, Chat, SupportTicket,
    TicketMessage, AuditLog, GameSettings
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'phone_number', 'email', 'is_verified', 'kyc_status', 'date_joined', 'wallet_balance')
    list_filter = ('is_verified', 'kyc_status', 'is_active', 'date_joined')
    search_fields = ('username', 'phone_number', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('BetMoto Profile', {
            'fields': ('phone_number', 'date_of_birth', 'is_verified', 'kyc_status')
        }),
    )
    
    def wallet_balance(self, obj):
        try:
            return f"KES {obj.wallet.balance}"
        except:
            return "No Wallet"
    wallet_balance.short_description = "Wallet Balance"
    
    actions = ['verify_users', 'approve_kyc', 'reject_kyc']
    
    def verify_users(self, request, queryset):
        queryset.update(is_verified=True)
        self.message_user(request, f"Verified {queryset.count()} users")
    verify_users.short_description = "Verify selected users"
    
    def approve_kyc(self, request, queryset):
        queryset.update(kyc_status='verified')
        self.message_user(request, f"Approved KYC for {queryset.count()} users")
    approve_kyc.short_description = "Approve KYC for selected users"
    
    def reject_kyc(self, request, queryset):
        queryset.update(kyc_status='rejected')
        self.message_user(request, f"Rejected KYC for {queryset.count()} users")
    reject_kyc.short_description = "Reject KYC for selected users"


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'bonus_balance', 'total_deposited', 'total_withdrawn', 'net_position')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__phone_number')
    readonly_fields = ('created_at', 'updated_at')
    
    def net_position(self, obj):
        net = obj.total_deposited - obj.total_withdrawn
        color = 'green' if net >= 0 else 'red'
        return format_html(
            '<span style="color: {};">KES {}</span>',
            color,
            net
        )
    net_position.short_description = "Net Position"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'user', 'transaction_type', 'amount', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('reference', 'user__username', 'mpesa_transaction_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(AviatorGame)
class AviatorGameAdmin(admin.ModelAdmin):
    list_display = ('round_number', 'multiplier', 'status', 'total_bets', 'total_bet_amount', 'start_time', 'crash_time')
    list_filter = ('status', 'start_time')
    search_fields = ('round_number', 'seed')
    readonly_fields = ('id', 'created_at', 'total_bets', 'total_bet_amount')
    ordering = ('-round_number',)
    
    def total_bets(self, obj):
        return obj.bets.count()
    total_bets.short_description = "Total Bets"
    
    def total_bet_amount(self, obj):
        total = obj.bets.aggregate(Sum('bet_amount'))['bet_amount__sum'] or 0
        return f"KES {total}"
    total_bet_amount.short_description = "Total Bet Amount"


@admin.register(AviatorBet)
class AviatorBetAdmin(admin.ModelAdmin):
    list_display = ('user', 'game_round', 'bet_amount', 'cash_out_multiplier', 'payout_amount', 'status', 'placed_at')
    list_filter = ('status', 'placed_at', 'game__round_number')
    search_fields = ('user__username', 'game__round_number')
    readonly_fields = ('id', 'placed_at', 'cashed_out_at')
    ordering = ('-placed_at',)
    
    def game_round(self, obj):
        return obj.game.round_number
    game_round.short_description = "Round"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'game')


@admin.register(GameStatistics)
class GameStatisticsAdmin(admin.ModelAdmin):
    list_display = ('game_round', 'total_bets', 'total_bet_amount', 'total_payout', 'unique_players', 'house_profit')
    readonly_fields = ('created_at',)
    ordering = ('-game__round_number',)
    
    def game_round(self, obj):
        return obj.game.round_number
    game_round.short_description = "Round"
    
    def house_profit(self, obj):
        profit = obj.total_bet_amount - obj.total_payout
        color = 'green' if profit >= 0 else 'red'
        return format_html(
            '<span style="color: {};">KES {}</span>',
            color,
            profit
        )
    house_profit.short_description = "House Profit"


@admin.register(UserGameStatistics)
class UserGameStatisticsAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_games_played', 'total_amount_bet', 'total_winnings', 'win_rate', 'biggest_win')
    list_filter = ('created_at',)
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'min_deposit', 'max_deposit', 'fee_percentage')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'payment_method', 'status', 'mpesa_transaction_id', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'mpesa_transaction_id', 'reference', 'phone_number')
    readonly_fields = ('id', 'reference', 'created_at', 'completed_at')
    ordering = ('-created_at',)
    
    actions = ['approve_deposits', 'reject_deposits']
    
    def approve_deposits(self, request, queryset):
        queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f"Approved {queryset.count()} deposits")
    approve_deposits.short_description = "Approve selected deposits"
    
    def reject_deposits(self, request, queryset):
        queryset.update(status='failed')
        self.message_user(request, f"Rejected {queryset.count()} deposits")
    reject_deposits.short_description = "Reject selected deposits"


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'payment_method', 'status', 'phone_number', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'reference', 'phone_number')
    readonly_fields = ('id', 'reference', 'created_at', 'processed_at', 'completed_at')
    ordering = ('-created_at',)
    
    actions = ['approve_withdrawals', 'reject_withdrawals']
    
    def approve_withdrawals(self, request, queryset):
        queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f"Approved {queryset.count()} withdrawals")
    approve_withdrawals.short_description = "Approve selected withdrawals"
    
    def reject_withdrawals(self, request, queryset):
        queryset.update(status='failed')
        self.message_user(request, f"Rejected {queryset.count()} withdrawals")
    reject_withdrawals.short_description = "Reject selected withdrawals"


@admin.register(Bonus)
class BonusAdmin(admin.ModelAdmin):
    list_display = ('name', 'bonus_type', 'amount', 'percentage', 'is_active', 'valid_from', 'valid_until')
    list_filter = ('bonus_type', 'is_active', 'valid_from')
    search_fields = ('name', 'bonus_type')
    readonly_fields = ('created_at',)


@admin.register(UserBonus)
class UserBonusAdmin(admin.ModelAdmin):
    list_display = ('user', 'bonus_name', 'amount_awarded', 'wagering_progress', 'status', 'awarded_at', 'expires_at')
    list_filter = ('status', 'awarded_at', 'bonus__bonus_type')
    search_fields = ('user__username', 'bonus__name')
    readonly_fields = ('awarded_at', 'completed_at')
    
    def bonus_name(self, obj):
        return obj.bonus.name
    bonus_name.short_description = "Bonus"
    
    def wagering_progress(self, obj):
        if obj.required_wagering > 0:
            progress = (obj.amount_wagered / obj.required_wagering) * 100
            return f"{progress:.1f}%"
        return "N/A"
    wagering_progress.short_description = "Wagering Progress"


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_id', 'start_time', 'end_time', 'total_bets', 'total_bet_amount', 'session_profit')
    list_filter = ('start_time',)
    search_fields = ('user__username', 'session_id')
    readonly_fields = ('session_id', 'start_time', 'ip_address', 'user_agent')
    
    def session_profit(self, obj):
        profit = obj.total_winnings - obj.total_bet_amount
        color = 'green' if profit >= 0 else 'red'
        return format_html(
            '<span style="color: {};">KES {}</span>',
            color,
            profit
        )
    session_profit.short_description = "Session P&L"


@admin.register(BetLimits)
class BetLimitsAdmin(admin.ModelAdmin):
    list_display = ('user', 'daily_bet_limit', 'weekly_bet_limit', 'monthly_bet_limit', 'is_self_excluded', 'self_exclusion_until')
    list_filter = ('is_self_excluded', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'is_important', 'created_at')
    list_filter = ('notification_type', 'is_read', 'is_important', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('created_at', 'read_at')
    
    actions = ['mark_as_read', 'mark_as_important']
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, f"Marked {queryset.count()} notifications as read")
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_important(self, request, queryset):
        queryset.update(is_important=True)
        self.message_user(request, f"Marked {queryset.count()} notifications as important")
    mark_as_important.short_description = "Mark selected notifications as important"


@admin.register(ReferralProgram)
class ReferralProgramAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referred_user', 'referral_code', 'bonus_awarded', 'is_bonus_claimed', 'referred_at')
    list_filter = ('is_bonus_claimed', 'referred_at')
    search_fields = ('referrer__username', 'referred_user__username', 'referral_code')
    readonly_fields = ('referred_at', 'bonus_claimed_at')


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'is_active', 'description', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('key', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(GameHistory)
class GameHistoryAdmin(admin.ModelAdmin):
    list_display = ('game_round', 'duration_seconds', 'total_players', 'total_bet_volume', 'house_edge', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('-game__round_number',)
    
    def game_round(self, obj):
        return obj.game.round_number
    game_round.short_description = "Round"


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('user', 'game_round', 'message_preview', 'is_system_message', 'is_moderated', 'created_at')
    list_filter = ('is_system_message', 'is_moderated', 'created_at')
    search_fields = ('user__username', 'message')
    readonly_fields = ('created_at',)
    
    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_preview.short_description = "Message"
    
    def game_round(self, obj):
        return obj.game.round_number if obj.game else "Global"
    game_round.short_description = "Game Round"
    
    actions = ['moderate_messages']
    
    def moderate_messages(self, request, queryset):
        queryset.update(is_moderated=True)
        self.message_user(request, f"Moderated {queryset.count()} messages")
    moderate_messages.short_description = "Moderate selected messages"


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'status', 'priority', 'assigned_to', 'created_at', 'resolved_at')
    list_filter = ('status', 'priority', 'created_at')
    search_fields = ('user__username', 'subject', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at', 'resolved_at')
    inlines = [TicketMessageInline]
    
    actions = ['assign_to_me', 'mark_resolved']
    
    def assign_to_me(self, request, queryset):
        queryset.update(assigned_to=request.user, status='in_progress')
        self.message_user(request, f"Assigned {queryset.count()} tickets to you")
    assign_to_me.short_description = "Assign selected tickets to me"
    
    def mark_resolved(self, request, queryset):
        queryset.update(status='resolved', resolved_at=timezone.now())
        self.message_user(request, f"Marked {queryset.count()} tickets as resolved")
    mark_resolved.short_description = "Mark selected tickets as resolved"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action_type', 'description', 'ip_address', 'created_at')
    list_filter = ('action_type', 'created_at')
    search_fields = ('user__username', 'description', 'ip_address')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(GameSettings)
class GameSettingsAdmin(admin.ModelAdmin):
    list_display = ('min_bet_amount', 'max_bet_amount', 'house_edge', 'is_maintenance_mode', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    
    def has_add_permission(self, request):
        return not GameSettings.objects.exists()


@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    list_display = ('user', 'leaderboard_type', 'rank', 'total_winnings', 'games_played', 'biggest_multiplier', 'period_start')
    list_filter = ('leaderboard_type', 'period_start', 'rank')
    search_fields = ('user__username',)
    readonly_fields = ('created_at',)
    ordering = ('leaderboard_type', 'rank')


# Custom admin site configuration
admin.site.site_header = "BetMoto Admin"
admin.site.site_title = "BetMoto Admin Portal"
admin.site.index_title = "Welcome to BetMoto Administration"


# Create a custom admin view for dashboard statistics
class DashboardStats:
    """Custom dashboard statistics"""
    
    @staticmethod
    def get_stats():
        from django.db.models import Sum, Count, Avg
        from datetime import datetime, timedelta
        
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        stats = {
            'total_users': User.objects.count(),
            'verified_users': User.objects.filter(is_verified=True).count(),
            'active_games': AviatorGame.objects.filter(status__in=['betting', 'flying']).count(),
            'pending_deposits': Deposit.objects.filter(status='pending').count(),
            'pending_withdrawals': Withdrawal.objects.filter(status='pending').count(),
            'open_tickets': SupportTicket.objects.filter(status='open').count(),
            'today_revenue': Transaction.objects.filter(
                transaction_type='bet',
                status='completed',
                created_at__date=today
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
            'yesterday_revenue': Transaction.objects.filter(
                transaction_type='bet',
                status='completed',
                created_at__date=yesterday
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
            'week_revenue': Transaction.objects.filter(
                transaction_type='bet',
                status='completed',
                created_at__date__gte=week_ago
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
        }
        
        return stats


# Register remaining models with basic admin
admin.site.register(TicketMessage)