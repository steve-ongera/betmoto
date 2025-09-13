
# startup.py - System startup script
import os
import sys
import django
import logging
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yourproject.settings')
django.setup()

from betting_app.views import game_engine
from betting_app.models import SystemConfiguration, GameSettings
from django.contrib.auth.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_system():
    """Initialize the Aviator system on startup"""
    logger.info("Initializing Aviator system...")
    
    try:
        # Create default game settings if they don't exist
        game_settings, created = GameSettings.objects.get_or_create(
            defaults={
                'house_edge': 3.0,
                'betting_phase_duration': 10,
                'game_interval': 5,
                'min_bet_amount': 1.00,
                'max_bet_amount': 10000.00,
                'is_maintenance_mode': False
            }
        )
        
        if created:
            logger.info("Created default game settings")
        
        # Create system configurations
        default_configs = [
            {'key': 'system_status', 'value': 'running', 'description': 'System operational status'},
            {'key': 'auto_start_games', 'value': 'true', 'description': 'Auto start games on system startup'},
            {'key': 'max_concurrent_players', 'value': '1000', 'description': 'Maximum concurrent players'},
            {'key': 'enable_chat', 'value': 'true', 'description': 'Enable in-game chat'},
            {'key': 'maintenance_message', 'value': 'System under maintenance', 'description': 'Message shown during maintenance'},
        ]
        
        for config in default_configs:
            SystemConfiguration.objects.get_or_create(
                key=config['key'],
                defaults={
                    'value': config['value'],
                    'description': config['description']
                }
            )
        
        logger.info("System configurations initialized")
        
        # Check if auto-start is enabled
        auto_start_config = SystemConfiguration.objects.filter(
            key='auto_start_games'
        ).first()
        
        if auto_start_config and auto_start_config.value.lower() == 'true':
            logger.info("Auto-start enabled, starting game engine...")
            success = game_engine.start()
            if success:
                logger.info("Game engine started successfully")
            else:
                logger.error("Failed to start game engine")
        else:
            logger.info("Auto-start disabled, system ready for manual start")
        
        logger.info("Aviator system initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"System initialization failed: {str(e)}")
        return False

def create_admin_user():
    """Create default admin user if none exists"""
    try:
        if not User.objects.filter(is_superuser=True).exists():
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@aviator.com',
                password='admin123',  # Change this in production
                phone_number='+254700000000'
            )
            logger.info(f"Created admin user: {admin_user.username}")
            return True
        else:
            logger.info("Admin user already exists")
            return True
    except Exception as e:
        logger.error(f"Failed to create admin user: {str(e)}")
        return False

def health_check():
    """Perform system health check"""
    logger.info("Performing system health check...")
    
    checks = {
        'database': False,
        'game_engine': False,
        'admin_user': False
    }
    
    try:
        # Database check
        User.objects.count()
        checks['database'] = True
        logger.info("✓ Database connection OK")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {str(e)}")
    
    try:
        # Game engine check
        checks['game_engine'] = game_engine is not None
        logger.info("✓ Game engine initialized")
    except Exception as e:
        logger.error(f"✗ Game engine initialization failed: {str(e)}")
    
    try:
        # Admin user check
        checks['admin_user'] = User.objects.filter(is_superuser=True).exists()
        logger.info("✓ Admin user exists")
    except Exception as e:
        logger.error(f"✗ Admin user check failed: {str(e)}")
    
    all_checks_passed = all(checks.values())
    if all_checks_passed:
        logger.info("✓ All health checks passed")
    else:
        logger.warning(f"✗ Some health checks failed: {checks}")
    
    return all_checks_passed

if __name__ == '__main__':
    print("Starting Aviator System...")
    
    # Perform health check
    if not health_check():
        print("Health check failed, attempting to fix...")
        
        # Try to create admin user
        create_admin_user()
    
    # Initialize system
    success = initialize_system()
    
    if success:
        print("Aviator system started successfully!")
        print("Access admin dashboard at: http://localhost:8000/admin/dashboard/")
        print("Default admin credentials: admin/admin123")
        
        # Keep the script running
        try:
            import time
            while True:
                time.sleep(60)  # Check every minute
                if not game_engine.running:
                    # Try to restart if it stopped unexpectedly
                    auto_restart = SystemConfiguration.objects.filter(
                        key='auto_restart'
                    ).first()
                    
                    if auto_restart and auto_restart.value.lower() == 'true':
                        logger.info("Game engine stopped unexpectedly, attempting restart...")
                        game_engine.start()
        except KeyboardInterrupt:
            print("\nShutting down system...")
            game_engine.stop()
            print("System shutdown complete")
    else:
        print("Failed to start Aviator system")
        sys.exit(1)
