from django.shortcuts import render

import random
from difflib import SequenceMatcher

from django.utils import timezone as dj_tz
from django.conf import settings
from rest_framework import viewsets, mixins, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound

from .models import Language, Course, Level, Item, Exercise, Attempt, ItemProgress
from .serializers import (
    LanguageSerializer, CourseSerializer, LevelSerializer,
    ExerciseSerializer, AttemptSerializer
)
from .utils import normalize
from .srs import schedule_after_review
from .tts import ensure_tts_mp3
from .asr import transcribe_local


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


class IsAuthOrRead(permissions.IsAuthenticatedOrReadOnly):
    pass


class CourseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Course.objects.select_related("language").all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthOrRead]
    lookup_field = "slug"


class LevelViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = LevelSerializer
    permission_classes = [IsAuthOrRead]

    def get_queryset(self):
        q = Level.objects.select_related("course", "course__language")
        course_slug = self.request.query_params.get("course")
        if course_slug:
            q = q.filter(course__slug=course_slug)
        return q.order_by("number")


class PracticeViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_course_level(self, request):
        course = request.query_params.get("course") or request.data.get("course")
        level = request.query_params.get("level") or request.data.get("level")
        if not course or not level:
            raise ValidationError("params requis: course=slug & level=numero")
        try:
            lvl = Level.objects.select_related("course").get(course__slug=course, number=int(level))
        except Level.DoesNotExist:
            raise NotFound("Niveau introuvable")
        return lvl

    @action(detail=False, methods=["post"])
    def start(self, request):
        lvl = self._get_course_level(request)
        # petit récap pour le client
        total_items = Item.objects.filter(level=lvl, is_active=True).count()
        return Response({
            "course": lvl.course.slug,
            "level": lvl.number,
            "total_items": total_items
        })

    @action(detail=False, methods=["get"])
    def progress(self, request):
        """Return progress statistics for a given level (requires course & level)."""
        user = request.user
        lvl = self._get_course_level(request)
        total = Item.objects.filter(level=lvl, is_active=True).count()

        # User-specific progress aggregates
        qs = ItemProgress.objects.filter(user=user, item__level=lvl)
        learned = qs.exclude(status="new").count() if hasattr(ItemProgress, "status") else qs.count()
        due = qs.filter(due_at__lte=dj_tz.now()).count()
        mastered = qs.filter(streak__gte=5).count()

        return Response({
            "course": lvl.course.slug,
            "level": lvl.number,
            "total": total,
            "learned": learned,
            "due": due,
            "mastered": mastered,
        })

    @action(detail=False, methods=["get"])
    def next(self, request):
        """
        Returns next exercise. Supports mode parameter:
        - translate (default): prompt=FR, expect Lingala text
        - listen: generate TTS for Lingala (target), expect FR text
        - speak: prompt=FR, expect Lingala (can be audio upload in answer)
        - mcq: prompt=FR, returns multiple choices with 1 correct target
        """
        user = request.user
        lvl = self._get_course_level(request)
        mode = (request.query_params.get("mode") or "translate").lower()

        now = dj_tz.now()

        # 1) items dus (SRS)
        due_qs = (
            ItemProgress.objects.filter(user=user, item__level=lvl, due_at__lte=now)
            .select_related("item")
            .order_by("due_at")
        )
        if due_qs.exists():
            candidate = random.choice(list(due_qs[:5])).item
        else:
            # 2) nouveaux items (sans ItemProgress)
            learned_item_ids = ItemProgress.objects.filter(user=user, item__level=lvl).values_list("item_id", flat=True)
            new_qs = Item.objects.filter(level=lvl, is_active=True).exclude(id__in=learned_item_ids)
            if new_qs.exists():
                candidate = random.choice(list(new_qs[:20]))
            else:
                # 3) révision aléatoire
                rev_qs = (
                    ItemProgress.objects.filter(user=user, item__level=lvl)
                    .select_related("item")
                    .order_by("?")
                )
                if not rev_qs.exists():
                    return Response({"detail": "Aucun item à pratiquer (niveau vide ?)"}, status=200)
                candidate = rev_qs.first().item

        # Trouver / créer un exercice basique de traduction
        ex = Exercise.objects.filter(item=candidate, ex_type="translate").first()
        if not ex:
            ex = Exercise.objects.create(
                item=candidate,
                ex_type="translate",
                prompt={"from": "fr", "text": candidate.fr},
                answer={"to": "target", "text": candidate.target},
                difficulty=1,
            )

        # Build payload with mode-specific fields
        payload = {
            "id": ex.id,
            "item": {"id": candidate.id, "fr": candidate.fr, "target": candidate.target},
            "mode": mode,
            "prompt": None,
            "audio_url": None,
            "choices": None,
        }

        if mode == "listen":
            # TTS of Lingala target; expect FR from user
            asset = ensure_tts_mp3(candidate.target, lang_code="ln", item=candidate)
            payload["prompt"] = {"from": "target", "text": None}
            payload["audio_url"] = settings.MEDIA_URL + asset.file.name
        elif mode == "speak":
            # Show FR; expect Lingala (text or audio)
            payload["prompt"] = {"from": "fr", "text": candidate.fr}
        elif mode == "mcq":
            # Build MCQ with 1 correct (target) + up to 3 distractors from the same level
            payload["prompt"] = {"from": "fr", "text": candidate.fr}
            correct = (candidate.target or "").strip()
            # sample distractors
            others = (
                Item.objects.filter(level=lvl, is_active=True)
                .exclude(id=candidate.id)
                .values_list("target", flat=True)
            )
            distractors = []
            for t in others:
                t = (t or "").strip()
                if not t or normalize(t) == normalize(correct):
                    continue
                if all(normalize(t) != normalize(d) for d in distractors):
                    distractors.append(t)
                if len(distractors) >= 10:
                    break
            import random as _r
            choices_pool = distractors[:]
            _r.shuffle(choices_pool)
            choices = [correct] + choices_pool[:3]
            _r.shuffle(choices)
            payload["choices"] = choices
        else:
            # translate text->text
            payload["prompt"] = {"from": "fr", "text": candidate.fr}

        return Response({"exercise": payload})

    @action(detail=False, methods=["post"])
    def answer(self, request):
        """
        Accepts answer as text (answer/answer_text) or as audio file (multipart "file").
        Uses similarity for tolerant matching. Updates SRS progression.
        """
        user = request.user
        exercise_id = request.data.get("exercise_id")
        if not exercise_id:
            raise ValidationError("exercise_id requis")
        try:
            ex = Exercise.objects.select_related("item").get(id=exercise_id)
        except Exercise.DoesNotExist:
            raise NotFound("Exercice introuvable")

        expected_target = (ex.item.target or "").strip()
        expected_fr = (ex.item.fr or "").strip()

        # Resolve mode to decide expected side
        mode = (request.data.get("mode") or "translate").lower()
        if mode == "listen":
            expected = expected_fr
        elif mode == "mcq":
            expected = expected_target
        else:
            expected = expected_target

        # Read user answer as text or via uploaded audio transcription
        user_answer = (request.data.get("answer") or request.data.get("answer_text") or "").strip()
        if not user_answer and "file" in request.FILES:
            up = request.FILES["file"]
            import tempfile, os
            suffix = ".wav" if up.name.lower().endswith(".wav") else ".mp3"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                for chunk in up.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            text = transcribe_local(tmp_path) or ""
            user_answer = text.strip()
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        # If MCQ, allow the client to send either text in `answer` or index `answer_index`
        if mode == "mcq" and not user_answer:
            try:
                idx = int(request.data.get("answer_index"))
            except (TypeError, ValueError):
                idx = None
            # for stateless check, also allow client to send back the selected choice string in `choice`
            user_answer = (request.data.get("choice") or "").strip() if idx is None else user_answer

        # Evaluate with synonyms tolerance
        synonyms = []
        if ex.answer and isinstance(ex.answer, dict):
            syns = ex.answer.get("synonyms")
            if isinstance(syns, list):
                synonyms = [str(s) for s in syns]

        exact = normalize(user_answer) == normalize(expected) or any(
            normalize(user_answer) == normalize(s) for s in synonyms
        )
        ok = exact or (similarity(user_answer, expected) >= 0.85)

        # Log attempt
        Attempt.objects.create(
            user=user, exercise=ex, is_correct=ok, time_ms=request.data.get("time_ms")
        )

        # Update SRS
        ip, _ = ItemProgress.objects.get_or_create(user=user, item=ex.item)
        ip.last_result = ok
        if ok:
            ip.streak = (ip.streak or 0) + 1
            ip.status = "review" if ip.streak >= 3 else "learning"
        else:
            ip.streak = 0
            ip.status = "learning"

        new_ease, new_interval, due_delta = schedule_after_review(ok, float(ip.ease), int(ip.interval_days))
        ip.ease = new_ease
        ip.interval_days = new_interval
        ip.due_at = dj_tz.now() + due_delta
        ip.save()

        return Response({
            "correct": ok,
            "expected": expected,
            "you_said": user_answer,
            "streak": ip.streak,
            "next_due_at": ip.due_at,
        })
