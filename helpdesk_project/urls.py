# helpdesk_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings  # Для доступа к settings.DEBUG
from django.conf.urls.static import static # Для обслуживания медиафайлов

urlpatterns = [
    # URL для админ-панели Django
    path('admin/', admin.site.urls),

    # Подключаем URL-маршруты нашего приложения 'tickets'
    # Все URL-адреса из tickets.urls будут доступны по префиксу /helpdesk/
    # Например, /helpdesk/create/, /helpdesk/check_status/
    path('helpdesk/', include('tickets.urls', namespace='tickets')),

    # Ты можешь добавить здесь другие URL-маршруты для других частей твоего проекта, если они появятся.
    # Например, если ты захочешь сделать главную страницу сайта не связанной с helpdesk:
    # from tickets import views as ticket_views # Пример
    # path('', ticket_views.some_landing_page_view, name='landing_page'),
]

# Это нужно ТОЛЬКО для режима разработки (DEBUG=True)
# чтобы Django Development Server мог отдавать загруженные пользователем медиафайлы.
# В продакшене медиафайлы должны раздаваться веб-сервером (Nginx, Apache и т.д.).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Также можно добавить раздачу статических файлов, если DEBUG=True и ты не используешь Whitenoise на ранних этапах
    # urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) # Но это если STATIC_ROOT определен