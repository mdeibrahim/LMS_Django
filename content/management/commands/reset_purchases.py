from django.core.management.base import BaseCommand
from django.db import transaction

from content.models import ModulePurchase


class Command(BaseCommand):
    help = 'Reset ModulePurchase.is_purchased to False. Dry-run by default.'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Apply changes (otherwise dry-run)')
        parser.add_argument('--user', type=str, help='Filter by user email')
        parser.add_argument('--course', type=str, help='Filter by course slug')

    def handle(self, *args, **options):
        qs = ModulePurchase.objects.all()
        if options.get('user'):
            qs = qs.filter(user__email=options.get('user'))
        course_slug = options.get('course')
        if course_slug:
            qs = qs.filter(course__slug=course_slug)

        total = qs.count()
        self.stdout.write(f'Found {total} matching ModulePurchase records.')

        if not options.get('yes'):
            self.stdout.write(self.style.WARNING('Dry run — no changes applied. Re-run with --yes to apply.'))
            return

        with transaction.atomic():
            updated = qs.update(is_purchased=False)

        self.stdout.write(self.style.SUCCESS(f'Updated {updated} records: set is_purchased=False.'))
