# BetMoto - Aviator Betting Web Application

A Django-based aviator betting platform similar to Betika, featuring real-time multiplayer crash games, wallet management, and mobile money integration.

## 🚀 Features

### Core Features
- **Real-time Aviator Game**: Multiplayer crash game with live multipliers
- **User Authentication**: Phone-based registration with OTP verification
- **Wallet System**: Secure balance management and transaction tracking
- **Mobile Money Integration**: M-Pesa deposits and withdrawals
- **Live Chat**: Real-time player communication during games
- **Betting System**: Place bets with auto cash-out functionality
- **Bonus System**: Welcome bonuses, referral rewards, and promotional campaigns
- **Admin Dashboard**: Comprehensive game and user management

### Game Features
- Live multiplier display with smooth animations
- Auto cash-out at specified multipliers
- Real-time betting statistics
- Game history and analytics
- Leaderboards and rankings
- Live player feed

## 🛠️ Technology Stack

- **Backend**: Django 4.2+
- **Database**: PostgreSQL (recommended) / SQLite (development)
- **Real-time**: Django Channels + WebSockets
- **Cache**: Redis
- **Task Queue**: Celery
- **Payment**: M-Pesa API Integration
- **Frontend**: HTML, CSS, JavaScript (with WebSocket support)
- **Deployment**: Docker, Nginx, Gunicorn

## 📋 Requirements

```
Django>=4.2.0
djangorestframework>=3.14.0
django-channels>=4.0.0
channels-redis>=4.1.0
celery>=5.3.0
redis>=4.5.0
psycopg2-binary>=2.9.0
python-decouple>=3.8
Pillow>=10.0.0
django-cors-headers>=4.0.0
```

## 🔧 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/betmoto.git
cd betmoto
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Create a `.env` file in the project root:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/betmoto_db

# Redis
REDIS_URL=redis://localhost:6379/0

# M-Pesa Configuration
MPESA_CONSUMER_KEY=your-mpesa-consumer-key
MPESA_CONSUMER_SECRET=your-mpesa-consumer-secret
MPESA_SHORTCODE=your-shortcode
MPESA_PASSKEY=your-passkey
MPESA_ENVIRONMENT=sandbox  # or production

# SMS Configuration
SMS_API_KEY=your-sms-api-key
SMS_SENDER_ID=BETMOTO

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### 5. Database Setup
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 6. Load Initial Data
```bash
python manage.py loaddata fixtures/initial_data.json
```

### 7. Start Redis Server
```bash
redis-server
```

### 8. Start Celery Worker (New Terminal)
```bash
celery -A betmoto worker --loglevel=info
```

### 9. Start Celery Beat (New Terminal)
```bash
celery -A betmoto beat --loglevel=info
```

### 10. Run Development Server
```bash
python manage.py runserver
```

## 🏗️ Project Structure

```
betmoto/
├── betmoto/                 # Main project directory
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── testing.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py
├── apps/
│   ├── accounts/            # User management
│   ├── games/               # Aviator game logic
│   ├── payments/            # Payment processing
│   ├── chat/                # Live chat system
│   ├── notifications/       # Notification system
│   └── analytics/           # Game analytics
├── static/                  # Static files
├── media/                   # Media uploads
├── templates/               # HTML templates
├── fixtures/                # Initial data
├── requirements/            # Requirements files
├── docker/                  # Docker configuration
└── docs/                    # Documentation
```

## 🎮 Key Models Overview

### User Management
- **User**: Extended Django user with phone verification
- **UserProfile**: Additional user information and preferences
- **Wallet**: User balance and transaction management
- **KYCDocument**: Identity verification documents

### Game System
- **AviatorGame**: Individual game rounds with multipliers
- **AviatorBet**: User bets with auto cash-out
- **GameSession**: User session tracking
- **GameStatistics**: Analytics and metrics

### Payment System
- **PaymentMethod**: Available payment options
- **Transaction**: All financial transactions
- **Deposit**: Deposit records
- **Withdrawal**: Withdrawal requests
- **MPesaTransaction**: M-Pesa specific transactions

### Bonus System
- **Bonus**: Promotional campaigns
- **UserBonus**: User-specific bonus tracking
- **ReferralReward**: Referral system rewards

## 🔌 API Endpoints

### Authentication
```
POST /api/auth/register/          # User registration
POST /api/auth/login/             # User login
POST /api/auth/verify-phone/      # Phone verification
POST /api/auth/logout/            # User logout
```

### Game Management
```
GET  /api/games/current/          # Current game status
POST /api/games/bet/              # Place bet
POST /api/games/cashout/          # Manual cash out
GET  /api/games/history/          # Game history
GET  /api/games/statistics/       # User statistics
```

