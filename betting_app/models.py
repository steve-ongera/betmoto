from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid

class User(AbstractUser):
    """Extended User model for BetMoto platform"""
    phone_number = models.CharField(max_length=15, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    kyc_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.username} - {self.phone_number}"


class Wallet(models.Model):
    """User wallet for managing funds"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    bonus_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_deposited = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    total_withdrawn = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - Balance: {self.balance}"


class Transaction(models.Model):
    """Track all financial transactions"""
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('bet', 'Bet'),
        ('win', 'Win'),
        ('bonus', 'Bonus'),
        ('refund', 'Refund'),
    ]
    
    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    reference = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    mpesa_transaction_id = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"


class AviatorGame(models.Model):
    """Aviator game rounds"""
    GAME_STATUS = [
        ('waiting', 'Waiting for Players'),
        ('betting', 'Betting Phase'),
        ('flying', 'Flying'),
        ('crashed', 'Crashed'),
        ('completed', 'Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round_number = models.PositiveIntegerField(unique=True)
    multiplier = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal('1.00'))]
    )
    status = models.CharField(max_length=20, choices=GAME_STATUS, default='waiting')
    start_time = models.DateTimeField(null=True, blank=True)
    crash_time = models.DateTimeField(null=True, blank=True)
    betting_end_time = models.DateTimeField(null=True, blank=True)
    seed = models.CharField(max_length=100)  # For provably fair gaming
    hash_value = models.CharField(max_length=100)  # For provably fair gaming
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Round {self.round_number} - {self.multiplier}x"


class AviatorBet(models.Model):
    """Individual bets placed on aviator game"""
    BET_STATUS = [
        ('active', 'Active'),
        ('won', 'Won'),
        ('lost', 'Lost'),
        ('cashed_out', 'Cashed Out'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='aviator_bets')
    game = models.ForeignKey(AviatorGame, on_delete=models.CASCADE, related_name='bets')
    bet_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))]
    )
    cash_out_multiplier = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal('1.00'))]
    )
    auto_cash_out_at = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal('1.01'))]
    )
    payout_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    status = models.CharField(max_length=20, choices=BET_STATUS, default='active')
    placed_at = models.DateTimeField(auto_now_add=True)
    cashed_out_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-placed_at']
        unique_together = ['user', 'game']  # One bet per user per game
    
    def __str__(self):
        return f"{self.user.username} - {self.bet_amount} - Round {self.game.round_number}"


class GameStatistics(models.Model):
    """Track game statistics and analytics"""
    game = models.OneToOneField(AviatorGame, on_delete=models.CASCADE, related_name='statistics')
    total_bets = models.PositiveIntegerField(default=0)
    total_bet_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_payout = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    unique_players = models.PositiveIntegerField(default=0)
    highest_bet = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Stats for Round {self.game.round_number}"


class UserGameStatistics(models.Model):
    """Track individual user game statistics"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='game_stats')
    total_games_played = models.PositiveIntegerField(default=0)
    total_amount_bet = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_winnings = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    biggest_win = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    highest_multiplier = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    win_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    games_won = models.PositiveIntegerField(default=0)
    games_lost = models.PositiveIntegerField(default=0)
    average_cash_out = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - Stats"


class PaymentMethod(models.Model):
    """Available payment methods"""
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    min_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    max_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('100000.00'))
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    max_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('100000.00'))
    fee_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class Deposit(models.Model):
    """Deposit transactions"""
    DEPOSIT_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposits')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=DEPOSIT_STATUS, default='pending')
    mpesa_transaction_id = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=15)
    reference = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - Deposit {self.amount}"


class Withdrawal(models.Model):
    """Withdrawal transactions"""
    WITHDRAWAL_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=WITHDRAWAL_STATUS, default='pending')
    phone_number = models.CharField(max_length=15)
    reference = models.CharField(max_length=100, unique=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - Withdrawal {self.amount}"


class Bonus(models.Model):
    """Bonus campaigns and promotions"""
    BONUS_TYPES = [
        ('welcome', 'Welcome Bonus'),
        ('deposit', 'Deposit Bonus'),
        ('loyalty', 'Loyalty Bonus'),
        ('referral', 'Referral Bonus'),
        ('cashback', 'Cashback'),
        ('free_bet', 'Free Bet'),
    ]
    
    name = models.CharField(max_length=100)
    bonus_type = models.CharField(max_length=20, choices=BONUS_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    min_deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_bonus = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    wagering_requirement = models.PositiveIntegerField(default=1)  # How many times to wager
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    description = models.TextField()
    terms_and_conditions = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.bonus_type}"


class UserBonus(models.Model):
    """Track user bonus allocations"""
    BONUS_STATUS = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_bonuses')
    bonus = models.ForeignKey(Bonus, on_delete=models.CASCADE)
    amount_awarded = models.DecimalField(max_digits=10, decimal_places=2)
    amount_wagered = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    required_wagering = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=BONUS_STATUS, default='active')
    awarded_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.bonus.name} - {self.amount_awarded}"


