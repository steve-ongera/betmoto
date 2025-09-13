
# Management command to start the system
# management/commands/start_aviator_system.py
from django.core.management.base import BaseCommand
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Start the Aviator game system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--auto-start',
            action='store_true',
            help='Auto-start the system on server startup'
        )
    
    def handle(self, *args, **options):
        from betting_app.views import game_engine
        
        try:
            if game_engine.running:
                self.stdout.write(
                    self.style.WARNING('Game engine is already running')
                )
                return
            
            success = game_engine.start()
            if success:
                self.stdout.write(
                    self.style.SUCCESS('Game engine started successfully')
                )
                logger.info('Game engine started via management command')
            else:
                self.stdout.write(
                    self.style.ERROR('Failed to start game engine')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error starting game engine: {str(e)}')
            )
            logger.error(f'Management command error: {str(e)}')
