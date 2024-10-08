import os
import environ
from django.db.models import Exists, OuterRef, F
from rest_framework import viewsets, status, parsers
from rest_framework.decorators import action, api_view, permission_classes, parser_classes
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from .models import Course, Lesson, Syllabus, Page, FileUpload, Exercise, ExerciseQuestions, ExerciseScores, CorrectExerciseQuestions
from Mocktest.models import MockTest
from User.models import Student, User
from Course.serializer import CourseListSerializer, CourseDetailSerializer, SyllabusSerializer, LessonSerializer, FileUploadSerializer, PageSerializer, ExerciseSerializer, ExerciseQuestionsSerializer, ExerciseScoresSerializer
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from storages.backends.azure_storage import AzureStorage
from openai import OpenAI
from bs4 import BeautifulSoup


@api_view(['POST'])
@csrf_exempt
def upload_image(request):
    if request.method == 'POST' and request.FILES['upload']:
        upload = request.FILES['upload']
        azure_storage = AzureStorage()
        filename = azure_storage.save(upload.name, upload)
        uploaded_file_url = azure_storage.url(filename)
        return JsonResponse({'url': uploaded_file_url})
    return JsonResponse({'error': 'Failed to upload file'}, status=400)

class CourseListViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseListSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.annotate(hasMocktest=Exists(MockTest.objects.filter(course=OuterRef('pk'))))
        return queryset

    @action(detail=False, methods=['get'], url_path='check_id/(?P<course_id>[^/.]+)')
    def check_course_id(self, request, course_id=None):
        """
        Check if a course with the given ID exists.
        """
        course_exists = Course.objects.filter(course_id=course_id).exists()
        return Response({'exists': course_exists})

    @action(detail=True, methods=['put'])
    def publish(self, request, pk=None):
        course = self.get_object()
        course.is_published = True
        course.save()
        return Response({'status': 'course published'}, status=status.HTTP_200_OK)

class CourseDetailViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseDetailSerializer

