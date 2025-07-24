"""
Management command to generate analytics reports for EasyRead usage.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q
from datetime import datetime, timedelta
import json

from api.models import UserSession, SessionEvent, ImageSelectionChange, ImageSetSelection


class Command(BaseCommand):
    help = 'Generate analytics reports for EasyRead usage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to analyze (default: 30)'
        )
        parser.add_argument(
            '--format',
            choices=['json', 'text'],
            default='text',
            help='Output format: json or text (default: text)'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Include detailed session information'
        )

    def handle(self, *args, **options):
        days = options['days']
        output_format = options['format']
        detailed = options['detailed']
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Generate report
        report = self.generate_report(start_date, end_date, detailed)
        
        # Output report
        if output_format == 'json':
            self.stdout.write(json.dumps(report, indent=2, default=str))
        else:
            self.print_text_report(report, days)

    def generate_report(self, start_date, end_date, detailed=False):
        """Generate analytics report for the specified date range."""
        
        # Base queryset for sessions in date range
        sessions = UserSession.objects.filter(
            started_at__gte=start_date,
            started_at__lt=end_date
        )
        
        # Basic session statistics
        total_sessions = sessions.count()
        
        # Session completion funnel
        sessions_with_pdf = sessions.filter(pdf_uploaded=True).count()
        sessions_with_processing = sessions.filter(sentences_generated__gt=0).count()
        sessions_with_export = sessions.filter(exported_result=True).count()
        
        # Content processing statistics
        total_sentences = sessions.aggregate(total=Sum('sentences_generated'))['total'] or 0
        avg_sentences_per_session = sessions.filter(
            sentences_generated__gt=0
        ).aggregate(avg=Avg('sentences_generated'))['avg'] or 0
        
        # PDF upload statistics
        pdf_sessions = sessions.filter(pdf_uploaded=True)
        total_pdf_size = pdf_sessions.aggregate(total=Sum('pdf_size_bytes'))['total'] or 0
        avg_pdf_size = pdf_sessions.aggregate(avg=Avg('pdf_size_bytes'))['avg'] or 0
        
        # Input content statistics
        content_sessions = sessions.filter(input_content_size__gt=0)
        total_input_content = content_sessions.aggregate(total=Sum('input_content_size'))['total'] or 0
        avg_input_content = content_sessions.aggregate(avg=Avg('input_content_size'))['avg'] or 0
        
        # Session duration statistics
        session_durations = []
        for session in sessions:
            duration = (session.last_activity - session.started_at).total_seconds() / 60
            session_durations.append(duration)
        
        avg_session_duration = sum(session_durations) / len(session_durations) if session_durations else 0
        
        # Event statistics
        events = SessionEvent.objects.filter(
            session__in=sessions
        )
        
        event_counts = events.values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Image selection statistics
        image_changes = ImageSelectionChange.objects.filter(
            session__in=sessions
        )
        
        total_image_changes = image_changes.count()
        avg_image_changes_per_session = sessions.filter(
            image_changes__isnull=False
        ).annotate(
            change_count=Count('image_changes')
        ).aggregate(avg=Avg('change_count'))['avg'] or 0
        
        # Popular image sets
        popular_sets = ImageSetSelection.objects.filter(
            session__in=sessions
        ).values('image_set__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Build report structure
        report = {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days
            },
            'sessions': {
                'total': total_sessions,
                'with_pdf_upload': sessions_with_pdf,
                'with_processing': sessions_with_processing,
                'with_export': sessions_with_export,
                'conversion_rates': {
                    'pdf_to_processing': (sessions_with_processing / sessions_with_pdf * 100) if sessions_with_pdf > 0 else 0,
                    'processing_to_export': (sessions_with_export / sessions_with_processing * 100) if sessions_with_processing > 0 else 0,
                    'pdf_to_export': (sessions_with_export / sessions_with_pdf * 100) if sessions_with_pdf > 0 else 0
                },
                'avg_duration_minutes': avg_session_duration
            },
            'content': {
                'total_sentences_generated': total_sentences,
                'avg_sentences_per_session': avg_sentences_per_session,
                'total_pdf_size_bytes': total_pdf_size,
                'avg_pdf_size_bytes': avg_pdf_size,
                'total_input_content_chars': total_input_content,
                'avg_input_content_chars': avg_input_content
            },
            'events': {
                'total': events.count(),
                'by_type': list(event_counts)
            },
            'images': {
                'total_selection_changes': total_image_changes,
                'avg_changes_per_session': avg_image_changes_per_session,
                'popular_image_sets': list(popular_sets)
            }
        }
        
        # Add detailed session info if requested
        if detailed:
            detailed_sessions = []
            for session in sessions.select_related().prefetch_related('events', 'image_changes'):
                session_data = {
                    'id': str(session.session_id),
                    'started_at': session.started_at,
                    'last_activity': session.last_activity,
                    'duration_minutes': (session.last_activity - session.started_at).total_seconds() / 60,
                    'ip_address': session.ip_address,
                    'pdf_uploaded': session.pdf_uploaded,
                    'pdf_size_bytes': session.pdf_size_bytes,
                    'input_content_size': session.input_content_size,
                    'sentences_generated': session.sentences_generated,
                    'exported_result': session.exported_result,
                    'events': list(session.events.values('event_type', 'timestamp')),
                    'image_changes': session.image_changes.count()
                }
                detailed_sessions.append(session_data)
            
            report['detailed_sessions'] = detailed_sessions
        
        return report

    def print_text_report(self, report, days):
        """Print a formatted text report."""
        
        self.stdout.write(self.style.SUCCESS(f'\n=== EasyRead Analytics Report ({days} days) ===\n'))
        
        # Period info
        period = report['period']
        self.stdout.write(f"Period: {period['start_date'].strftime('%Y-%m-%d')} to {period['end_date'].strftime('%Y-%m-%d')}")
        
        # Session statistics
        sessions = report['sessions']
        self.stdout.write(f"\n📊 Session Statistics:")
        self.stdout.write(f"  Total Sessions: {sessions['total']}")
        self.stdout.write(f"  Sessions with PDF Upload: {sessions['with_pdf_upload']}")
        self.stdout.write(f"  Sessions with Processing: {sessions['with_processing']}")
        self.stdout.write(f"  Sessions with Export: {sessions['with_export']}")
        self.stdout.write(f"  Average Session Duration: {sessions['avg_duration_minutes']:.1f} minutes")
        
        # Conversion rates
        conv = sessions['conversion_rates']
        self.stdout.write(f"\n🔄 Conversion Rates:")
        self.stdout.write(f"  PDF Upload → Processing: {conv['pdf_to_processing']:.1f}%")
        self.stdout.write(f"  Processing → Export: {conv['processing_to_export']:.1f}%")
        self.stdout.write(f"  PDF Upload → Export: {conv['pdf_to_export']:.1f}%")
        
        # Content statistics
        content = report['content']
        self.stdout.write(f"\n📝 Content Statistics:")
        self.stdout.write(f"  Total Sentences Generated: {content['total_sentences_generated']}")
        self.stdout.write(f"  Average Sentences per Session: {content['avg_sentences_per_session']:.1f}")
        self.stdout.write(f"  Total PDF Size: {content['total_pdf_size_bytes'] / (1024*1024):.1f} MB")
        self.stdout.write(f"  Average PDF Size: {content['avg_pdf_size_bytes'] / (1024*1024):.1f} MB")
        self.stdout.write(f"  Total Input Content: {content['total_input_content_chars']} characters")
        self.stdout.write(f"  Average Input Content: {content['avg_input_content_chars']:.0f} characters")
        
        # Event statistics
        events = report['events']
        self.stdout.write(f"\n🎯 Event Statistics:")
        self.stdout.write(f"  Total Events: {events['total']}")
        self.stdout.write(f"  Top Events:")
        for event in events['by_type'][:5]:
            self.stdout.write(f"    {event['event_type']}: {event['count']}")
        
        # Image statistics
        images = report['images']
        self.stdout.write(f"\n🖼️  Image Statistics:")
        self.stdout.write(f"  Total Image Selection Changes: {images['total_selection_changes']}")
        self.stdout.write(f"  Average Changes per Session: {images['avg_changes_per_session']:.1f}")
        self.stdout.write(f"  Popular Image Sets:")
        for image_set in images['popular_image_sets'][:5]:
            self.stdout.write(f"    {image_set['image_set__name']}: {image_set['count']} selections")
        
        # Detailed sessions if available
        if 'detailed_sessions' in report:
            self.stdout.write(f"\n📋 Detailed Session Information:")
            for session in report['detailed_sessions'][:10]:  # Show first 10 sessions
                self.stdout.write(f"  Session {session['id'][:8]}...")
                self.stdout.write(f"    Duration: {session['duration_minutes']:.1f} min")
                self.stdout.write(f"    PDF: {session['pdf_uploaded']}, Processing: {session['sentences_generated']} sentences")
                self.stdout.write(f"    Export: {session['exported_result']}, Image Changes: {session['image_changes']}")
                self.stdout.write(f"    Events: {len(session['events'])}")
        
        self.stdout.write(f"\n" + "="*60)