# tasks.py - Celery tasks for background processing
from celery import shared_task
from django.utils import timezone
from django.db.models import Sum, Count
from decimal import Decimal
import logging
from datetime import timedelta

from .models import (
    AviatorGame, AviatorBet, Transaction, User, 
    UserGameStatistics, GameStatistics, AuditLog
)
from .views import game_engine

logger = logging.getLogger(__name__)

@shared_task
def start_game_engine():
    """Start the game engine via Celery"""
    try:
        success = game_engine.start()
        if success:
            logger.info("Game engine started successfully via Celery")
        else:
            logger.warning("Game engine was already running")
        return success
    except Exception as e:
        logger.error(f"Failed to start game engine: {str(e)}")
        return False

@shared_task
def stop_game_engine():
    """Stop the game engine via Celery"""
    try:
        success = game_engine.stop()
        if success:
            logger.info("Game engine stopped successfully via Celery")
        else:
            logger.warning("Game engine was not running")
        return success
    except Exception as e:
        logger.error(f"Failed to stop game engine: {str(e)}")
        return False

@shared_task
def cleanup_old_games():
    """Clean up old game data to prevent database bloat"""
    try:
        # Delete games older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_games = AviatorGame.objects.filter(
            created_at__lt=cutoff_date,
            status='completed'
        )
        
        count = old_games.count()
        old_games.delete()
        
        logger.info(f"Cleaned up {count} old games")
        return count
        
    except Exception as e:
        logger.error(f"Failed to cleanup old games: {str(e)}")
        return 0

@shared_task
def generate_daily_report():
    """Generate daily statistics report"""
    try:
        today = timezone.now().date()
        
        # Calculate daily statistics
        daily_stats = {
            'date': today.isoformat(),
            'total_games': AviatorGame.objects.filter(
                created_at__date=today,
                status='completed'
            ).count(),
            'total_bets': AviatorBet.objects.filter(
                placed_at__date=today
            ).count(),
            'total_bet_amount': float(
                AviatorBet.objects.filter(
                    placed_at__date=today
                ).aggregate(Sum('bet_amount'))['bet_amount__sum'] or 0
            ),
            'total_payout': float(
                Transaction.objects.filter(
                    created_at__date=today,
                    transaction_type='win',
                    status='completed'
                ).aggregate(Sum('amount'))['amount__sum'] or 0
            ),
            'unique_players': User.objects.filter(
                aviator_bets__placed_at__date=today
            ).distinct().count(),
            'new_registrations': User.objects.filter(
                date_joined__date=today
            ).count()
        }
        
        # Calculate house profit
        daily_stats['house_profit'] = daily_stats['total_bet_amount'] - daily_stats['total_payout']
        daily_stats['profit_margin'] = (
            daily_stats['house_profit'] / daily_stats['total_bet_amount'] * 100
            if daily_stats['total_bet_amount'] > 0 else 0
        )
        
        # Log the report
        AuditLog.objects.create(
            action_type='daily_report',
            description=f"Daily report generated for {today}",
            ip_address='127.0.0.1',
            additional_data=daily_stats
        )
        
        logger.info(f"Daily report generated: {daily_stats}")
        return daily_stats
        
    except Exception as e:
        logger.error(f"Failed to generate daily report: {str(e)}")
        return None

