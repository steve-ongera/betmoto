from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views


urlpatterns = [
    # Main game page
    path('', views.home, name='home'),
    
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # User account
    path('profile/', views.profile_view, name='profile'),
    path('deposit/', views.deposit_view, name='deposit'),
    path('withdrawal/', views.withdrawal_view, name='withdrawal'),
    path('transactions/', views.transactions_view, name='transactions'),
    
    # Game pages
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    
    # AJAX API endpoints
    path('api/game-state/', views.game_state, name='game_state'),
    path('api/place-bet/', views.place_bet, name='place_bet'),
    path('api/cash-out/', views.cash_out, name='cash_out'),
    path('api/game-history/', views.game_history, name='game_history'),
    path('api/user-balance/', views.user_balance, name='user_balance'),
    path('api/live-stats/', views.live_stats, name='live_stats'),
    
    # Testing (remove in production)
    path('api/simulate-round/', views.simulate_game_round, name='simulate_round'),

    # Admin Dashboard
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # System Control
    path('admin-start-system/', views.start_system, name='admin_start_system'),
    path('admin-stop-system/', views.stop_system, name='admin_stop_system'),
    path('admin-force-crash/', views.force_crash, name='admin_force_crash'),
    path('admin-toggle-maintenance/', views.toggle_maintenance, name='admin_toggle_maintenance'),
    
    # Settings
    path('admin-update-settings/', views.update_settings, name='admin_update_settings'),
    
    # Data endpoints
    path('admin-game-data/', views.game_data, name='admin_game_data'),
    path('admin-system-logs/', views.system_logs, name='admin_system_logs'),
    path('admin-player-management/', views.player_management, name='admin_player_management'),
    path('admin-analytics-data/', views.analytics_data, name='admin_analytics_data'),
    
    # Player management
    path('admin-suspend-player/', views.suspend_player, name='admin_suspend_player'),
]