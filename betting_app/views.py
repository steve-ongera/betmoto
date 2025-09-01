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
    """Get current game state"""
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
                'multiplier': float(current_game.multiplier) if current_game.multiplier else 1.0,
                'start_time': current_game.start_time.isoformat() if current_game.start_time else None,
                'betting_end_time': current_game.betting_end_time.isoformat() if current_game.betting_end_time else None,
            },
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
            'new_balance': float(wallet.balance)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def cash_out(request):
    """Cash out active bet"""
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
            'new_balance': float(wallet.balance)
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