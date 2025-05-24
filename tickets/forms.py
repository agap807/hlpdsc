# tickets/forms.py
from django import forms
from .models import (
    Ticket, Agent, Comment, 
    TicketCategory, TicketStatus, TicketPriority, Project
)

# ------------------- Форма для Шага 1: Выбор Категории Тикета -------------------
class SelectTicketCategoryForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=TicketCategory.objects.filter(
            project__is_active=True, 
            is_active=True # Фильтруем по новому полю TicketCategory.is_active
        ).select_related('project').order_by('project__name', 'name'),
        label="Выберите категорию вашей проблемы",
        empty_label=None, 
        widget=forms.RadioSelect(attrs={'class': 'form-check-input-stacked'}),
        help_text="От выбора категории зависит, какие поля вам нужно будет заполнить далее."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем метку для каждого Radio-инпута более информативной
        self.fields['category'].label_from_instance = lambda obj: f"{obj.name} (Проект: {obj.project.name})"

# ------------------- Форма для Шага 2: Создание Тикета (базовая часть) -------------------
class TicketCreateForm(forms.ModelForm):
    reporter_name = forms.CharField(
        label='Ваше ФИО', 
        required=True, 
        widget=forms.TextInput(attrs={'placeholder': 'Иванов Иван Иванович', 'class': 'form-control'})
    )
    reporter_email = forms.EmailField(
        label='Ваш Email (для уведомлений)', 
        required=True, 
        widget=forms.EmailInput(attrs={'placeholder': 'ivan.ivanov@example.com', 'class': 'form-control'})
    )
    
    # Поле attachment_file теперь будет добавляться динамически, если для категории
    # настроен CustomFormField с типом 'file'.

    class Meta:
        model = Ticket
        fields = [
            'reporter_name', 
            'reporter_email',
            # Остальные поля модели ('title', 'description', etc.) будут добавлены динамически
            # из CustomFormField во views.py.
        ]
        labels = {} 
        widgets = {} 

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # __init__ остается пустым или с минимальной общей логикой, 
        # т.к. большинство полей добавляются и настраиваются во views.py

# ------------------- Формы для Агентов на странице деталей тикета -------------------

