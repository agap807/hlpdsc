# C:\Projects\MyHelpdesk\tickets\templatetags\ticket_extras.py
from django import template
import os

register = template.Library() # Обязательно для регистрации фильтров/тегов

@register.filter(name='filename') # Регистрируем фильтр с именем 'filename'
def filename_filter(value):
    """
    Возвращает только имя файла из полного пути.
    Например, 'path/to/your/file.txt' -> 'file.txt'
    """
    if hasattr(value, 'name'): # Проверка, есть ли атрибут 'name' (как у FileField)
        return os.path.basename(value.name)
    # Если value - это просто строка, также пытаемся получить имя файла
    # Это может быть полезно, если путь к файлу хранится как строка
    elif isinstance(value, str):
        return os.path.basename(value)
    return str(value) # Возвращаем как есть, если не можем обработать