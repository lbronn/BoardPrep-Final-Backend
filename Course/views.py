# views.py
import os, environ
from django.db.models import Exists, OuterRef, F
from rest_framework import viewsets, status
from rest_framework.decorators import action, parser_classes
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from .models import Course, Lesson, Syllabus, Page, FileUpload, Exercise, ExerciseQuestions, ExerciseScores, CorrectExerciseQuestions
from Mocktest.models import MockTest
from User.models import Student
from Course.serializer import CourseListSerializer, CourseDetailSerializer, SyllabusSerializer, LessonSerializer, FileUploadSerializer, PageSerializer, ExerciseSerializer, ExerciseQuestionsSerializer, ExerciseScoresSerializer
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, models
from storages.backends.azure_storage import AzureStorage
from openai import OpenAI


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
    
class ExerciseViewSet(viewsets.ModelViewSet):
    queryset = Exercise.objects.all()
    serializer_class = ExerciseSerializer

    def generate_new_questions(self, lesson, exercise):
        env = environ.Env(
            DEBUG=(bool, False)
        )
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        environ.Env.read_env(os.path.join(BASE_DIR, '.env'))
        client = OpenAI(
            api_key=env('OPENAI_API_KEY'),
        )

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are Preppy, BoardPrep's Engineering Companion and an excellent and critical engineer, tasked with creating exercise questions based on the lesson provided. In creating the exercise questions, you don't mind the student's capability, whether he or she is a beginner or an expert, instead, you must focus on creating questions that will help the student understand the lesson better and in varying difficulties, easy, medium, or hard questions."},
                    {"role": "user", "content": f"This course is mainly about Integral Calculus. Based on this lesson: {lesson.lesson_title} - {lesson.description}\n\nPlease generate 12 questions of varying difficulty for this lesson that ensures the student can fully understand the lesson better."}
                ]
            )
            questions = response.choices[0].message.content.strip().split("\n\n")

            for question_data in questions:
                question_lines = question_data.split("\n")
                question_text = question_lines[0]
                choices = {line.split(". ")[0]: line.split(". ")[1] for line in question_lines[1:5]}
                correct_answer = question_lines[5].split(": ")[1]

                ExerciseQuestions.objects.create(
                    exercise=exercise,
                    question=question_text,
                    choiceA=choices['A'],
                    choiceB=choices['B'],
                    choiceC=choices['C'],
                    choiceD=choices['D'],
                    subject="Integral Calculus", 
                    correctAnswer=correct_answer
                )

        except Exception as e:
            return Response({"Error in generating questions": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=True, methods=['post'], url_path='generate_questions')
    def generate_questions(self, request, pk=None):
        lesson = get_object_or_404(Lesson, pk=pk)
        exercise = Exercise.objects.get_or_create(lesson=lesson, exerciseName=f"{lesson.lesson_title} Exercise")

        ExerciseQuestions.objects.filter(exercise=exercise).delete()
        try:
            self.generate_new_questions(lesson, exercise)
            return Response({"message": "Questions generated and saved successfully."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='submit_exercise')
    def submit_exercise(self, request, pk=None):
        exercise = get_object_or_404(Exercise, pk=pk)
        student = get_object_or_404(Student, user__username=request.data.get('username'))
        answers = request.data.get('answers', {})

        correct_answers = ExerciseQuestions.objects.filter(exercise=exercise).values_list('id', 'correctAnswer')
        correct_answers_dict = {str(question_id): correct for question_id, correct in correct_answers}

        score = sum(answer == correct_answers_dict.get(str(question_id)) for question_id, answer in answers.items())
        total_questions = len(correct_answers)
        passing_score = 10 

        if score >= passing_score:
            feedback = "Congratulations, you passed the exercise!"
            passed = True
        else:
            feedback = "You did not pass the exercise. Please try again."
            passed = False
            ExerciseQuestions.objects.filter(exercise=exercise).delete()
            self.generate_new_questions(exercise.lesson, exercise)

        with transaction.atomic():
            exercise_score, created = ExerciseScores.objects.update_or_create(
                exercise_id=exercise,
                student=student,
                defaults={
                    'score': score,
                    'totalQuestions': total_questions,
                    'feedback': feedback
                }
            )

            if not created:
                exercise_score.correct_questions.clear()

            for question_id in answers:
                if answers[question_id] == correct_answers_dict.get(str(question_id)):
                    correct_question = ExerciseQuestions.objects.get(id=question_id)
                    exercise_score.correct_questions.add(correct_question)

        if passed:
            next_lesson = Lesson.objects.filter(syllabus=exercise.lesson.syllabus, order=exercise.lesson.order + 1).first()
            if next_lesson:
                next_lesson.available = True
                next_lesson.save()

        return Response({"score": score, "total_questions": total_questions, "feedback": feedback, "passed": passed})

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

class FileUploadViewSet(viewsets.ModelViewSet):
    queryset = FileUpload.objects.all()
    serializer_class = FileUploadSerializer


