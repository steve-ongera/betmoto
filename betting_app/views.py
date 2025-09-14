from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate , logout
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from decimal import Decimal
import json
import random
import hashlib
import time
from datetime import datetime, timedelta
from django.db import models


from .models import (
    User, Wallet, Transaction, AviatorGame, AviatorBet, 
    GameStatistics, UserGameStatistics, Deposit, Withdrawal,
    PaymentMethod, Notification, GameSession, BetLimits
)
from .forms import RegistrationForm, LoginForm, DepositForm, WithdrawalForm


def home(request):
    """Main game page - accessible to all users"""
    # Get recent games for statistics
    recent_games = AviatorGame.objects.filter(
        status='completed'
    ).order_by('-round_number')[:20]
    
    # Get current/active game
    current_game = AviatorGame.objects.filter(
        status__in=['waiting', 'betting', 'flying']
    ).first()
    
    # Calculate statistics for display
    if recent_games:
        avg_multiplier = sum(float(game.multiplier or 0) for game in recent_games) / len(recent_games)
        high_multipliers = [game for game in recent_games if game.multiplier and game.multiplier >= 10]
        low_multipliers = [game for game in recent_games if game.multiplier and game.multiplier < 2]
    else:
        avg_multiplier = 0
        high_multipliers = []
        low_multipliers = []
    
    context = {
        'recent_games': recent_games,
        'current_game': current_game,
        'avg_multiplier': round(avg_multiplier, 2),
        'high_count': len(high_multipliers),
        'low_count': len(low_multipliers),
    }
    
    if request.user.is_authenticated:
        try:
            wallet = request.user.wallet
            context['wallet'] = wallet
            
            # Get user's recent bets
            recent_bets = AviatorBet.objects.filter(
                user=request.user
            ).order_by('-placed_at')[:10]
            context['recent_bets'] = recent_bets
            
            # Get user stats
            try:
                user_stats = request.user.game_stats
                context['user_stats'] = user_stats
            except UserGameStatistics.DoesNotExist:
                pass
                
        except Wallet.DoesNotExist:
            # Create wallet if doesn't exist
            Wallet.objects.create(user=request.user)
            context['wallet'] = request.user.wallet
    
    return render(request, 'aviator/game.html', context)


