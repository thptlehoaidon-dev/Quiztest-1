from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('add/', views.add_exam, name='add_exam'),
    path('take/<int:exam_id>/', views.take_exam, name='take_exam'),
    path('result/<int:exam_id>/<int:score>/<int:total>/', views.exam_result, name='exam_result'),
    path('delete/<int:exam_id>/', views.delete_exam, name='delete_exam'),
    path('import-json/', views.import_json, name='import_json'),
    path('ai-exam/', views.ai_exam, name='ai_exam'),
]
