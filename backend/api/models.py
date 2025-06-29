from django.db import models

# Create your models here.

class ProcessedContent(models.Model):
    title = models.CharField(max_length=255, blank=True, default='')
    original_markdown = models.TextField()
    # Store the list of dicts including sentence, keyword, and SELECTED image path
    easy_read_json = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Avoid loading large JSON in admin list view if possible
        title_str = f' - "{self.title}"' if self.title else ''
        return f"Processed Content (ID: {self.id}){title_str} - Created at {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ImageMetadata(models.Model):
    description = models.CharField(max_length=500, blank=True)
    image = models.ImageField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_generated = models.BooleanField(default=False)

    def __str__(self):
        source = "Generated" if self.is_generated else "Uploaded"
        desc = self.description[:50] + '...' if len(self.description) > 50 else self.description
        return f'{source} Image (ID: {self.id}) - "{desc}" - Created: {self.uploaded_at.strftime("%Y-%m-%d %H:%M")}'
