from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from typing import Optional

from learning.models import Item
from learning.tts import ensure_tts_mp3


class Command(BaseCommand):
    help = "Pre-generate and cache TTS MP3 files for items."

    def add_arguments(self, parser):
        parser.add_argument("--course", help="Filter by course slug (e.g. lingala-a1)", default=None)
        parser.add_argument("--level", type=int, help="Filter by level number", default=None)
        parser.add_argument("--lang", default="ln", help="Language code for TTS (default: ln)")
        parser.add_argument("--limit", type=int, default=None, help="Limit number of items to process")

    @transaction.atomic
    def handle(self, *args, **opts):
        course_slug: Optional[str] = opts.get("course")
        level_num: Optional[int] = opts.get("level")
        lang_code: str = opts.get("lang") or "ln"
        limit: Optional[int] = opts.get("limit")

        qs = Item.objects.select_related("level", "level__course").filter(is_active=True)
        if course_slug:
            qs = qs.filter(level__course__slug=course_slug)
        if level_num is not None:
            qs = qs.filter(level__number=level_num)
        qs = qs.order_by("level__course__slug", "level__number", "id")
        if limit:
            qs = qs[:limit]

        count = 0
        for item in qs:
            ensure_tts_mp3(item.target or "", lang_code=lang_code, item=item)
            count += 1
            if count % 20 == 0:
                self.stdout.write(f"Processed {count} items...")

        self.stdout.write(self.style.SUCCESS(f"Warm TTS done. Items processed: {count}"))