class AgentCommentForm(forms.ModelForm):
    is_internal = forms.BooleanField(
        label="Внутренний комментарий (виден только агентам)", 
        required=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    attachment_file_comment = forms.FileField(
        label="Прикрепить файл к комментарию (необязательно)", 
        required=False, 
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'}) # Можно просто 'form-control' для единообразия
    )
    class Meta:
        model = Comment
        fields = ['body', 'is_internal', 'attachment_file_comment']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Введите текст вашего комментария...', 'class': 'form-control'}),
        }
        labels = {
            'body': 'Текст комментария',
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['body'].required = True

class TicketUpdateStatusForm(forms.ModelForm):
    status = forms.ModelChoiceField(
        queryset=TicketStatus.objects.all().order_by('order', 'name'), 
        label="Новый статус", 
        widget=forms.Select(attrs={'class': 'form-select'}) # Bootstrap 5 класс для select
    )
    class Meta: 
        model = Ticket
        fields = ['status']

class TicketUpdatePriorityForm(forms.ModelForm):
    priority = forms.ModelChoiceField(
        queryset=TicketPriority.objects.all().order_by('order', 'name'), 
        label="Новый приоритет", 
        widget=forms.Select(attrs={'class': 'form-select'}), 
        required=False # Приоритет может быть не назначен
    )
    class Meta: 
        model = Ticket
        fields = ['priority']

# TicketUpdateCategoryForm была убрана из логики agent_ticket_detail_view,
# так как изменение категории тикета с кастомными полями - сложная операция.
# Если она нужна, ее нужно будет аккуратно реализовать.

class TicketReassignAgentForm(forms.ModelForm):
    assignee = forms.ModelChoiceField(
        queryset=Agent.objects.none(), # Queryset устанавливается во view
        label="Новый исполнитель", 
        required=True, # Обычно назначение требует выбора исполнителя
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta: 
        model = Ticket
        fields = ['assignee']
        
    def __init__(self, *args, **kwargs):
        assignable_agents_queryset = kwargs.pop('assignable_agents', Agent.objects.none())
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = assignable_agents_queryset
        if not assignable_agents_queryset.exists(): # Если нет доступных агентов для выбора
            self.fields['assignee'].empty_label = "Нет доступных исполнителей"
            self.fields['assignee'].widget.attrs['disabled'] = True


class TicketUpdateProjectForm(forms.ModelForm):
    project = forms.ModelChoiceField(
        queryset=Project.objects.filter(is_active=True).order_by('name'),
        label="Новый проект",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = Ticket
        fields = ['project']

# ------------------- Форма Фильтров для Списка Тикетов Агента -------------------
class TicketFilterForm(forms.Form):
    search_query = forms.CharField(
        label="Поиск",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'ID, тема, заявитель...', 'class': 'form-control form-control-sm'}) # form-control-sm для компактности
    )
    project = forms.ModelChoiceField(
        label="Проект",
        queryset=Project.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label="Все проекты", # Позволяет не выбирать проект
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}) # form-select-sm для компактности
    )
    category = forms.ModelChoiceField(
        label="Категория",
        queryset=TicketCategory.objects.all().order_by('project__name', 'name'),
        required=False,
        empty_label="Все категории",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    status = forms.ModelChoiceField(
        label="Статус",
        queryset=TicketStatus.objects.all().order_by('order', 'name'),
        required=False,
        empty_label="Все статусы",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    priority = forms.ModelChoiceField(
        label="Приоритет",
        queryset=TicketPriority.objects.all().order_by('order', 'name'),
        required=False,
        empty_label="Все приоритеты",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    assignee = forms.ModelChoiceField(
        label="Исполнитель",
        queryset=Agent.objects.filter(is_active=True).order_by('username'), # Начальный queryset, будет уточнен в __init__
        required=False,
        empty_label="Любой исполнитель", # Изменено для ясности
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    show_active = forms.BooleanField(
        label="Активные", # Метка будет в HTML
        required=False,
        initial=True, # По умолчанию показывать активные
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    show_completed = forms.BooleanField(
        label="Завершенные", # Метка будет в HTML
        required=False,
        initial=False, # По умолчанию не показывать завершенные
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)

        # Настройка querysets в зависимости от пользователя
        if user:
            if not (user.is_superuser or getattr(user, 'agent_role', None) == 'admin'): # Проверка на agent_role, если есть
                user_projects = user.projects.filter(is_active=True)
                self.fields['project'].queryset = user_projects
                
                if user_projects.exists():
                    self.fields['category'].queryset = TicketCategory.objects.filter(project__in=user_projects, is_active=True).select_related('project').order_by('project__name', 'name')
                    # Фильтруем исполнителей по доступным проектам пользователя
                    self.fields['assignee'].queryset = Agent.objects.filter(
                        is_active=True, 
                        projects__in=user_projects
                    ).distinct().order_by('username')
                else:
                    self.fields['category'].queryset = TicketCategory.objects.none()
                    self.fields['assignee'].queryset = Agent.objects.none()
            else: # Для суперадмина/админа показываем все активные категории и всех активных агентов
                 self.fields['category'].queryset = TicketCategory.objects.filter(project__is_active=True, is_active=True).select_related('project').order_by('project__name', 'name')
                 self.fields['assignee'].queryset = Agent.objects.filter(is_active=True).order_by('username')
        else: # Если пользователь не передан (маловероятно для этого контекста)
            self.fields['project'].queryset = Project.objects.none()
            self.fields['category'].queryset = TicketCategory.objects.none()
            self.fields['assignee'].queryset = Agent.objects.none()
            
        # Устанавливаем label_from_instance для лучшего отображения категорий в фильтре
        self.fields['category'].label_from_instance = lambda obj: f"{obj.name} ({obj.project.name})"
        self.fields['project'].label_from_instance = lambda obj: obj.name
        self.fields['assignee'].label_from_instance = lambda obj: obj.get_full_name() or obj.username