def register_view(request):
    """User registration"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create wallet for new user
            Wallet.objects.create(user=user)
            # Create user game statistics
            UserGameStatistics.objects.create(user=user)
            
            messages.success(request, 'Account created successfully! Please login.')
            return redirect('login')
    else:
        form = RegistrationForm()
    
    return render(request, 'aviator/register.html', {'form': form})


def login_view(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'Invalid credentials')
    else:
        form = LoginForm()
    
    return render(request, 'aviator/login.html', {'form': form})


def logout_view(request):
    logout(request)  # Clears the session
    return redirect('home')  # Redirect to home page after logout

@login_required
def profile_view(request):
    """User profile page"""
    wallet = request.user.wallet
    
    # Get transaction history
    transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:20]
    
    # Get deposits and withdrawals
    deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')[:10]
    withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    # Get user stats
    try:
        user_stats = request.user.game_stats
    except UserGameStatistics.DoesNotExist:
        user_stats = UserGameStatistics.objects.create(user=request.user)
    
    context = {
        'wallet': wallet,
        'transactions': transactions,
        'deposits': deposits,
        'withdrawals': withdrawals,
        'user_stats': user_stats,
    }
    
    return render(request, 'aviator/profile.html', context)


@login_required
def deposit_view(request):
    """Deposit funds"""
    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            deposit = form.save(commit=False)
            deposit.user = request.user
            deposit.net_amount = deposit.amount - deposit.fee
            deposit.reference = f"DEP_{int(time.time())}_{request.user.id}"
            deposit.save()
            
            messages.success(request, 'Deposit request submitted successfully!')
            return redirect('profile')
    else:
        form = DepositForm()
    
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    
    return render(request, 'aviator/deposit.html', {
        'form': form,
        'payment_methods': payment_methods
    })


@login_required
def withdrawal_view(request):
    """Withdraw funds"""
    wallet = request.user.wallet
    
    if request.method == 'POST':
        form = WithdrawalForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            
            if amount > wallet.balance:
                messages.error(request, 'Insufficient balance')
            else:
                withdrawal = form.save(commit=False)
                withdrawal.user = request.user
                withdrawal.net_amount = withdrawal.amount - withdrawal.fee
                withdrawal.reference = f"WTH_{int(time.time())}_{request.user.id}"
                withdrawal.save()
                
                messages.success(request, 'Withdrawal request submitted successfully!')
                return redirect('profile')
    else:
        form = WithdrawalForm()
    
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    
    return render(request, 'aviator/withdrawal.html', {
        'form': form,
        'payment_methods': payment_methods,
        'wallet': wallet
    })


# AJAX Views for game functionality

@csrf_exempt
@require_http_methods(["GET"])
def game_state(request):
    """Get current game state with enhanced multiplier tracking"""
    try:
        current_game = AviatorGame.objects.filter(
            status__in=['waiting', 'betting', 'flying']
        ).first()
        
        if not current_game:
            # Create new game if none exists
            last_round = AviatorGame.objects.aggregate(
                max_round=models.Max('round_number')
            )['max_round'] or 0
            
            current_game = AviatorGame.objects.create(
                round_number=last_round + 1,
                status='waiting',
                seed=hashlib.md5(f"{time.time()}".encode()).hexdigest(),
                hash_value=hashlib.sha256(f"{time.time()}".encode()).hexdigest()
            )
        
        # Enhanced multiplier calculation for smoother experience
        current_multiplier = 1.00
        if current_game.status == 'flying':
            # Calculate real-time multiplier based on flight time
            if current_game.start_time:
                flight_time = (timezone.now() - current_game.start_time).total_seconds()
                # Smoother multiplier progression
                current_multiplier = 1.00 + (flight_time * 0.1)  # Increases by 0.1 per second
                
                # Cap at game's final multiplier if set
                if current_game.multiplier and current_multiplier >= float(current_game.multiplier):
                    current_multiplier = float(current_game.multiplier)
        
        # Get user's current bet if authenticated
        user_bet = None
        potential_payout = 0
        if request.user.is_authenticated and current_game:
            try:
                bet = AviatorBet.objects.get(
                    user=request.user,
                    game=current_game,
                    status='active'
                )
                user_bet = {
                    'id': str(bet.id),
                    'amount': float(bet.bet_amount),
                    'auto_cash_out': float(bet.auto_cash_out_at) if bet.auto_cash_out_at else None,
                    'status': bet.status
                }
                potential_payout = float(bet.bet_amount) * current_multiplier
            except AviatorBet.DoesNotExist:
                pass
        
        # Get bets for current game
        bets = []
        if current_game:
            game_bets = AviatorBet.objects.filter(
                game=current_game
            ).select_related('user')[:50]
            
            bets = [{
                'username': bet.user.username,
                'amount': float(bet.bet_amount),
                'auto_cash_out': float(bet.auto_cash_out_at) if bet.auto_cash_out_at else None,
                'status': bet.status,
                'cash_out_at': float(bet.cash_out_multiplier) if bet.cash_out_multiplier else None,
                'payout': float(bet.payout_amount)
            } for bet in game_bets]
        
        # Get recent game history
        recent_games = AviatorGame.objects.filter(
            status='completed'
        ).order_by('-round_number')[:20]
        
        history = [{
            'round': game.round_number,
            'multiplier': float(game.multiplier) if game.multiplier else 0,
            'timestamp': game.crash_time.isoformat() if game.crash_time else None
        } for game in recent_games]
        
        response_data = {
            'game': {
                'id': str(current_game.id),
                'round_number': current_game.round_number,
                'status': current_game.status,
                'multiplier': current_multiplier,
                'final_multiplier': float(current_game.multiplier) if current_game.multiplier else None,
                'start_time': current_game.start_time.isoformat() if current_game.start_time else None,
                'betting_end_time': current_game.betting_end_time.isoformat() if current_game.betting_end_time else None,
            },
            'user_bet': user_bet,
            'potential_payout': potential_payout,
            'bets': bets,
            'history': history,
            'server_time': timezone.now().isoformat()
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def place_bet(request):
    """Place a bet on current game"""
    try:
        data = json.loads(request.body)
        bet_amount = Decimal(str(data.get('amount', 0)))
        auto_cash_out = data.get('auto_cash_out')
        
        if bet_amount < Decimal('1.00'):
            return JsonResponse({'error': 'Minimum bet is KES 1.00'}, status=400)
        
        wallet = request.user.wallet
        if bet_amount > wallet.balance:
            return JsonResponse({'error': 'Insufficient balance'}, status=400)
        
        # Get current game in betting phase
        current_game = AviatorGame.objects.filter(
            status='betting'
        ).first()
        
        if not current_game:
            return JsonResponse({'error': 'No active betting round'}, status=400)
        
        # Check if user already has a bet in this game
        existing_bet = AviatorBet.objects.filter(
            user=request.user,
            game=current_game
        ).first()
        
        if existing_bet:
            return JsonResponse({'error': 'You already have a bet in this round'}, status=400)
        
        # Create bet and deduct from wallet
        with transaction.atomic():
            # Deduct amount from wallet
            wallet.balance -= bet_amount
            wallet.save()
            
            # Create bet
            bet = AviatorBet.objects.create(
                user=request.user,
                game=current_game,
                bet_amount=bet_amount,
                auto_cash_out_at=Decimal(str(auto_cash_out)) if auto_cash_out else None
            )
            
            # Create transaction record
            Transaction.objects.create(
                user=request.user,
                transaction_type='bet',
                amount=bet_amount,
                status='completed',
                reference=f"BET_{bet.id}",
                description=f"Bet on Round {current_game.round_number}"
            )
        
        return JsonResponse({
            'success': True,
            'bet_id': str(bet.id),
            'new_balance': float(wallet.balance),
            'bet_amount': float(bet_amount)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def cash_out(request):
    """Cash out active bet with real-time multiplier"""
    try:
        data = json.loads(request.body)
        current_multiplier = Decimal(str(data.get('multiplier', 1.0)))
        
        # Get user's active bet
        current_game = AviatorGame.objects.filter(
            status='flying'
        ).first()
        
        if not current_game:
            return JsonResponse({'error': 'No active game'}, status=400)
        
        bet = AviatorBet.objects.filter(
            user=request.user,
            game=current_game,
            status='active'
        ).first()
        
        if not bet:
            return JsonResponse({'error': 'No active bet found'}, status=400)
        
        # Validate multiplier is reasonable (game hasn't crashed)
        if current_game.multiplier and current_multiplier > current_game.multiplier:
            return JsonResponse({'error': 'Game has already crashed'}, status=400)
        
        # Calculate payout
        payout = bet.bet_amount * current_multiplier
        
        with transaction.atomic():
            # Update bet
            bet.status = 'cashed_out'
            bet.cash_out_multiplier = current_multiplier
            bet.payout_amount = payout
            bet.cashed_out_at = timezone.now()
            bet.save()
            
            # Add winnings to wallet
            wallet = request.user.wallet
            wallet.balance += payout
            wallet.save()
            
            # Create transaction record
            Transaction.objects.create(
                user=request.user,
                transaction_type='win',
                amount=payout,
                status='completed',
                reference=f"WIN_{bet.id}",
                description=f"Winnings from Round {current_game.round_number} at {current_multiplier}x"
            )
            
            # Update user statistics
            user_stats, created = UserGameStatistics.objects.get_or_create(
                user=request.user
            )
            user_stats.total_winnings += payout
            user_stats.games_won += 1
            if current_multiplier > user_stats.highest_multiplier:
                user_stats.highest_multiplier = current_multiplier
            if payout > user_stats.biggest_win:
                user_stats.biggest_win = payout
            user_stats.save()
        
        return JsonResponse({
            'success': True,
            'payout': float(payout),
            'multiplier': float(current_multiplier),
            'new_balance': float(wallet.balance),
            'message': f'Successfully cashed out at {current_multiplier}x!'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def game_history(request):
    """Get game history for statistics"""
    games = AviatorGame.objects.filter(
        status='completed'
    ).order_by('-round_number')[:100]
    
    history = []
    for game in games:
        color = 'green'
        if game.multiplier:
            if game.multiplier < 2:
                color = 'red'
            elif game.multiplier < 10:
                color = 'yellow'
            else:
                color = 'purple'
        
        history.append({
            'round': game.round_number,
            'multiplier': float(game.multiplier) if game.multiplier else 0,
            'color': color,
            'timestamp': game.crash_time.isoformat() if game.crash_time else None
        })
    
    return JsonResponse({'history': history})


@csrf_exempt
@login_required
@require_http_methods(["GET"])
def user_balance(request):
    """Get user's current balance"""
    try:
        wallet = request.user.wallet
        return JsonResponse({
            'balance': float(wallet.balance),
            'bonus_balance': float(wallet.bonus_balance)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def leaderboard_view(request):
    """Leaderboard page"""
    # Get top players by winnings
    top_players = UserGameStatistics.objects.filter(
        total_winnings__gt=0
    ).order_by('-total_winnings')[:20]
    
    # Get top players by win rate
    top_win_rate = UserGameStatistics.objects.filter(
        total_games_played__gte=10
    ).order_by('-win_rate')[:20]
    
    # Get biggest wins
    biggest_wins = UserGameStatistics.objects.filter(
        biggest_win__gt=0
    ).order_by('-biggest_win')[:20]
    
    context = {
        'top_players': top_players,
        'top_win_rate': top_win_rate,
        'biggest_wins': biggest_wins
    }
    
    return render(request, 'aviator/leaderboard.html', context)


@login_required
def transactions_view(request):
    """User transaction history"""
    transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'aviator/transactions.html', {
        'page_obj': page_obj
    })


# Game Engine Functions (called by background tasks/celery)

def start_new_game():
    """Start a new game round"""
    # Get last round number
    last_round = AviatorGame.objects.aggregate(
        max_round=models.Max('round_number')
    )['max_round'] or 0
    
    # Create new game
    new_game = AviatorGame.objects.create(
        round_number=last_round + 1,
        status='betting',
        start_time=timezone.now(),
        betting_end_time=timezone.now() + timedelta(seconds=10),
        seed=hashlib.md5(f"{time.time()}_{random.random()}".encode()).hexdigest(),
        hash_value=hashlib.sha256(f"{time.time()}_{random.random()}".encode()).hexdigest()
    )
    
    return new_game


def end_betting_phase(game_id):
    """End betting phase and start flying"""
    try:
        game = AviatorGame.objects.get(id=game_id)
        game.status = 'flying'
        game.start_time = timezone.now()  # Set actual flight start time
        game.save()
        
        # Generate crash multiplier (provably fair)
        # This is a simplified version - in production, use cryptographic methods
        random.seed(game.seed)
        
        # Generate crash point with house edge
        # Higher probability of low multipliers
        rand_val = random.random()
        
        if rand_val < 0.33:  # 33% chance of crash before 2x
            crash_multiplier = round(1.00 + random.random() * 1.0, 2)
        elif rand_val < 0.66:  # 33% chance of crash between 2x-10x
            crash_multiplier = round(2.00 + random.random() * 8.0, 2)
        else:  # 34% chance of higher multipliers
            crash_multiplier = round(10.0 + random.random() * 90.0, 2)
        
        # Simulate flight time based on multiplier
        flight_duration = min(crash_multiplier * 2, 60)  # Max 60 seconds
        crash_time = timezone.now() + timedelta(seconds=flight_duration)
        
        game.multiplier = Decimal(str(crash_multiplier))
        game.crash_time = crash_time
        game.save()
        
        return game
        
    except AviatorGame.DoesNotExist:
        return None


def crash_game(game_id):
    """Crash the game and process all bets"""
    try:
        game = AviatorGame.objects.get(id=game_id)
        game.status = 'crashed'
        game.save()
        
        # Process all bets
        bets = AviatorBet.objects.filter(game=game, status='active')
        
        total_bet_amount = Decimal('0.00')
        total_payout = Decimal('0.00')
        
        for bet in bets:
            total_bet_amount += bet.bet_amount
            
            # Check if bet should be cashed out
            should_cash_out = False
            cash_out_multiplier = game.multiplier
            
            if bet.auto_cash_out_at and bet.auto_cash_out_at <= game.multiplier:
                should_cash_out = True
                cash_out_multiplier = bet.auto_cash_out_at
            
            if should_cash_out:
                # Winner
                payout = bet.bet_amount * cash_out_multiplier
                bet.status = 'won'
                bet.cash_out_multiplier = cash_out_multiplier
                bet.payout_amount = payout
                total_payout += payout
                
                # Add to user's wallet
                wallet = bet.user.wallet
                wallet.balance += payout
                wallet.save()
                
                # Create win transaction
                Transaction.objects.create(
                    user=bet.user,
                    transaction_type='win',
                    amount=payout,
                    status='completed',
                    reference=f"WIN_{bet.id}",
                    description=f"Win from Round {game.round_number} at {cash_out_multiplier}x"
                )
                
                # Update user stats
                user_stats, created = UserGameStatistics.objects.get_or_create(
                    user=bet.user
                )
                user_stats.total_winnings += payout
                user_stats.games_won += 1
                if cash_out_multiplier > user_stats.highest_multiplier:
                    user_stats.highest_multiplier = cash_out_multiplier
                if payout > user_stats.biggest_win:
                    user_stats.biggest_win = payout
            else:
                # Loser
                bet.status = 'lost'
                
                # Update user stats
                user_stats, created = UserGameStatistics.objects.get_or_create(
                    user=bet.user
                )
                user_stats.games_lost += 1
            
            # Update common user stats
            user_stats.total_games_played += 1
            user_stats.total_amount_bet += bet.bet_amount
            if user_stats.total_games_played > 0:
                user_stats.win_rate = (user_stats.games_won / user_stats.total_games_played) * 100
            user_stats.save()
            
            bet.save()
        
        # Create game statistics
        GameStatistics.objects.create(
            game=game,
            total_bets=bets.count(),
            total_bet_amount=total_bet_amount,
            total_payout=total_payout,
            unique_players=bets.values('user').distinct().count(),
            highest_bet=bets.aggregate(max_bet=models.Max('bet_amount'))['max_bet'] or Decimal('0.00')
        )
        
        # Mark game as completed
        game.status = 'completed'
        game.save()
        
        return game
        
    except AviatorGame.DoesNotExist:
        return None


@csrf_exempt
@require_http_methods(["GET"])
def live_stats(request):
    """Get live statistics for the game"""
    # Get recent statistics
    today = timezone.now().date()
    
    stats = {
        'online_players': GameSession.objects.filter(
            end_time__isnull=True,
            start_time__gte=timezone.now() - timedelta(minutes=10)
        ).count(),
        'todays_games': AviatorGame.objects.filter(
            created_at__date=today,
            status='completed'
        ).count(),
        'total_players': User.objects.filter(is_active=True).count(),
        'biggest_win_today': UserGameStatistics.objects.aggregate(
            max_win=models.Max('biggest_win')
        )['max_win'] or 0,
        'total_bets_today': AviatorBet.objects.filter(
            placed_at__date=today
        ).count()
    }
    
    return JsonResponse(stats)


# Utility view for testing game mechanics
def simulate_game_round(request):
    """Simulate a complete game round (for testing)"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        # Start new game
        game = start_new_game()
        
        # Wait 10 seconds for betting
        time.sleep(1)  # Simulate shorter for testing
        
        # End betting and start flying
        end_betting_phase(game.id)
        
        # Wait for crash
        time.sleep(2)  # Simulate flight time
        
        # Crash game
        crash_game(game.id)
        
        return JsonResponse({
            'success': True,
            'round': game.round_number,
            'multiplier': float(game.multiplier)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
# admin_views.py
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count, Avg, Q, Max
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import json
import threading
import time
import random
import hashlib
from datetime import datetime, timedelta
from django.core.cache import cache

from .models import (
    User, Wallet, Transaction, AviatorGame, AviatorBet, 
    GameStatistics, UserGameStatistics, GameSettings,
    SystemConfiguration, GameSession, AuditLog
)

class GameEngine:
    """Main game engine for automated Aviator game management"""
    
    def __init__(self):
        self.running = False
        self.game_thread = None
        self.current_game = None
        self.settings = self.load_settings()
        
    def load_settings(self):
        """Load game settings from database"""
        try:
            settings = GameSettings.objects.first()
            if not settings:
                settings = GameSettings.objects.create()
            return {
                'house_edge': float(settings.house_edge),
                'betting_duration': settings.betting_phase_duration,
                'game_interval': settings.game_interval,
                'min_bet': float(settings.min_bet_amount),
                'max_bet': float(settings.max_bet_amount),
                'maintenance_mode': settings.is_maintenance_mode
            }
        except Exception as e:
            return {
                'house_edge': 3.0,
                'betting_duration': 10,
                'game_interval': 5,
                'min_bet': 1.0,
                'max_bet': 10000.0,
                'maintenance_mode': False
            }
    
    def start(self):
        """Start the game engine"""
        if self.running:
            return False
            
        self.running = True
        self.game_thread = threading.Thread(target=self._game_loop, daemon=True)
        self.game_thread.start()
        
        # Log system start
        self._log_event('SYSTEM_START', 'Game engine started')
        return True
    
    def stop(self):
        """Stop the game engine"""
        self.running = False
        if self.game_thread:
            self.game_thread.join(timeout=5)
        
        # Complete any active game
        if self.current_game and self.current_game.status in ['betting', 'flying']:
            self._force_crash_game(self.current_game.id)
        
        self._log_event('SYSTEM_STOP', 'Game engine stopped')
        return True
    
    def force_crash(self):
        """Force crash current game"""
        if self.current_game and self.current_game.status == 'flying':
            self._force_crash_game(self.current_game.id)
            return True
        return False
    
    def update_settings(self, new_settings):
        """Update game settings"""
        self.settings.update(new_settings)
        
        # Update database
        game_settings = GameSettings.objects.first()
        if game_settings:
            game_settings.house_edge = Decimal(str(new_settings.get('house_edge', 3.0)))
            game_settings.betting_phase_duration = new_settings.get('betting_duration', 10)
            game_settings.game_interval = new_settings.get('game_interval', 5)
            game_settings.save()
        
        self._log_event('SETTINGS_UPDATE', f'Settings updated: {new_settings}')
    
    def _game_loop(self):
        """Main game loop - runs continuously"""
        while self.running:
            try:
                if self.settings.get('maintenance_mode', False):
                    time.sleep(5)
                    continue
                
                # Start new game
                game = self._start_new_game()
                if not game:
                    time.sleep(1)
                    continue
                
                self.current_game = game
                
                # Betting phase
                self._log_event('GAME_START', f'Round {game.round_number} - Betting phase started')
                time.sleep(self.settings['betting_duration'])
                
                if not self.running:
                    break
                
                # End betting, start flying
                game = self._start_flying_phase(game.id)
                if not game:
                    continue
                
                # Flying phase with crash calculation
                crash_multiplier, flight_time = self._calculate_crash_point()
                self._log_event('GAME_FLYING', f'Round {game.round_number} - Flying (will crash at {crash_multiplier}x)')
                
                # Simulate flight
                start_time = time.time()
                multiplier = 1.0
                
                while self.running and multiplier < crash_multiplier:
                    elapsed = time.time() - start_time
                    multiplier = self._calculate_current_multiplier(elapsed, crash_multiplier, flight_time)
                    
                    # Update game state in cache for real-time updates
                    cache.set(f'game_{game.id}_multiplier', multiplier, 60)
                    
                    # Check for manual cash outs
                    self._process_auto_cashouts(game.id, multiplier)
                    
                    time.sleep(0.1)  # 100ms updates
                
                if not self.running:
                    break
                
                # Crash the game
                self._crash_game(game.id, crash_multiplier)
                self._log_event('GAME_CRASH', f'Round {game.round_number} - Crashed at {crash_multiplier}x')
                
                # Wait before next game
                time.sleep(self.settings['game_interval'])
                
            except Exception as e:
                self._log_event('ERROR', f'Game loop error: {str(e)}')
                time.sleep(5)
    
    def _start_new_game(self):
        """Create a new game round"""
        try:
            with transaction.atomic():
                # Get last round number
                last_round = AviatorGame.objects.aggregate(
                    max_round=Max('round_number')
                )['max_round'] or 0
                
                # Generate provably fair seed
                seed = hashlib.md5(f"{time.time()}_{random.random()}".encode()).hexdigest()
                hash_value = hashlib.sha256(seed.encode()).hexdigest()
                
                game = AviatorGame.objects.create(
                    round_number=last_round + 1,
                    status='betting',
                    start_time=timezone.now(),
                    betting_end_time=timezone.now() + timedelta(seconds=self.settings['betting_duration']),
                    seed=seed,
                    hash_value=hash_value
                )
                
                return game
        except Exception as e:
            self._log_event('ERROR', f'Failed to create game: {str(e)}')
            return None
    
    def _start_flying_phase(self, game_id):
        """Transition game from betting to flying"""
        try:
            game = AviatorGame.objects.get(id=game_id)
            game.status = 'flying'
            game.save()
            return game
        except AviatorGame.DoesNotExist:
            return None
    
    def _calculate_crash_point(self):
        """Calculate when the game will crash using house edge"""
        # Provably fair crash calculation
        # This is simplified - in production, use cryptographic methods
        
        house_edge = self.settings['house_edge'] / 100
        
        # Generate random number
        rand = random.random()
        
        # Apply house edge to crash calculation
        # Higher house edge = more low multipliers
        if rand < (0.5 + house_edge):  # Increased probability of low crashes
            crash_multiplier = round(1.0 + random.random() * 1.5, 2)  # 1.0x - 2.5x
            flight_time = crash_multiplier * 0.8
        elif rand < (0.8 + house_edge/2):
            crash_multiplier = round(2.5 + random.random() * 5.0, 2)  # 2.5x - 7.5x
            flight_time = crash_multiplier * 0.6
        elif rand < (0.95 + house_edge/4):
            crash_multiplier = round(7.5 + random.random() * 15.0, 2)  # 7.5x - 22.5x
            flight_time = crash_multiplier * 0.4
        else:
            crash_multiplier = round(22.5 + random.random() * 77.5, 2)  # 22.5x - 100x
            flight_time = crash_multiplier * 0.3
        
        return crash_multiplier, max(flight_time, 1.0)
    
    def _calculate_current_multiplier(self, elapsed_time, target_multiplier, flight_time):
        """Calculate current multiplier based on elapsed time"""
        if elapsed_time >= flight_time:
            return target_multiplier
        
        # Exponential growth curve
        progress = elapsed_time / flight_time
        return 1.0 + (target_multiplier - 1.0) * progress
    
    def _process_auto_cashouts(self, game_id, current_multiplier):
        """Process automatic cash outs"""
        try:
            # Get bets with auto cash out at current multiplier
            bets_to_cash_out = AviatorBet.objects.filter(
                game_id=game_id,
                status='active',
                auto_cash_out_at__lte=Decimal(str(current_multiplier)),
                auto_cash_out_at__isnull=False
            )
            
            for bet in bets_to_cash_out:
                self._process_cashout(bet, bet.auto_cash_out_at)
                
        except Exception as e:
            self._log_event('ERROR', f'Auto cashout error: {str(e)}')
    
    def _process_cashout(self, bet, multiplier):
        """Process individual bet cashout"""
        try:
            with transaction.atomic():
                payout = bet.bet_amount * multiplier
                
                # Update bet
                bet.status = 'won'
                bet.cash_out_multiplier = multiplier
                bet.payout_amount = payout
                bet.cashed_out_at = timezone.now()
                bet.save()
                
                # Add to wallet
                wallet = bet.user.wallet
                wallet.balance += payout
                wallet.save()
                
                # Create transaction
                Transaction.objects.create(
                    user=bet.user,
                    transaction_type='win',
                    amount=payout,
                    status='completed',
                    reference=f"WIN_{bet.id}",
                    description=f"Win from Round {bet.game.round_number} at {multiplier}x"
                )
                
                self._log_event('CASHOUT', f'{bet.user.username} cashed out {payout} at {multiplier}x')
        except Exception as e:
            self._log_event('ERROR', f'Cashout error: {str(e)}')
    
    def _crash_game(self, game_id, crash_multiplier):
        """Crash the game and process all remaining bets"""
        try:
            with transaction.atomic():
                game = AviatorGame.objects.get(id=game_id)
                game.status = 'crashed'
                game.multiplier = Decimal(str(crash_multiplier))
                game.crash_time = timezone.now()
                game.save()
                
                # Process remaining active bets (losers)
                losing_bets = AviatorBet.objects.filter(
                    game=game,
                    status='active'
                )
                
                total_bet_amount = Decimal('0.00')
                total_payout = Decimal('0.00')
                
                for bet in losing_bets:
                    bet.status = 'lost'
                    bet.save()
                    total_bet_amount += bet.bet_amount
                    
                    # Update user stats for loss
                    self._update_user_stats(bet.user, bet.bet_amount, Decimal('0.00'), False)
                
                # Calculate payouts for winners
                winning_bets = AviatorBet.objects.filter(
                    game=game,
                    status='won'
                )
                
                for bet in winning_bets:
                    total_payout += bet.payout_amount
                    # Update user stats for win
                    self._update_user_stats(bet.user, bet.bet_amount, bet.payout_amount, True)
                
                # Create game statistics
                GameStatistics.objects.create(
                    game=game,
                    total_bets=AviatorBet.objects.filter(game=game).count(),
                    total_bet_amount=total_bet_amount + sum(bet.bet_amount for bet in winning_bets),
                    total_payout=total_payout,
                    unique_players=AviatorBet.objects.filter(game=game).values('user').distinct().count(),
                    highest_bet=AviatorBet.objects.filter(game=game).aggregate(
                        max_bet=Max('bet_amount')
                    )['max_bet'] or Decimal('0.00')
                )
                
                # Mark game as completed
                game.status = 'completed'
                game.save()
                
                # Clear cache
                cache.delete(f'game_{game.id}_multiplier')
                
        except Exception as e:
            self._log_event('ERROR', f'Game crash error: {str(e)}')
    
    def _force_crash_game(self, game_id):
        """Force crash current game"""
        current_multiplier = cache.get(f'game_{game_id}_multiplier', 1.0)
        self._crash_game(game_id, max(current_multiplier, 1.0))
    
    def _update_user_stats(self, user, bet_amount, payout, won):
        """Update user game statistics"""
        try:
            stats, created = UserGameStatistics.objects.get_or_create(user=user)
            
            stats.total_games_played += 1
            stats.total_amount_bet += bet_amount
            
            if won:
                stats.games_won += 1
                stats.total_winnings += payout
                if payout > stats.biggest_win:
                    stats.biggest_win = payout
            else:
                stats.games_lost += 1
            
            # Calculate win rate
            if stats.total_games_played > 0:
                stats.win_rate = (stats.games_won / stats.total_games_played) * 100
            
            stats.save()
        except Exception as e:
            self._log_event('ERROR', f'Stats update error: {str(e)}')
    
    def _log_event(self, event_type, message):
        """Log system events"""
        try:
            AuditLog.objects.create(
                action_type='system_event',
                description=f'{event_type}: {message}',
                ip_address='127.0.0.1',
                additional_data={'event_type': event_type}
            )
        except Exception:
            pass  # Don't let logging errors crash the system

# Global game engine instance
game_engine = GameEngine()

@staff_member_required
def admin_dashboard(request):
    """Main admin dashboard view"""
    # Get basic statistics
    today = timezone.now().date()
    
    stats = {
        'total_users': User.objects.count(),
        'active_games_today': AviatorGame.objects.filter(
            created_at__date=today
        ).count(),
        'total_revenue_today': Transaction.objects.filter(
            transaction_type='bet',
            created_at__date=today,
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00'),
        'active_players': GameSession.objects.filter(
            end_time__isnull=True,
            start_time__gte=timezone.now() - timedelta(minutes=30)
        ).count()
    }
    
    # Get current game
    current_game = AviatorGame.objects.filter(
        status__in=['waiting', 'betting', 'flying']
    ).first()
    
    # Get recent games
    recent_games = AviatorGame.objects.filter(
        status='completed'
    ).order_by('-round_number')[:10]
    
    context = {
        'stats': stats,
        'current_game': current_game,
        'recent_games': recent_games,
        'engine_running': game_engine.running,
        'game_settings': game_engine.settings
    }
    
    return render(request, 'admin/aviator_dashboard.html', context)

@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def start_system(request):
    """Start the game engine"""
    try:
        success = game_engine.start()
        if success:
            return JsonResponse({'status': 'success', 'message': 'System started'})
        else:
            return JsonResponse({'status': 'error', 'message': 'System already running'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def stop_system(request):
    """Stop the game engine"""
    try:
        success = game_engine.stop()
        if success:
            return JsonResponse({'status': 'success', 'message': 'System stopped'})
        else:
            return JsonResponse({'status': 'error', 'message': 'System not running'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def force_crash(request):
    """Force crash current game"""
    try:
        success = game_engine.force_crash()
        if success:
            return JsonResponse({'status': 'success', 'message': 'Game crashed'})
        else:
            return JsonResponse({'status': 'error', 'message': 'No active game to crash'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def update_settings(request):
    """Update game settings"""
    try:
        data = json.loads(request.body)
        game_engine.update_settings(data)
        return JsonResponse({'status': 'success', 'message': 'Settings updated'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
def game_data(request):
    """Get real-time game data for dashboard"""
    try:
        # Current game data
        current_game = AviatorGame.objects.filter(
            status__in=['waiting', 'betting', 'flying']
        ).first()
        
        game_data = {}
        if current_game:
            # Get current multiplier from cache if flying
            current_multiplier = 1.0
            if current_game.status == 'flying':
                current_multiplier = cache.get(f'game_{current_game.id}_multiplier', 1.0)
            
            # Get bets for current game
            current_bets = AviatorBet.objects.filter(game=current_game)
            total_bet_amount = current_bets.aggregate(Sum('bet_amount'))['bet_amount__sum'] or Decimal('0.00')
            
            game_data = {
                'id': str(current_game.id),
                'round_number': current_game.round_number,
                'status': current_game.status,
                'multiplier': round(current_multiplier, 2),
                'player_count': current_bets.count(),
                'total_bets': float(total_bet_amount),
                'start_time': current_game.start_time.isoformat() if current_game.start_time else None
            }
        
        # Statistics
        today = timezone.now().date()
        stats = {
            'total_revenue': float(Transaction.objects.filter(
                transaction_type='bet',
                status='completed'
            ).aggregate(Sum('amount'))['amount__sum'] or 0),
            'active_players': GameSession.objects.filter(
                end_time__isnull=True,
                start_time__gte=timezone.now() - timedelta(minutes=30)
            ).count(),
            'games_today': AviatorGame.objects.filter(
                created_at__date=today,
                status='completed'
            ).count(),
            'house_profit': float(
                (Transaction.objects.filter(transaction_type='bet', status='completed').aggregate(
                    Sum('amount'))['amount__sum'] or 0) -
                (Transaction.objects.filter(transaction_type='win', status='completed').aggregate(
                    Sum('amount'))['amount__sum'] or 0)
            )
        }
        
        # Live bets
        live_bets = []
        if current_game:
            bets = AviatorBet.objects.filter(
                game=current_game,
                status='active'
            ).select_related('user')[:10]
            
            live_bets = [{
                'username': bet.user.username,
                'amount': float(bet.bet_amount),
                'auto_cash_out': float(bet.auto_cash_out_at) if bet.auto_cash_out_at else None
            } for bet in bets]
        
        # Game history
        recent_games = AviatorGame.objects.filter(
            status='completed'
        ).order_by('-round_number')[:20]
        
        history = []
        for game in recent_games:
            stats_obj = GameStatistics.objects.filter(game=game).first()
            history.append({
                'round': game.round_number,
                'multiplier': float(game.multiplier) if game.multiplier else 0,
                'players': stats_obj.total_bets if stats_obj else 0,
                'total_bets': float(stats_obj.total_bet_amount) if stats_obj else 0,
                'total_payout': float(stats_obj.total_payout) if stats_obj else 0,
                'house_profit': float(stats_obj.total_bet_amount - stats_obj.total_payout) if stats_obj else 0,
                'timestamp': game.crash_time.isoformat() if game.crash_time else game.created_at.isoformat()
            })
        
        return JsonResponse({
            'current_game': game_data,
            'stats': stats,
            'live_bets': live_bets,
            'history': history,
            'engine_status': 'running' if game_engine.running else 'stopped'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@staff_member_required
def system_logs(request):
    """Get system logs"""
    logs = AuditLog.objects.filter(
        action_type='system_event'
    ).order_by('-created_at')[:100]
    
    log_data = [{
        'timestamp': log.created_at.isoformat(),
        'message': log.description,
        'type': log.additional_data.get('event_type', 'info') if log.additional_data else 'info'
    } for log in logs]
    
    return JsonResponse({'logs': log_data})

@staff_member_required
def player_management(request):
    """Get player data for management"""
    players = User.objects.filter(
        is_active=True
    ).select_related('wallet').order_by('-date_joined')[:50]
    
    player_data = []
    for player in players:
        try:
            wallet = player.wallet if hasattr(player, 'wallet') else None
            stats = getattr(player, 'game_stats', None)
            
            player_data.append({
                'id': player.id,
                'username': player.username,
                'email': player.email,
                'balance': float(wallet.balance) if wallet else 0,
                'total_bets': float(stats.total_amount_bet) if stats else 0,
                'total_winnings': float(stats.total_winnings) if stats else 0,
                'games_played': stats.total_games_played if stats else 0,
                'win_rate': float(stats.win_rate) if stats else 0,
                'status': 'active' if player.is_active else 'inactive',
                'joined_date': player.date_joined.isoformat(),
                'kyc_status': getattr(player, 'kyc_status', 'pending')
            })
        except Exception as e:
            continue
    
    return JsonResponse({'players': player_data})

@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def toggle_maintenance(request):
    """Toggle maintenance mode"""
    try:
        settings = GameSettings.objects.first()
        if settings:
            settings.is_maintenance_mode = not settings.is_maintenance_mode
            settings.save()
            
            game_engine.settings['maintenance_mode'] = settings.is_maintenance_mode
            
            status = 'enabled' if settings.is_maintenance_mode else 'disabled'
            return JsonResponse({
                'status': 'success', 
                'message': f'Maintenance mode {status}',
                'maintenance_mode': settings.is_maintenance_mode
            })
        else:
            return JsonResponse({'status': 'error', 'message': 'Settings not found'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def suspend_player(request):
    """Suspend a player"""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        user = User.objects.get(id=user_id)
        user.is_active = False
        user.save()
        
        # Log the action
        AuditLog.objects.create(
            user=request.user,
            action_type='account_suspended',
            description=f'Player {user.username} suspended by admin',
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            additional_data={'suspended_user_id': user_id}
        )
        
        return JsonResponse({'status': 'success', 'message': 'Player suspended'})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
def analytics_data(request):
    """Get analytics data for charts"""
    try:
        # Revenue data for last 24 hours
        now = timezone.now()
        hours_ago_24 = now - timedelta(hours=24)
        
        revenue_data = []
        for i in range(24):
            hour_start = hours_ago_24 + timedelta(hours=i)
            hour_end = hour_start + timedelta(hours=1)
            
            revenue = Transaction.objects.filter(
                transaction_type='bet',
                status='completed',
                created_at__gte=hour_start,
                created_at__lt=hour_end
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            revenue_data.append({
                'hour': hour_start.strftime('%H:%M'),
                'revenue': float(revenue)
            })
        
        # Multiplier distribution
        recent_games = AviatorGame.objects.filter(
            status='completed',
            multiplier__isnull=False,
            created_at__gte=now - timedelta(days=7)
        ).values_list('multiplier', flat=True)
        
        multiplier_distribution = {
            'low': 0,      # < 2x
            'medium': 0,   # 2x - 5x  
            'high': 0,     # 5x - 10x
            'extreme': 0   # > 10x
        }
        
        for multiplier in recent_games:
            multiplier = float(multiplier)
            if multiplier < 2:
                multiplier_distribution['low'] += 1
            elif multiplier < 5:
                multiplier_distribution['medium'] += 1
            elif multiplier < 10:
                multiplier_distribution['high'] += 1
            else:
                multiplier_distribution['extreme'] += 1
        
        return JsonResponse({
            'revenue_data': revenue_data,
            'multiplier_distribution': multiplier_distribution
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)