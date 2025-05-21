# tickets/urls.py
from django.urls import path
from django.views.generic.base import RedirectView # Для редиректа
from . import views  # Импортируем наши представления из текущего приложения
from django.contrib.auth import views as auth_views # Встроенные представления Django для аутентификации

app_name = 'tickets' # Определяем пространство имен для URL-адресов этого приложения

urlpatterns = [
    # --- URL-адреса для обычных пользователей (клиентская часть) ---
    
    # Шаг 1: Выбор категории тикета
    path('create/select-category/', views.select_ticket_category_view, name='select_ticket_category'),
    
    # Шаг 2: Создание тикета для выбранной категории
    path('create/for-category/<int:category_id>/', views.create_ticket_view, name='create_ticket_for_category'),
    
    # URL /helpdesk/create/ теперь редиректит на выбор категории.
    # Если пользователь попытается зайти на старый URL, его перенаправит.
    path('create/', RedirectView.as_view(pattern_name='tickets:select_ticket_category', permanent=False), name='create_ticket_redirect'),

    # Проверка статуса тикета
    path('check_status/', views.check_ticket_status_view, name='check_ticket_status'),

    # --- URL-адреса для Агентов (сотрудники техподдержки) ---
    # Страница входа для агентов
    path('agent/login/', auth_views.LoginView.as_view(
        template_name='tickets/agent_login.html',
        redirect_authenticated_user=True
        ), name='agent_login'),
    
    # URL для выхода агента из системы
    path('agent/logout/', auth_views.LogoutView.as_view(
        next_page='tickets:agent_login'
        ), name='agent_logout'),
    
    # Главная панель управления агента (дашборд)
    path('agent/dashboard/', views.agent_dashboard_view, name='agent_dashboard'),
    path('agent/', views.agent_dashboard_view, name='agent_home'), # Альтернативный URL для дашборда

    # Списки тикетов для агента
    path('agent/tickets/', views.agent_ticket_list_view, name='agent_ticket_list'), 
    path('agent/tickets/my/', views.agent_my_tickets_view, name='agent_my_ticket_list'), 
    
    # Детальный просмотр и управление тикетом
    path('agent/ticket/<int:ticket_pk>/', views.agent_ticket_detail_view, name='agent_ticket_detail'),
]