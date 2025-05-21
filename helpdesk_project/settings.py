# helpdesk_project/settings.py

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/stable/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Сгенерируй свой собственный SECRET_KEY. Не используй этот в продакшене.
# Можно использовать `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`
SECRET_KEY = 'django-insecure-=y-4f(_(g(y8bgs4vwz8ocv4=l2w3b55wrvgmw%zaj!170no8@' # ЗАМЕНИ ЭТО В ПРОДАКШENE!

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True  # В режиме разработки True, в продакшене False

ALLOWED_HOSTS = [] # В продакшене здесь нужно указать домен(ы) твоего сайта


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Наши приложения
    'tickets.apps.TicketsConfig', # Убедись, что это правильное имя конфигурации из tickets/apps.py
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Для локализации может понадобиться LocaleMiddleware, если не все работает
    # 'django.middleware.locale.LocaleMiddleware',
]

ROOT_URLCONF = 'helpdesk_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # DIRS - это список директорий, где Django будет искать шаблоны ВНЕ приложений.
        # Если у тебя есть общая папка 'templates' на уровне проекта (C:\Projects\MyHelpdesk\templates),
        # она должна быть здесь.
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        
        # APP_DIRS = True говорит Django искать шаблоны в папке 'templates'
        # ВНУТРИ каждого приложения из INSTALLED_APPS.
        # Это то, что нам нужно для tickets/templates/
        'APP_DIRS': True, # КЛЮЧЕВОЙ МОМЕНТ! Должно быть True.
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'helpdesk_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'myhelpdesk_db',  # Имя твоей базы данных
        'USER': 'postgres',       # Пользователь PostgreSQL (обычно 'postgres')
        'PASSWORD': 'X9Ar3@v7DL',  # ЗАМЕНИ НА СВОЙ НАСТОЯЩИЙ ПАРОЛЬ для пользователя 'postgres'
        'HOST': 'localhost',      # Или '127.0.0.1'
        'PORT': '5432',           # Стандартный порт PostgreSQL
    }
}


# Password validation
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Наша кастомная модель пользователя (Агента)
AUTH_USER_MODEL = 'tickets.Agent'


# Internationalization
# https://docs.djangoproject.com/en/stable/topics/i18n/

LANGUAGE_CODE = 'ru-RU'

TIME_ZONE = 'Europe/Moscow' # ЗАМЕНИ НА СВОЙ ЧАСОВОЙ ПОЯС, если нужно

USE_I18N = True  # Интернационализация (переводы интерфейса)
USE_L10N = True  # Локализация форматов (даты, числа и т.д. согласно локали)
USE_TZ = True    # Поддержка часовых поясов


# Static files (CSS, JavaScript, Images for the app itself)
# https://docs.djangoproject.com/en/stable/howto/static-files/

STATIC_URL = 'static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles_collected') # Куда собираются статические файлы для продакшена командой collectstatic
# STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')] # Дополнительные папки со статикой (если нужны)


# Media files (User-uploaded files)
# https://docs.djangoproject.com/en/stable/topics/files/

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# URL-адреса для системы аутентификации агентов
LOGIN_URL = 'tickets:agent_login'  # Имя URL-шаблона для страницы входа агентов
LOGIN_REDIRECT_URL = 'tickets:agent_dashboard' # Имя URL-шаблона для перенаправления после входа агента
# LOGOUT_REDIRECT_URL можно не указывать здесь, если next_page задан в LogoutView


# Настройки для Email (пока можно не трогать, но понадобятся для уведомлений)
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.example.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your_email@example.com'
# EMAIL_HOST_PASSWORD = 'your_email_password'
# DEFAULT_FROM_EMAIL = 'helpdesk@example.com'