class GameSession(models.Model):
    """Track user game sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='game_sessions')
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    total_bets = models.PositiveIntegerField(default=0)
    total_bet_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_winnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    def __str__(self):
        return f"{self.user.username} - Session {self.session_id}"


class BetLimits(models.Model):
    """Betting limits for responsible gambling"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bet_limits')
    daily_bet_limit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    weekly_bet_limit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    monthly_bet_limit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    single_bet_limit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    is_self_excluded = models.BooleanField(default=False)
    self_exclusion_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - Bet Limits"


class Notification(models.Model):
    """User notifications"""
    NOTIFICATION_TYPES = [
        ('game', 'Game Notification'),
        ('transaction', 'Transaction'),
        ('bonus', 'Bonus'),
        ('system', 'System'),
        ('promotion', 'Promotion'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"


class ReferralProgram(models.Model):
    """Referral program tracking"""
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referred_user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referred_by')
    referral_code = models.CharField(max_length=20)
    bonus_awarded = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_bonus_claimed = models.BooleanField(default=False)
    referred_at = models.DateTimeField(auto_now_add=True)
    bonus_claimed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.referrer.username} referred {self.referred_user.username}"


class SystemConfiguration(models.Model):
    """System-wide configuration settings"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.key}: {self.value}"


class GameHistory(models.Model):
    """Historical data for completed games"""
    game = models.OneToOneField(AviatorGame, on_delete=models.CASCADE, related_name='history')
    duration_seconds = models.PositiveIntegerField()
    total_players = models.PositiveIntegerField()
    total_bet_volume = models.DecimalField(max_digits=15, decimal_places=2)
    house_edge = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"History for Round {self.game.round_number}"


class Chat(models.Model):
    """In-game chat messages"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    game = models.ForeignKey(AviatorGame, on_delete=models.CASCADE, related_name='chat_messages', null=True, blank=True)
    message = models.TextField(max_length=500)
    is_system_message = models.BooleanField(default=False)
    is_moderated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user.username}: {self.message[:50]}"


class SupportTicket(models.Model):
    """Customer support tickets"""
    TICKET_STATUS = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=TICKET_STATUS, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='medium')
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_tickets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Ticket #{self.id} - {self.subject}"


class TicketMessage(models.Model):
    """Messages within support tickets"""
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    is_staff_response = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message for Ticket #{self.ticket.id}"


class AuditLog(models.Model):
    """Track important system events"""
    ACTION_TYPES = [
        ('user_login', 'User Login'),
        ('user_register', 'User Registration'),
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('bet_placed', 'Bet Placed'),
        ('bet_won', 'Bet Won'),
        ('bonus_awarded', 'Bonus Awarded'),
        ('limit_change', 'Limit Change'),
        ('account_suspended', 'Account Suspended'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs', null=True, blank=True)
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    additional_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        username = self.user.username if self.user else "System"
        return f"{username} - {self.action_type} - {self.created_at}"


class GameSettings(models.Model):
    """Game configuration settings"""
    min_bet_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('1.00')
    )
    max_bet_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('10000.00')
    )
    min_cash_out_multiplier = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal('1.01')
    )
    max_cash_out_multiplier = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal('1000.00')
    )
    betting_phase_duration = models.PositiveIntegerField(default=10)  # seconds
    game_interval = models.PositiveIntegerField(default=5)  # seconds between games
    house_edge = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('3.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('50.00'))]
    )
    is_maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Game Settings"
        verbose_name_plural = "Game Settings"
    
    def __str__(self):
        return f"Game Settings - Updated: {self.updated_at}"


class Leaderboard(models.Model):
    """Track top players"""
    LEADERBOARD_TYPES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('all_time', 'All Time'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaderboard_entries')
    leaderboard_type = models.CharField(max_length=20, choices=LEADERBOARD_TYPES)
    total_winnings = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    games_played = models.PositiveIntegerField(default=0)
    biggest_multiplier = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    rank = models.PositiveIntegerField()
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'leaderboard_type', 'period_start']
        ordering = ['rank']
    
    def __str__(self):
        return f"{self.user.username} - {self.leaderboard_type} - Rank {self.rank}"