from django.db import models
from django_ckeditor_5.fields import CKEditor5Field

class Course(models.Model):
    course_id = models.CharField(max_length=10, primary_key=True)
    course_title = models.CharField(max_length=200)
    short_description = models.CharField(max_length=500)
    long_description = models.TextField()
    image = models.ImageField(upload_to='images/', default='default.png')
    is_published = models.BooleanField(default=False)  # New field

    def __str__(self):
        return self.course_title

    def has_mock_test(self):
        return self.mocktest_set.exists()

class Syllabus(models.Model):
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='syllabus')
    syllabus_id = models.CharField(max_length=10, primary_key=True)

    def __str__(self):
        return f"Syllabus for {self.course.course_title}"

class Lesson(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name='lessons')
    lesson_id = models.CharField(max_length=10, primary_key=True)
    lesson_title = models.CharField(max_length=200)
    order = models.IntegerField(help_text="Order of the lesson in the syllabus")

    def __str__(self):
        return f"{self.lesson_title} - {self.syllabus.course.course_title}"

class Page(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name='pages_by_syllabus')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='pages')
    page_number = models.IntegerField(help_text="Page number within the lesson")
    content = CKEditor5Field('Content', config_name='extends')

    class Meta:
        ordering = ['page_number']
        unique_together = ('lesson', 'page_number')

    def __str__(self):
        return f"Page {self.page_number} - {self.lesson.lesson_title}"

class FileUpload(models.Model):
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Exercise(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, blank=True, null=True)
    exerciseID = models.BigAutoField(primary_key=True)
    exerciseName = models.CharField(max_length=200)
    
    def __str__(self):
        return self.exerciseName
    
class ExerciseQuestions(models.Model):
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name='exercisequestions')
    question = models.TextField(max_length=512)
    choiceA = models.CharField(max_length=255, verbose_name="A")
    choiceB = models.CharField(max_length=255, verbose_name="B")
    choiceC = models.CharField(max_length=255, verbose_name="C")
    choiceD = models.CharField(max_length=255, verbose_name="D")
    subject = models.CharField(max_length=255)
    correctAnswer = models.CharField(max_length=255, verbose_name="Correct Answer")
    
    def __str__(self):
        return f"{self.question} - {self.subject}"
    
class ExerciseScores(models.Model):
    exerciseScoreID = models.BigAutoField(primary_key=True)
    exercise_id = models.ForeignKey('Exercise', on_delete=models.CASCADE, related_name='exercise_scores')
    student = models.ForeignKey('User.Student', on_delete=models.CASCADE, related_name='studentexercise_scores')
    score = models.FloatField(null=False)
    feedback = models.TextField(null=False)
    exerciseDateTaken = models.DateField(auto_now_add=True)
    totalQuestions = models.IntegerField(default=0)
    correct_questions = models.ManyToManyField(
        'ExerciseQuestions',
        through='CorrectExerciseQuestions',
        related_name='correct_in_exercises'
    )
    
    class Meta:
        unique_together = ['exercise_id', 'student']
    
    def __str__(self):
        return f"{self.student} - {self.exercise_id}"
    
class CorrectExerciseQuestions(models.Model):
    exercise_score = models.ForeignKey(ExerciseScores, on_delete=models.CASCADE)
    exercisequestion = models.ForeignKey(ExerciseQuestions, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('exercise_score', 'exercisequestion')
    
    def __str__(self):
        return f"{self.exercise_score} - {self.exercisequestion}"