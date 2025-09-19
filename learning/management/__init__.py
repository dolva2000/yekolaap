from django.core.management.base import BaseCommand
from django.db import transaction
from pathlib import Path
import csv

from learning.models import Language, Course, Level, Topic, Item, Exercise

TOPIC_MAP = {
    "salutation": "salutation",
    "politesse": "politesse",
    "presentation": "presentation",
    "origine": "origine",
    "essentiels": "essentiels",
    "verbe_etre": "verbe-etre",
    "mini_phrases": "mini-phrases",
    "contextes": "contextes",
}

class Command(BaseCommand):
    help = "Import CSV (fr -> target) dans items/exercises pour une langue/niveau."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Chemin du CSV")
        parser.add_argument("--language", default="lingala")
        parser.add_argument("--code", default="ln")            # code de langue, ex: ln
        parser.add_argument("--course", default="lingala-a1")  # slug du cours
        parser.add_argument("--level", type=int, default=1)
        parser.add_argument("--truncate", action="store_true", help="Supprimer les items du niveau avant import")

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["file"]).resolve()
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Fichier introuvable: {path}"))
            return

        lang, _ = Language.objects.get_or_create(code=opts["code"], defaults={"name": opts["language"].title()})
        course, _ = Course.objects.get_or_create(language=lang, slug=opts["course"], defaults={"title": f"{lang.name} – A1"})
        level, _ = Level.objects.get_or_create(course=course, number=opts["level"], defaults={"title": f"Niveau {opts['level']}"})

        if opts["truncate"]:
            Item.objects.filter(level=level).delete()

        # Assure que les topics existent
        topics = {}
        for k, slug in TOPIC_MAP.items():
            topics[k] = Topic.objects.get_or_create(course=course, slug=slug, defaults={"name": k.title()})[0]

        created = 0
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                cat = (row.get("category") or "").strip()
                fr = (row.get("fr") or "").strip()
                target = (row.get("target") or "").strip()
                translit = (row.get("translit") or "").strip()
                notes = (row.get("notes") or "").strip()
                audio = (row.get("audio") or "").strip()

                if not fr or not target:
                    continue

                topic = topics.get(cat)
                item, made = Item.objects.get_or_create(
                    level=level, fr=fr, target=target,
                    defaults={"topic": topic, "translit": translit, "notes": notes, "audio_url": audio}
                )
                if made:
                    created += 1
                    Exercise.objects.create(
                        item=item,
                        ex_type="translate",
                        prompt={"from": "fr", "text": fr},
                        answer={"to": "target", "text": target},
                        difficulty=1,
                    )

        self.stdout.write(self.style.SUCCESS(f"Import OK. Items créés: {created}"))