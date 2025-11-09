from rest_framework import routers
from .views import (
    # ActivityViewSet, 
    ActivityById,
    BulkUploadActivitiesView,
    DeleteActivity,
    ThematicFacetView, 
    CountriesFacetView, 
    RegionsFacetView, 
    DirectorateFacetView, 
    StackedDatasetView,
    DateYearFacetView, 
    ActivitiesPaginatedView,
    UpdateActivity
)
from django.urls import path, include

router = routers.DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),  # keep existing API routes
    path('dashboard/thematic-facets/', ThematicFacetView.as_view(), name='thematic_facets'),
    path('dashboard/country-facets/', CountriesFacetView.as_view(), name='country_facets'),
    path('dashboard/region-facets/', RegionsFacetView.as_view(), name='region_facets'),
    path('dashboard/directorate-facets/', DirectorateFacetView.as_view(), name='directorate_facets'),
    path('dashboard/yearly-facets/', DateYearFacetView.as_view(), name='yearly_facets'),
    path('dashboard/activities/', ActivitiesPaginatedView.as_view(), name='activities'),
    path('dashboard/stacked-dataset/', StackedDatasetView.as_view(), name='stacked_dataset'),

    path('activities/<int:db_id>/', ActivityById.as_view(), name='activity_by_id'),
    path('activities/<int:db_id>/update', UpdateActivity.as_view(), name='update_activity'),
    path('activities/<int:db_id>/delete', DeleteActivity.as_view(), name='delete_activity'),

    path('activities/bulk-upload', BulkUploadActivitiesView.as_view(), name='upload_activity'),
]