class SyllabusViewSet(viewsets.ModelViewSet):
    queryset = Syllabus.objects.all()
    serializer_class = SyllabusSerializer
    @action(detail=False, methods=['get'], url_path='(?P<course_id>[^/.]+)')
    def by_course(self, request, course_id=None):
        queryset = self.get_queryset().filter(course=course_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.all().prefetch_related('pages')
    serializer_class = LessonSerializer

    @action(detail=True, methods=['get'], url_path='pages')
    def get_lesson_pages(self, request, pk=None):
        lesson = self.get_object()  # This should fetch the lesson based on the provided lesson_id
        pages = Page.objects.filter(lesson=lesson)
        serializer = PageSerializer(pages, many=True)
        return Response(serializer.data)

    def by_syllabus(self, request, syllabus_id=None):
        queryset = self.get_queryset().filter(syllabus=syllabus_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['put'], url_path='update_lesson')
    def update_lesson(self, request, pk):
        try:
            lesson = get_object_or_404(Lesson, pk=pk)
            new_order = int(request.data.get('order', lesson.order))
            new_title = request.data.get('lesson_title', lesson.lesson_title)

            with transaction.atomic():
                # Update the order of lessons
                if new_order != lesson.order:
                    if new_order < lesson.order:
                        Lesson.objects.filter(
                            syllabus=lesson.syllabus,
                            order__lt=lesson.order,
                            order__gte=new_order
                        ).update(order=F('order') + 1)
                    else:
                        Lesson.objects.filter(
                            syllabus=lesson.syllabus,
                            order__gt=lesson.order,
                            order__lte=new_order
                        ).update(order=F('order') - 1)

                # Update the lesson's order and title
                lesson.order = new_order
                lesson.lesson_title = new_title
                lesson.save()

            return Response({'status': 'lesson updated'}, status=status.HTTP_200_OK)

        except (ValueError, TypeError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'], url_path='exercises')
    def get_exercises(self, request, pk=None):
        lesson = get_object_or_404(Lesson, pk=pk)
        exercises = Exercise.objects.filter(lesson=lesson)
        serializer = ExerciseSerializer(exercises, many=True)
        return Response(serializer.data)
    
class PageViewSet(viewsets.ModelViewSet):
    queryset = Page.objects.all()
    serializer_class = PageSerializer
    lookup_field = 'page_number'  # Specify the lookup field

    @action(detail=False, methods=['get', 'post', 'put'], url_path='(?P<lesson_id>[^/.]+)')
    def by_lesson(self, request, lesson_id=None):
        if request.method == 'GET':
            # Handle GET requests
            pages = self.queryset.filter(lesson_id=lesson_id)
            serializer = self.get_serializer(pages, many=True)
            return Response(serializer.data)
        elif request.method == 'POST':
            # Handle POST requests
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        elif request.method == 'PUT':
            # Handle PUT requests
            # You need to extract 'page_number' from the request data or URL, for example:
            page_number = request.data.get('page_number')  # Adjust this based on your data structure
            # Then, you can update the specific page
            page = Page.objects.filter(lesson_id=lesson_id, page_number=page_number).first()
            if page:
                serializer = self.get_serializer(page, data=request.data)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)


    @action(detail=False, methods=['get', 'put', 'delete'],
            url_path='(?P<lesson_id>[^/.]+)/(?P<page_number>[^/.]+)')
    def by_lesson_and_page(self, request, lesson_id=None, page_number=None):
        if request.method == 'GET':
            # Handle GET requests
            page = get_object_or_404(self.queryset, lesson_id=lesson_id, page_number=page_number)
            serializer = self.serializer_class(page)
            return Response(serializer.data)
        elif request.method == 'PUT':
            # Handle PUT requests
            page = get_object_or_404(self.queryset, lesson_id=lesson_id, page_number=page_number)
            serializer = self.serializer_class(page, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        elif request.method == 'DELETE':
            # Handle DELETE requests
            page = get_object_or_404(self.queryset, lesson_id=lesson_id, page_number=page_number)
            page.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({"detail": "Invalid request method."}, status=status.HTTP_400_BAD_REQUEST)
    
class ExerciseViewSet(viewsets.ModelViewSet):
    queryset = Exercise.objects.all()
    serializer_class = ExerciseSerializer

    @action(detail=True, methods=['post'], url_path='generate_questions')
    def generate_questions(self, request, pk=None):
        page_id = request.data.get('page_id')
        lesson_id = request.data.get('lesson_id')
        course_id = request.data.get('course_id')
        student_id = request.data.get('student_id')
        print(page_id, lesson_id, course_id, student_id)
        if not page_id or not lesson_id or not student_id:
            return Response({"error": "Page ID, Lesson ID, and Student ID are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            page = Page.objects.get(id=page_id)
            course = Course.objects.get(course_id=course_id)
            student = get_object_or_404(Student, user_name=student_id)
        except Page.DoesNotExist:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)

        course_title = course.course_title
        print(course_title)
        content = page.content
        content_title, content_content = self.extract_title_and_content(content)
        print(content_content)
        if not content_title or not content_content:
            return Response({"error": "Invalid content format"}, status=status.HTTP_400_BAD_REQUEST)
        if not course_title:
            return Response({"error": "Course title not found"}, status=status.HTTP_404_NOT_FOUND)

        existing_exercise = Exercise.objects.filter(lesson_id=lesson_id, student_id=student_id).first()
        if existing_exercise:
            return Response({'status': 'existing exercise', 'exercise_id': existing_exercise.exerciseID}, status=status.HTTP_200_OK)

        exercise = Exercise.objects.create(lesson_id=lesson_id, student_id=student_id, exerciseName=content_title)

        env = environ.Env(DEBUG=(bool, False))
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        environ.Env.read_env(os.path.join(BASE_DIR, '.env'))
        client = OpenAI(api_key=env('OPENAI_API_KEY'))

        #try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are Preppy, BoardPrep's Engineering Companion and an excellent and critical engineer, tasked with creating exercise questions based on the lesson provided. In creating the exercise questions, you don't mind the student's capability, whether he or she is a beginner or an expert, instead, you must focus on creating questions that will help the student understand the lesson better and in varying difficulties."
                },
                {
                    "role": "user", 
                    "content": f"This course is about {course_title}\n\n. Based on this lesson: {content_content}\n\nGenerate 15 questions of varying difficulty to ensure the student can fully understand the lesson better. Each question must be labeled as question. Each question must have 4 choices labeled as choiceA, choiceB, choiceC, and choiceD, with indicators placed before each choice as follows: A., B., C., and D., and indicate the correct choice with 'Correct Answer: ' followed by the correct choice text only (e.g., 'Correct Answer: correct choice'). Ensure the question ends with a question mark, and each choice ends with a period. Generate each question, choice, and correct choice in separate lines, and ensure none are left blank. Do not number the questions or indicate their difficulty."
                }
            ]
        )
        questions_text = response.choices[0].message.content.strip()
        print('1' + questions_text)
        if('*' in questions_text):
            questions_text = questions_text.replace('*', '')
        if('.' in questions_text):
            questions_text = questions_text.replace('.', '')
        if('\( ' in questions_text):    
            questions_text = questions_text.replace('\( ', '')
        if('\)' in questions_text):
            questions_text = questions_text.replace(' \)', '')
        print('shi:' +  questions_text)
        questions = self.process_openai_response(questions_text)
        for question_data in questions:
            ExerciseQuestions.objects.create(
                exercise=exercise,
                question=question_data['question'],
                choiceA=question_data['choiceA'],
                choiceB=question_data['choiceB'],
                choiceC=question_data['choiceC'],
                choiceD=question_data['choiceD'],
                correctAnswer=question_data['correctAnswer'],
                student=student,
            )

        return Response({'status': 'questions generated', 'exercise_id': exercise.exerciseID}, status=status.HTTP_201_CREATED)
        #except Exception as e:
        return Response({"Error in generating questions": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def extract_title_and_content(html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        title = soup.title.string if soup.title else 'No title'
        content = soup.get_text()
        return title, content
    
    @staticmethod
    def process_openai_response(response_text):
        questions = response_text.split('\n\n')
        processed_questions = []

        for question in questions:
            if question:
                lines = question.split('\n')
                question_text = ""
                choices = {}
                correct_answer = ""

                for line in lines:
                    if ('?' in line or line.endswith(':')) or (line.startswith('Question:') or line.startswith('question:')):
                        if line.startswith('Question:') or line.startswith('question:'):
                            question_text = line[len('Question:'):].strip()
                            print('typashi:' + question_text)
                        elif '?' in line:
                            question_text = line
                    elif 'Correct Answer:' not in line:
                        if line.startswith('A'):
                            choices['A'] = line[1:].strip() 
                        if line.startswith('B'):
                            choices['B'] = line[1:].strip()
                        if line.startswith('C'):
                            choices['C'] = line[1:].strip()
                        if line.startswith('D'):
                            choices['D'] = line[1:].strip()
                        if line.startswith('choiceA:'):
                            choices['A'] = line[len('choiceA:'):].strip()
                        if line.startswith('choiceB:'):
                            choices['B'] = line[len('choiceB:'):].strip()
                        if line.startswith('choiceC:'):
                            choices['C'] = line[len('choiceC:'):].strip()
                        if line.startswith('choiceD:'):
                            choices['D'] = line[len('choiceD:'):].strip()
                        if line.startswith('ChoiceA:'):
                            choices['A'] = line[len('ChoiceA:'):].strip()
                        if line.startswith('ChoiceB:'):
                            choices['B'] = line[len('ChoiceB:'):].strip()
                        if line.startswith('ChoiceC:'):
                            choices['C'] = line[len('ChoiceC:'):].strip() 
                        if line.startswith('ChoiceD:'):
                            choices['D'] = line[len('ChoiceD:'):].strip()
                        if line.startswith('**ChoiceA:**'):
                            choices['A'] = line[len('**ChoiceA:**'):].strip()
                        if line.startswith('**ChoiceB:**'):
                            choices['B'] = line[len('**ChoiceB:**'):].strip()
                        if line.startswith('**ChoiceC:**'):
                            choices['C'] = line[len('**ChoiceC:**'):].strip()
                        if line.startswith('**ChoiceD:**'):
                            choices['D'] = line[len('**ChoiceD:**'):].strip()
                    elif 'Correct Answer:' in line:
                        if line.startswith('Correct Answer:'):
                            print('line:' + line)
                            correct_answer = line.split(': ')[1].strip()
                            if correct_answer.startswith('A '):
                                correct_answer = correct_answer[2:]
                            if correct_answer.startswith('B '):
                                correct_answer = correct_answer[2:]
                            if correct_answer.startswith('C '):
                                correct_answer = correct_answer[2:]
                            if correct_answer.startswith('D '):
                                correct_answer = correct_answer[2:]
                            print('correct:' + correct_answer)
                        
                processed_questions.append({
                    'question': question_text,
                    'choiceA': choices.get('A', ''),
                    'choiceB': choices.get('B', ''),
                    'choiceC': choices.get('C', ''),
                    'choiceD': choices.get('D', ''),
                    'correctAnswer': correct_answer
                })

        return processed_questions

    @action(detail=False, methods=['get', 'delete'], url_path='(?P<lesson_id>[^/.]+)')
    def by_lesson(self, request, lesson_id=None):
        student_id = request.query_params.get('student_id')
        print(student_id)
        if not student_id:
            return Response({"error": "(1) Student ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset().filter(lesson_id=lesson_id, student_id=student_id)
        if request.method == 'DELETE':
            queryset.delete()
            return Response({"message": "Exercise deleted successfully for student and lesson."}, status=status.HTTP_204_NO_CONTENT)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class ExerciseQuestionsViewSet(viewsets.ModelViewSet):
    queryset = ExerciseQuestions.objects.all()
    serializer_class = ExerciseQuestionsSerializer
    
    @action(detail=False, methods=['get', 'delete'], url_path='(?P<exercise_id>[^/.]+)')
    def by_exercise(self, request, exercise_id=None):
        student_id = request.query_params.get('student_id')
        print(student_id)
        if not student_id:
            return Response({"error": "(2) Student ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset().filter(exercise_id=exercise_id, student_id=student_id)
        if request.method == 'DELETE':
            queryset.delete()
            return Response({"message": "Exercise questions deleted successfully for student and exercise."}, status=status.HTTP_204_NO_CONTENT)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class ExerciseScoresViewSet(viewsets.ModelViewSet):
    queryset = ExerciseScores.objects.all()
    serializer_class = ExerciseScoresSerializer

    @action(detail=False, methods=['get', 'post'], url_path='(?P<exercise_id>[^/.]+)')
    def by_student_exercise(self, request, exercise_id=None):
        page = request.query_params.get('page_id')
        lesson = request.query_params.get('lesson_id')
        print(page, lesson)

        if request.method == 'POST':
            user_name = request.data.get('student_id')
            if not user_name:
                return Response({'error': 'User name not provided.'}, status=400)
            student = get_object_or_404(User, user_name=user_name)
        else:
            student = request.user

        exercise = get_object_or_404(Exercise, exerciseID=exercise_id)
        print(student, exercise_id)

        if request.method == 'POST':
            score = request.data.get('score', 0)
            total_questions = request.data.get('totalQuestions', 0)
            passing_score = 0.8 * total_questions 

            has_finished = float(score) >= passing_score
            existing_score = ExerciseScores.objects.filter(student=student, exercise_id=exercise).first()
            if existing_score:
                existing_score.score = score
                existing_score.hasFinished = has_finished
                existing_score.save()
            else:
                request.data['student'] = student.user_name
                request.data['exercise'] = exercise.exerciseID
                request.data['hasFinished'] = has_finished
                serializer = self.get_serializer(data=request.data)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(student=student, exercise_id=exercise)
        serializer = self.get_serializer(queryset, many=True)
        if request.method == 'DELETE':
            queryset.delete()
            return Response({"message": "Exercise scores deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        
        return Response(serializer.data)

class CorrectExerciseQuestionsViewSet(viewsets.ModelViewSet):
    queryset = CorrectExerciseQuestions.objects.all()
    serializer_class = ExerciseQuestionsSerializer

    @action(detail=False, methods=['get'], url_path='(?P<exercise_id>[^/.]+)/(?P<student_id>[^/.]+)')
    def by_student_exercise(self, request, exercise_id=None, student_id=None):
        queryset = self.get_queryset().filter(exercise=exercise_id, student=student_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class FileUploadViewSet(viewsets.ModelViewSet):
    queryset = FileUpload.objects.all()
    serializer_class = FileUploadSerializer
    parser_classes = [parsers.FormParser, parsers.MultiPartParser]

    @action(detail=False, methods=['post'], url_path='upload')
    @csrf_exempt
    def upload_file(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        azure_storage = AzureStorage()
        filename = azure_storage.save(file.name, file)
        file_url = azure_storage.url(filename)

        file_instance = FileUpload(file=file_url, filename=filename)
        file_instance.save()

        return Response({'url': file_url}, status=status.HTTP_201_CREATED)