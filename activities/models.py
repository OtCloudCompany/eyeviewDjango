from django.db import models

class Activity(models.Model):
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    country = models.CharField(max_length=100)
    region = models.CharField(max_length=50)
    activity = models.CharField(max_length=200)
    objective = models.CharField(max_length=500)
    thematic = models.CharField(max_length=500)
    directorate = models.CharField(max_length=500)
    url = models.CharField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"{self.country} - {self.activity}"
