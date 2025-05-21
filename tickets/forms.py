# tickets/forms.py
from django import forms
from .models import (
    Ticket, Agent, Comment, 
    TicketCategory, TicketStatus, TicketPriority
    # CustomFormField не импортируем сюда напрямую для генерации формы, 
    # так как форма будет строиться динамически в view на основе этих полей.
)

# ------------------- Форма для Шага 1: Выбор Категории Тикета -------------------
class SelectTicketCategoryForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=TicketCategory.objects.all().order_by('name'),
        label="Выберите категорию вашей проблемы",
        empty_label=None, # Пользователь должен выбрать категорию
        widget=forms.RadioSelect(attrs={'class': 'form-check-input-stacked'}), # RadioSelect для наглядности
        # Или можно использовать forms.Select(attrs={'class': 'form-select'})
        help_text="От выбора категории зависит, какие поля вам нужно будет заполнить далее."
    )

# ------------------- Форма для Шага 2: Создание Тикета (базовая часть) -------------------
# Эта форма будет содержать стандартные поля. Кастомные поля будут добавляться к ней
# динамически в представлении на основе выбранной категории.
class TicketCreateForm(forms.ModelForm):
    attachment_file = forms.FileField(
        label="Прикрепить файл (необязательно)",
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )

    class Meta:
        model = Ticket
        fields = [ # Поле 'category' убрано, так как категория уже выбрана на предыдущем шаге
            'reporter_name', 
            'reporter_email', 
            'reporter_phone', 
            'reporter_building',
            'reporter_room',
            'reporter_department',
            'title', 
            'description',
            # 'custom_form_data' будет заполняться в view из динамических полей
        ]
        labels = {
            'reporter_name': 'Ваше ФИО',
            'reporter_email': 'Ваш Email (для уведомлений)',
            'reporter_phone': 'Контактный телефон (необязательно)',
            'reporter_building': 'Корпус (необязательно)',
            'reporter_room': 'Комната/Кабинет (необязательно)',
            'reporter_department': 'Подразделение (необязательно)',
            'title': 'Тема проблемы (кратко)',
            'description': 'Подробное описание проблемы',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'reporter_building': forms.TextInput(attrs={'class': 'form-control'}),
            'reporter_room': forms.TextInput(attrs={'class': 'form-control'}),
            'reporter_department': forms.TextInput(attrs={'class': 'form-control'}),
            'reporter_phone': forms.TextInput(attrs={'class': 'form-control', 'type': 'tel'}),
        }

    def __init__(self, *args, **kwargs):
        # category_obj = kwargs.pop('category_obj', None) # Для получения объекта категории, если нужно
        # custom_fields_queryset = kwargs.pop('custom_fields', None) # Для получения кастомных полей

        super().__init__(*args, **kwargs)
        
        # Обязательные стандартные поля
        self.fields['reporter_name'].required = True
        self.fields['reporter_email'].required = True
        self.fields['title'].required = True
        self.fields['description'].required = True
        
        # Плейсхолдеры
        self.fields['reporter_name'].widget.attrs.update({'placeholder': 'Иванов Иван Иванович'})
        # ... (остальные плейсхолдеры, как были) ...
        self.fields['reporter_email'].widget.attrs.update({'placeholder': 'ivan.ivanov@example.com'})
        self.fields['reporter_phone'].widget.attrs.update({'placeholder': '+7 (XXX) XXX-XX-XX'})
        self.fields['reporter_building'].widget.attrs.update({'placeholder': 'Корпус А, Главный корпус, ...'})
        self.fields['reporter_room'].widget.attrs.update({'placeholder': '101, 3 этаж, опенспейс, ...'})
        self.fields['reporter_department'].widget.attrs.update({'placeholder': 'Отдел маркетинга, Бухгалтерия, ...'})
        self.fields['title'].widget.attrs.update({'placeholder': 'Не работает принтер / Ошибка в программе X'})
        self.fields['description'].widget.attrs.update({'placeholder': 'Опишите подробно, что произошло...'})

        # Применяем CSS классы
        for visible_field_name, field in self.fields.items(): # Используем .fields.items() для всех полей
            widget = field.widget
            if not isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.ClearableFileInput, forms.FileInput)):
                 widget.attrs['class'] = widget.attrs.get('class', '') + ' form-control' # Добавляем класс 'form-control'
                 widget.attrs['class'] = widget.attrs['class'].strip()
            elif isinstance(widget, (forms.ClearableFileInput, forms.FileInput)):
                 widget.attrs['class'] = widget.attrs.get('class', '') + ' form-control-file'
                 widget.attrs['class'] = widget.attrs['class'].strip()
        
        # Динамическое добавление кастомных полей будет происходить в view,
        # которое создаст экземпляр этой формы и модифицирует его self.fields


# ------------------- Формы для Агентов на странице деталей тикета -------------------

class AgentCommentForm(forms.ModelForm):
    # ... (код без изменений, как в предыдущих версиях) ...
    is_internal = forms.BooleanField(label="Внутренний комментарий (виден только агентам)", required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    attachment_file_comment = forms.FileField(label="Прикрепить файл к комментарию (необязательно)", required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'}))
    class Meta:
        model = Comment
        fields = ['body', 'is_internal', 'attachment_file_comment']
        widgets = {'body': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Введите текст вашего комментария...', 'class': 'form-control'}),}
        labels = {'body': 'Текст комментария',}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.fields['body'].required = True

class TicketUpdateStatusForm(forms.ModelForm):
    # ... (код без изменений) ...
    status = forms.ModelChoiceField(queryset=TicketStatus.objects.all().order_by('order', 'name'), label="Новый статус", widget=forms.Select(attrs={'class': 'form-select'}))
    class Meta: model = Ticket; fields = ['status']

class TicketUpdatePriorityForm(forms.ModelForm):
    # ... (код без изменений) ...
    priority = forms.ModelChoiceField(queryset=TicketPriority.objects.all().order_by('order', 'name'), label="Новый приоритет", widget=forms.Select(attrs={'class': 'form-select'}), required=False)
    class Meta: model = Ticket; fields = ['priority']

class TicketUpdateCategoryForm(forms.ModelForm):
    # ... (код без изменений) ...
    category = forms.ModelChoiceField(queryset=TicketCategory.objects.all().order_by('name'), label="Новая категория", widget=forms.Select(attrs={'class': 'form-select'}), required=False, empty_label="Без категории")
    class Meta: model = Ticket; fields = ['category']

class TicketReassignAgentForm(forms.ModelForm):
    # ... (код с динамическим queryset, как мы обсуждали) ...
    assignee = forms.ModelChoiceField(queryset=Agent.objects.none(), label="Новый исполнитель", required=True, widget=forms.Select(attrs={'class': 'form-select'}))
    class Meta: model = Ticket; fields = ['assignee']
    def __init__(self, *args, **kwargs):
        assignable_agents_queryset = kwargs.pop('assignable_agents', Agent.objects.none())
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = assignable_agents_queryset