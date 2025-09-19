from rest_framework import serializers
from .models import Language, Course, Level, Topic, Item, Exercise, Attempt, ItemProgress


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ["id", "code", "name"]


class CourseSerializer(serializers.ModelSerializer):
    language = LanguageSerializer(read_only=True)

    class Meta:
        model = Course
        fields = ["id", "slug", "title", "description", "language"]


class LevelSerializer(serializers.ModelSerializer):
    course = serializers.SlugRelatedField(read_only=True, slug_field="slug")

    class Meta:
        model = Level
        fields = ["id", "course", "number", "title"]


class ItemSerializer(serializers.ModelSerializer):
    topic = serializers.SlugRelatedField(read_only=True, slug_field="slug")

    class Meta:
        model = Item
        fields = ["id", "kind", "fr", "target", "translit", "notes", "audio_url", "topic"]


class ExerciseSerializer(serializers.ModelSerializer):
    item = ItemSerializer(read_only=True)

    class Meta:
        model = Exercise
        fields = ["id", "ex_type", "prompt", "choices", "answer", "difficulty", "item"]


class AttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attempt
        fields = ["id", "exercise", "is_correct", "time_ms", "created_at"]
