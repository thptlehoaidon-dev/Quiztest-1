import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from .models import Exam, Question, Choice
import google.generativeai as genai
import re

def dashboard(request):
    exams = Exam.objects.all().order_by('-created_at')
    return render(request, 'quiz/dashboard.html', {'exams': exams})

def add_exam(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        
        if not title:
            messages.error(request, 'Vui lòng nhập tên đề thi.')
            return redirect('quiz:add_exam')
            
        exam = Exam.objects.create(title=title, description=description)
        
        # Parse questions and choices
        question_count = int(request.POST.get('question_count', 0))
        for i in range(1, question_count + 1):
            q_text = request.POST.get(f'question_{i}_text')
            if q_text:
                question = Question.objects.create(exam=exam, text=q_text, order=i)
                
                # Choices for this question
                correct_choice = request.POST.get(f'question_{i}_correct') # e.g., '1', '2', '3', '4'
                
                for j in range(1, 5):
                    c_text = request.POST.get(f'question_{i}_choice_{j}')
                    if c_text:
                        is_correct = (str(j) == str(correct_choice))
                        Choice.objects.create(question=question, text=c_text, is_correct=is_correct)

        messages.success(request, 'Thêm đề bài thành công!')
        return redirect('quiz:dashboard')

    return render(request, 'quiz/add_exam.html')

def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    questions = exam.questions.all()
    
    if request.method == 'POST':
        score = 0
        total = questions.count()
        
        for question in questions:
            selected_choice_id = request.POST.get(f'question_{question.id}')
            if selected_choice_id:
                try:
                    choice = Choice.objects.get(id=selected_choice_id, question=question)
                    if choice.is_correct:
                        score += 1
                except Choice.DoesNotExist:
                    pass
                    
        return redirect('quiz:exam_result', exam_id=exam.id, score=score, total=total)
        
    return render(request, 'quiz/take_exam.html', {'exam': exam, 'questions': questions})

def exam_result(request, exam_id, score, total):
    exam = get_object_or_404(Exam, id=exam_id)
    return render(request, 'quiz/result.html', {'exam': exam, 'score': score, 'total': total})

def delete_exam(request, exam_id):
    if request.method == 'POST':
        exam = get_object_or_404(Exam, id=exam_id)
        exam.delete()
        messages.success(request, 'Xoá đề bài thành công.')
    return redirect('quiz:dashboard')

def import_json(request):
    if request.method == 'POST':
        json_file = request.FILES.get('json_file')

        # --- Kiểm tra file được chọn ---
        if not json_file:
            messages.error(request, 'Vui lòng chọn file JSON.')
            return redirect('quiz:import_json')

        if not json_file.name.lower().endswith('.json'):
            messages.error(request, 'File không hợp lệ. Vui lòng chọn file có đuôi .json')
            return redirect('quiz:import_json')

        # --- Đọc & parse JSON ---
        try:
            raw = json_file.read().decode('utf-8')
            data = json.loads(raw)
        except UnicodeDecodeError:
            messages.error(request, 'Không thể đọc file. Hãy đảm bảo file được lưu với encoding UTF-8.')
            return redirect('quiz:import_json')
        except json.JSONDecodeError as e:
            messages.error(request, f'File JSON không đúng định dạng: {e}')
            return redirect('quiz:import_json')

        # --- Kiểm tra cấu trúc ---
        title = data.get('title', '').strip() if isinstance(data, dict) else ''
        if not title:
            messages.error(request, 'File JSON thiếu trường "title" (tên đề thi).')
            return redirect('quiz:import_json')

        questions_data = data.get('questions', [])
        if not questions_data or not isinstance(questions_data, list):
            messages.error(request, 'File JSON thiếu hoặc có trường "questions" rỗng.')
            return redirect('quiz:import_json')

        # --- Lưu vào database (atomic transaction) ---
        try:
            with transaction.atomic():
                exam = Exam.objects.create(
                    title=title,
                    description=data.get('description', '').strip(),
                )

                question_count = 0
                for order, q_data in enumerate(questions_data, start=1):
                    if not isinstance(q_data, dict):
                        continue
                    q_text = q_data.get('text', '').strip()
                    if not q_text:
                        continue

                    question = Question.objects.create(
                        exam=exam,
                        text=q_text,
                        order=order,
                    )

                    for c_data in q_data.get('choices', []):
                        if not isinstance(c_data, dict):
                            continue
                        c_text = c_data.get('text', '').strip()
                        if not c_text:
                            continue
                        Choice.objects.create(
                            question=question,
                            text=c_text,
                            is_correct=bool(c_data.get('is_correct', False)),
                        )

                    question_count += 1

        except Exception as e:
            messages.error(request, f'Đã xảy ra lỗi khi lưu đề thi: {e}')
            return redirect('quiz:import_json')

        messages.success(
            request,
            f'Import thành công đề {exam.title} với {question_count} câu hỏi!'
        )
        return redirect('quiz:dashboard')

    return render(request, 'quiz/import_json.html')

def ai_exam(request):
    genai.configure(api_key="AIzaSyCrQoFRNRAF1GUOgkEEqPpGqCHVAwDe5t0")
    model = genai.GenerativeModel("gemini-2.5-flash")

    if request.method == 'POST':
        prompt = request.POST.get('prompt')
        num_questions = request.POST.get('num_questions',4)
        title = request.POST.get('title')

        prompt_AI = f"""
        Bạn là một giáo viên giỏi, có khả năng tạo ra các câu hỏi trắc nghiệm chất lượng cao.
        Hãy tạo cho tôi {num_questions} câu hỏi trắc nghiệm dựa trên chủ đề sau:
        {prompt}
        
        Yêu cầu:
        - Mỗi câu hỏi có 4 đáp án.
        - Chỉ có 1 đáp án đúng.
        - Viết các công thức không dùng LaTex
        - Đáp án đúng được đánh dấu là "is_correct": true.
        - Các đáp án sai được đánh dấu là "is_correct": false.
        - Trả về kết quả dưới dạng JSON hợp lệ với cấu trúc sau:
        {{
            "description": "Mô tả đề thi",
            "questions": [
                {{
                    "text": "Nội dung câu hỏi",
                    "choices": [
                        {{"text": "Đáp án 1", "is_correct": false}},
                        {{"text": "Đáp án 2", "is_correct": true}},
                        {{"text": "Đáp án 3", "is_correct": false}},
                        {{"text": "Đáp án 4", "is_correct": false}}
                    ]
                }}
            ]
        }}
        """

        response = model.generate_content(prompt_AI)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            messages.error(request, f'AI trả về sai định dạng JSON: {e}')

            print(raw);
            print(data.text);

            return redirect('quiz:ai_exam')

        try:
            with transaction.atomic():
                exam = Exam.objects.create(
                    title=title,
                    description=data.get('description', '').strip(),
                )

                question_count = 0
                for order, q_data in enumerate(data.get('questions', []), start=1):
                    if not isinstance(q_data, dict):
                        continue
                    q_text = q_data.get('text', '').strip()
                    if not q_text:
                        continue

                    question = Question.objects.create(
                        exam=exam,
                        text=q_text,
                        order=order,
                    )

                    for c_data in q_data.get('choices', []):
                        if not isinstance(c_data, dict):
                            continue
                        c_text = c_data.get('text', '').strip()
                        if not c_text:
                            continue
                        Choice.objects.create(
                            question=question,
                            text=c_text,
                            is_correct=bool(c_data.get('is_correct', False)),
                        )

                    question_count += 1

        except Exception as e:
            messages.error(request, f'Đã xảy ra lỗi khi lưu đề thi: {e}')
            return redirect('quiz:ai_exam')

        messages.success(
            request,
            f'Import thành công đề {exam.title} với {question_count} câu hỏi!'
        )
        
        return redirect('quiz:dashboard')

    return render(request, 'quiz/ai_exam.html')
