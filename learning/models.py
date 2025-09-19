from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify

User = get_user_model()

class Language(models.Model):
    code = models.CharField(max_length=10, unique=True)  # 'ln'
    name = models.CharField(max_length=80)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Course(models.Model):
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.language.code}-a1")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class Level(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=120, blank=True)

    class Meta:
        unique_together = ("course", "number")

    def __str__(self):
        return f"{self.course.slug} L{self.number}"

class Topic(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    slug = models.SlugField()
    name = models.CharField(max_length=120)

    class Meta:
        unique_together = ("course", "slug")

    def __str__(self):
        return f"{self.course.slug}:{self.slug}"

class Item(models.Model):
    KIND_CHOICES = (("phrase", "Phrase"), ("vocab", "Vocab"),)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="phrase")
    fr = models.TextField()
    target = models.TextField()
    translit = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    audio_url = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)

    class Meta:
        unique_together = ("level", "fr", "target")
        indexes = [models.Index(fields=["level", "topic"])]

    def __str__(self):
        return f"{self.fr} -> {self.target}"

class Exercise(models.Model):
    EX_TYPES = (
        ("translate", "Traduction"),
        ("mcq", "Choix multiple"),
        ("listen", "Écoute"),
    )
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    ex_type = models.CharField(max_length=12, choices=EX_TYPES)
    prompt = models.JSONField(null=True, blank=True)
    choices = models.JSONField(null=True, blank=True)
    answer = models.JSONField(null=True, blank=True)
    difficulty = models.PositiveSmallIntegerField(default=1)

class Enrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "course")

class ItemProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    status = models.CharField(max_length=16, default="new")  # new|learning|review|mastered
    last_result = models.BooleanField(null=True)
    streak = models.IntegerField(default=0)
    ease = models.DecimalField(max_digits=4, decimal_places=2, default=2.50)
    interval_days = models.IntegerField(default=0)
    due_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "item")
        indexes = [models.Index(fields=["user", "due_at"])]

class Attempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    is_correct = models.BooleanField()
    time_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MediaAsset(models.Model):
    KIND_CHOICES = (("tts", "TTS"), ("recording", "UserRecording"))
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    lang_code = models.CharField(max_length=10, default="ln")  # ex: 'ln'
    text_hash = models.CharField(max_length=64, db_index=True, blank=True)
    text = models.TextField(blank=True)
    file = models.FileField(upload_to="audio/")
    duration_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Optionnel: lien vers un Item pour rattacher un TTS à un contenu
    item = models.ForeignKey("Item", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.kind}:{self.lang_code}:{self.text_hash or self.file.name}"
