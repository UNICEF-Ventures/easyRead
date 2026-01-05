from django.contrib import admin
from .models import ProcessedContent, ImageSet, Image, Embedding, WhitelistedEmail, OTPToken

# Register your models here.

@admin.register(ProcessedContent)
class ProcessedContentAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'original_markdown')
    readonly_fields = ('created_at',)


# New models for refactored system
@admin.register(ImageSet)
class ImageSetAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'image_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    
    def image_count(self, obj):
        return obj.images.count()
    image_count.short_description = 'Number of Images'

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'filename', 'set', 'file_format', 'file_size', 'has_embeddings', 'created_at')
    list_filter = ('file_format', 'set', 'created_at')
    search_fields = ('filename', 'description', 'set__name')
    readonly_fields = ('created_at',)
    raw_id_fields = ('set',)
    
    def has_embeddings(self, obj):
        return obj.embeddings.exists()
    has_embeddings.boolean = True
    has_embeddings.short_description = 'Has Embeddings'

@admin.register(Embedding)
class EmbeddingAdmin(admin.ModelAdmin):
    list_display = ('id', 'image', 'embedding_type', 'model_name', 'created_at')
    list_filter = ('embedding_type', 'model_name', 'created_at')
    search_fields = ('image__filename', 'image__set__name')
    readonly_fields = ('created_at', 'vector')
    raw_id_fields = ('image',)


# OTP Authentication Models

@admin.register(WhitelistedEmail)
class WhitelistedEmailAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'is_active', 'last_login', 'created_at')
    list_filter = ('is_active', 'created_at', 'last_login')
    search_fields = ('email', 'name')
    readonly_fields = ('created_at', 'last_login')
    list_editable = ('is_active',)
    ordering = ('email',)

    actions = ['activate_emails', 'deactivate_emails']

    def activate_emails(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} email(s) activated.')
    activate_emails.short_description = 'Activate selected emails'

    def deactivate_emails(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} email(s) deactivated.')
    deactivate_emails.short_description = 'Deactivate selected emails'


@admin.register(OTPToken)
class OTPTokenAdmin(admin.ModelAdmin):
    list_display = ('email', 'token', 'created_at', 'expires_at', 'used', 'attempts', 'status')
    list_filter = ('used', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('email', 'token', 'created_at', 'expires_at', 'used', 'used_at', 'attempts')
    ordering = ('-created_at',)

    def status(self, obj):
        if obj.used:
            return 'Used'
        from django.utils import timezone
        if obj.expires_at <= timezone.now():
            return 'Expired'
        return 'Valid'
    status.short_description = 'Status'

    def has_add_permission(self, request):
        return False  # OTPs should only be created via the API
