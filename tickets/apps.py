# tickets/apps.py

from django.apps import AppConfig

class TicketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tickets'
    # verbose_name = "Управление заявками" # Раскомментируй, если хочешь другое имя в админ-панели Django
    
    # Если бы мы использовали сигналы, их можно было бы импортировать здесь в методе ready:
    # def ready(self):
    #     import tickets.signals # Пример