from haystack import indexes
from .models import Activity

class ActivityIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    start_date = indexes.DateField(model_attr='start_date', null=True)
    end_date = indexes.DateField(model_attr='end_date', null=True)
    country = indexes.CharField(model_attr='country', faceted=True)
    region = indexes.CharField(model_attr='region', faceted=True)
    activity = indexes.CharField(model_attr='activity', faceted=True)
    objective = indexes.CharField(model_attr='objective', faceted=True)
    thematic = indexes.CharField(model_attr='thematic', faceted=True)
    directorate = indexes.CharField(model_attr='directorate', faceted=True)
    url = indexes.CharField(model_attr='url', null=True)
    db_id = indexes.IntegerField(model_attr='id', null=True)
    
    def get_model(self):
        return Activity

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.all()
