from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from haystack import connections
from .models import Activity

@receiver(post_save, sender=Activity)
def update_activity_index(sender, instance, **kwargs):
    # Update or create document in Solr
    backend = connections['default'].get_backend()
    backend.update(sender, [instance])

@receiver(post_delete, sender=Activity)
def delete_activity_index(sender, instance, **kwargs):
    # Remove document from Solr
    backend = connections['default'].get_backend()
    backend.remove("activities.activity.%s" % instance.pk)