### Wallet & Payments
```
GET  /api/wallet/balance/         # Get wallet balance
POST /api/wallet/deposit/         # Initiate deposit
POST /api/wallet/withdraw/        # Request withdrawal
GET  /api/wallet/transactions/    # Transaction history
```

### Real-time WebSocket Endpoints
```
ws://localhost:8000/ws/game/      # Game updates
ws://localhost:8000/ws/chat/      # Live chat
ws://localhost:8000/ws/notifications/ # Notifications
```

## 🎯 Game Logic

### Aviator Game Flow
1. **Game Start**: New round begins every 30 seconds
2. **Betting Phase**: 10-second window for placing bets
3. **Flight Phase**: Multiplier increases from 1.00x
4. **Crash**: Random crash point between 1.00x - 50.00x
5. **Payout**: Winners receive bet × multiplier

### Auto Cash-Out
- Players can set automatic cash-out multipliers
- System automatically cashes out when target reached
- Prevents losses from late manual cash-outs

## 💰 Payment Integration

### M-Pesa Integration
- **STK Push**: Automated payment requests
- **C2B Callbacks**: Real-time payment confirmations
- **B2C Payments**: Automated withdrawals
- **Transaction Validation**: Secure payment verification

### Supported Payment Methods
- M-Pesa (Primary)
- Airtel Money
- Bank Transfers
- Cryptocurrency (Future)

## 🔐 Security Features

### User Security
- Phone number verification via OTP
- KYC document verification
- Session management and tracking
- Rate limiting on sensitive endpoints
- IP-based fraud detection

### Financial Security
- Transaction encryption
- Payment callback validation
- Withdrawal limits and verification
- Suspicious activity monitoring
- Double-entry bookkeeping

## 📊 Analytics & Monitoring

### Game Analytics
- Real-time player counts
- Betting volume tracking
- Win/loss ratios
- Popular multiplier targets
- Revenue analytics

### User Analytics
- Registration funnel tracking
- Player lifetime value
- Churn analysis
- Referral effectiveness

## 🚀 Deployment

### Docker Deployment
```bash
# Build and start services
docker-compose up --build

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

### Production Checklist
- [ ] Set `DEBUG=False`
- [ ] Configure secure database
- [ ] Set up Redis cluster
- [ ] Configure Nginx reverse proxy
- [ ] Set up SSL certificates
- [ ] Configure monitoring (Sentry)
- [ ] Set up backup strategy
- [ ] Configure CDN for static files

## 🧪 Testing

### Run Tests
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.games

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

### Test Categories
- Unit tests for models and utilities
- Integration tests for game logic
- API endpoint tests
- WebSocket connection tests
- Payment integration tests

## 📱 Mobile Considerations

### Responsive Design
- Mobile-first CSS framework
- Touch-optimized game controls
- Fast loading on slow connections
- Offline capability for basic features

### PWA Features
- Service worker for caching
- Push notifications
- Add to home screen
- Background sync

## 🔧 Configuration

### Game Settings
```python
# Game configuration in settings.py
AVIATOR_SETTINGS = {
    'GAME_DURATION': 30,  # seconds between rounds
    'BETTING_WINDOW': 10,  # seconds to place bets
    'MIN_BET': Decimal('10.00'),  # KES
    'MAX_BET': Decimal('100000.00'),  # KES
    'MIN_MULTIPLIER': Decimal('1.00'),
    'MAX_MULTIPLIER': Decimal('50.00'),
    'HOUSE_EDGE': Decimal('0.03'),  # 3%
}
```

### Redis Configuration
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('localhost', 6379)],
        },
    },
}
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Write comprehensive tests
- Update documentation
- Use meaningful commit messages
- Ensure backwards compatibility

## 📞 Support & Contact

- **Documentation**: [docs.betmoto.com](https://docs.betmoto.com)
- **Support Email**: support@betmoto.com
- **Developer Email**: dev@betmoto.com
- **Bug Reports**: [GitHub Issues](https://github.com/yourusername/betmoto/issues)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational purposes. Ensure compliance with local gambling laws and regulations before deployment. The developers are not responsible for any legal issues arising from the use of this software.

## 🔄 Version History

### v1.0.0 (Current)
- Initial release
- Basic aviator game functionality
- M-Pesa integration
- User authentication and wallet system
- Admin dashboard

### Upcoming Features
- [ ] Live dealer games
- [ ] Sports betting integration
- [ ] Mobile app development
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Cryptocurrency payments

---

**Happy Betting! 🎰**