@shared_task
def update_user_statistics():
    """Update user statistics - run periodically"""
    try:
        updated_count = 0
        
        # Get users who have played games but need stats update
        users_to_update = User.objects.filter(
            aviator_bets__isnull=False
        ).distinct()
        
        for user in users_to_update:
            try:
                stats, created = UserGameStatistics.objects.get_or_create(user=user)
                
                # Recalculate all stats
                user_bets = AviatorBet.objects.filter(user=user)
                
                stats.total_games_played = user_bets.count()
                stats.total_amount_bet = user_bets.aggregate(
                    Sum('bet_amount')
                )['bet_amount__sum'] or Decimal('0.00')
                
                winning_bets = user_bets.filter(status__in=['won', 'cashed_out'])
                stats.games_won = winning_bets.count()
                stats.games_lost = user_bets.filter(status='lost').count()
                
                stats.total_winnings = winning_bets.aggregate(
                    Sum('payout_amount')
                )['payout_amount__sum'] or Decimal('0.00')
                
                # Biggest win
                biggest_win = winning_bets.aggregate(
                    max_payout=Sum('payout_amount')
                )['max_payout']
                if biggest_win:
                    stats.biggest_win = biggest_win
                
                # Highest multiplier
                highest_multiplier = winning_bets.filter(
                    cash_out_multiplier__isnull=False
                ).aggregate(
                    max_multiplier=Sum('cash_out_multiplier')
                )['max_multiplier']
                if highest_multiplier:
                    stats.highest_multiplier = highest_multiplier
                
                # Win rate
                if stats.total_games_played > 0:
                    stats.win_rate = (stats.games_won / stats.total_games_played) * 100
                
                # Average cash out
                if stats.games_won > 0:
                    avg_multiplier = winning_bets.filter(
                        cash_out_multiplier__isnull=False
                    ).aggregate(
                        avg_multiplier=Sum('cash_out_multiplier')
                    )['avg_multiplier']
                    if avg_multiplier:
                        stats.average_cash_out = avg_multiplier / stats.games_won
                
                stats.save()
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to update stats for user {user.username}: {str(e)}")
                continue
        
        logger.info(f"Updated statistics for {updated_count} users")
        return updated_count
        
    except Exception as e:
        logger.error(f"Failed to update user statistics: {str(e)}")
        return 0

@shared_task
def monitor_system_health():
    """Monitor system health and alert if issues detected"""
    try:
        issues = []
        
        # Check if game engine is running
        if not game_engine.running:
            issues.append("Game engine is not running")
        
        # Check for stuck games
        stuck_games = AviatorGame.objects.filter(
            status__in=['betting', 'flying'],
            created_at__lt=timezone.now() - timedelta(minutes=10)
        )
        
        if stuck_games.exists():
            issues.append(f"{stuck_games.count()} games appear to be stuck")
            # Auto-fix stuck games
            for game in stuck_games:
                try:
                    game_engine._force_crash_game(game.id)
                except Exception as e:
                    logger.error(f"Failed to fix stuck game {game.id}: {str(e)}")
        
        # Check database connections
        try:
            User.objects.count()
        except Exception:
            issues.append("Database connection issues detected")
        
        # Check for unusual betting patterns
        recent_bets = AviatorBet.objects.filter(
            placed_at__gte=timezone.now() - timedelta(hours=1)
        )
        
        if recent_bets.exists():
            avg_bet = recent_bets.aggregate(Sum('bet_amount'))['bet_amount__sum'] / recent_bets.count()
            max_bet = recent_bets.aggregate(Sum('bet_amount'))['bet_amount__sum']
            
            # Alert if there are unusually large bets
            if max_bet > avg_bet * 100:
                issues.append("Unusually large bets detected - possible fraud")
        
        # Log health check
        health_status = "healthy" if not issues else "issues_detected"
        
        AuditLog.objects.create(
            action_type='health_check',
            description=f"System health check: {health_status}",
            ip_address='127.0.0.1',
            additional_data={
                'status': health_status,
                'issues': issues,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        if issues:
            logger.warning(f"System health issues detected: {issues}")
        else:
            logger.info("System health check passed")
        
        return {
            'status': health_status,
            'issues': issues
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            'status': 'error',
            'issues': [f"Health check failed: {str(e)}"]
        }

@shared_task
def backup_critical_data():
    """Backup critical game data"""
    try:
        today = timezone.now().date()
        
        # Export today's game data
        games_today = AviatorGame.objects.filter(
            created_at__date=today,
            status='completed'
        ).values(
            'round_number', 'multiplier', 'start_time', 
            'crash_time', 'seed', 'hash_value'
        )
        
        # Export today's bets
        bets_today = AviatorBet.objects.filter(
            placed_at__date=today
        ).values(
            'game__round_number', 'user__username', 'bet_amount',
            'cash_out_multiplier', 'payout_amount', 'status'
        )
        
        backup_data = {
            'date': today.isoformat(),
            'games': list(games_today),
            'bets': list(bets_today),
            'games_count': len(games_today),
            'bets_count': len(bets_today)
        }
        
        # Log backup creation
        AuditLog.objects.create(
            action_type='data_backup',
            description=f"Daily backup created for {today}",
            ip_address='127.0.0.1',
            additional_data=backup_data
        )
        
        logger.info(f"Backup created: {backup_data['games_count']} games, {backup_data['bets_count']} bets")
        return backup_data
        
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return None
