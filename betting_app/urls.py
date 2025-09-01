from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views


urlpatterns = [
    # Main game page
    path('', views.home, name='home'),
    
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    
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
]