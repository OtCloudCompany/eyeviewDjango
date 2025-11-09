from datetime import datetime
from http.client import BAD_REQUEST, NOT_FOUND, OK
from rest_framework.parsers import MultiPartParser, FormParser
import pandas as pd
import chardet
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.generics import DestroyAPIView, RetrieveAPIView, UpdateAPIView, get_object_or_404
from .models import Activity
from .serializers import ActivitySerializer
from rest_framework.permissions import IsAuthenticated
from haystack.query import SearchQuerySet
from haystack.inputs import Exact
from haystack import connections
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.paginator import Paginator, EmptyPage
from urllib.parse import unquote
from django.db import transaction
from rest_framework import status

def _get_list_param(request, name):
    """
    Return a list for a query param name, supporting repeated and comma-separated values.
    """
    values = request.GET.getlist(name)
    if len(values) == 1 and "," in values[0]:
        values = [v.strip() for v in values[0].split(",") if v.strip()]
    return [v for v in values if v]

def _apply_common_filters(sqs, request):
    """
    Apply country, region, and thematic filters (when present) to the SQS.
    Uses *_exact fields for precise filtering in Solr.
    
    Handles URL-encoded values (e.g., 'South%20Africa') and ensures exact matching
    for values containing spaces by using the Exact input type.
    """
    thematics = request.GET.get('f.thematics')
    countries = request.GET.get('f.countries')
    regions = request.GET.get('f.regions')

    # URL-decode values and use Exact input type for proper quoting of multi-word values
    if countries:
        # Django usually URL-decodes GET params, but unquote ensures it's decoded
        countries_decoded = unquote(countries)
        # Pass Exact input type directly to ensure proper quoting for Solr queries with spaces
        sqs = sqs.filter(country_exact_str=Exact(countries_decoded))
    if regions:
        regions_decoded = unquote(regions)
        sqs = sqs.filter(region_exact_str=Exact(regions_decoded))
    if thematics:
        thematics_decoded = unquote(thematics)
        sqs = sqs.filter(thematic_exact_str=Exact(thematics_decoded))

    return sqs

class ThematicFacetView(APIView):
    """
    Returns facet counts of thematic areas using Haystack SearchQuerySet.
    """
    
    http_method_names = ['get']

    def get(self, request):
        sqs = _apply_common_filters(SearchQuerySet(), request).facet('thematic_exact_str')
        facet_data = sqs.facet_counts()

        if not facet_data or 'fields' not in facet_data:
            return Response({"detail": "No facet data found"}, status=404)

        thematic_facets = facet_data['fields'].get('thematic_exact_str', [])
        result = [
            {"thematic_area": theme, "count": count} for theme, count in thematic_facets
        ]

        return Response(result)

class CountriesFacetView(APIView):
    """
    Returns facet counts of countries using Haystack SearchQuerySet.
    """

    def get(self, request):
        sqs = _apply_common_filters(SearchQuerySet(), request).facet('country_exact_str')
        
        facet_data = sqs.facet_counts()

        if not facet_data or 'fields' not in facet_data:
            return Response({"detail": "No facet data found"}, status=404)

        country_facets = facet_data['fields'].get('country_exact_str', [])
        result = [
            {"country": country, "count": count} for country, count in country_facets
        ]

        return Response(result)
    
class RegionsFacetView(APIView):
    """
    Returns facet counts of regions using Haystack SearchQuerySet.
    """

    def get(self, request):
        sqs = _apply_common_filters(SearchQuerySet(), request).facet('region_exact_str')
        
        facet_data = sqs.facet_counts()

        if not facet_data or 'fields' not in facet_data:
            return Response({"detail": "No facet data found"}, status=404)
        region_facets = facet_data['fields'].get('region_exact_str', [])
        
        result = [
            {"region": theme, "count": count}
            for theme, count in region_facets
        ]
        return Response(result)
    
class DirectorateFacetView(APIView):
    """
    Returns facet counts of directorates using Haystack SearchQuerySet.
    """

    def get(self, request):
        try:
            sqs = _apply_common_filters(SearchQuerySet(), request).facet('directorate_exact_str')
        except Exception as e:
            return Response({"detail": f"Search backend unavailable: {e}"}, status=503)
        
        facet_data = sqs.facet_counts()

        if not facet_data or 'fields' not in facet_data:
            return Response({"detail": "No facet data found"}, status=404)
        directorate_facets = facet_data['fields'].get('directorate_exact_str', [])
        
        result = [
            {"directorate": directorate, "count": count} for directorate, count in directorate_facets
        ]
        return Response(result)

class DateYearFacetView(APIView):
    """
    Returns yearly cumulative facet counts of 'start_date' using Haystack SearchQuerySet.
    """
    def get(self, request):
        sqs = _apply_common_filters(SearchQuerySet(), request).facet('start_date')
        facet_data = sqs.facet_counts()

        if not facet_data or 'fields' not in facet_data:
            return Response({"detail": "No facet data found"}, status=404)

        # Date facet - usually returns: [('2022-01-01T00:00:00Z', 4), ('2022-02-01T00:00:00Z', 2), ...]
        date_facets = facet_data['fields'].get('start_date', [])

        # Build cumulative sum per year
        yearly_counts = {}

        for date_str, count in date_facets:
            # Extract year only (assumes date_str like 'YYYY-MM-DD...' )
            year = date_str[:4]
            yearly_counts[year] = yearly_counts.get(year, 0) + count

        # Transform for API output
        result = [
            {"year": year, "count": yearly_counts[year]} for year in sorted(yearly_counts)
        ]
        return Response(result)

class ActivitiesPaginatedView(APIView):
    """
    Returns paginated Solr records with only *_exact fields, 10 per page.
    """
    SOLR_FIELDS_TO_RETRIEVE = [
        'id', 'db_id', 'url', 'start_date', 'end_date', 'country_exact', 
        'region_exact', 'activity_exact', 'objective_exact', 
        'thematic_exact', 'directorate_exact'
    ]

    def get(self, request):
        try:
            # 1. Start with a SearchQuerySet to get all documents.
            #    Using .values() is the key to selecting specific fields.
            base_sqs = _apply_common_filters(SearchQuerySet().all(), request)
            all_records_sqs = base_sqs.order_by('-start_date').values(*self.SOLR_FIELDS_TO_RETRIEVE)

            # 2. Get the page number from the request's query parameters.
            #    Default to page 1 if 'page' is not provided.
            page_number = request.GET.get('page', 1)

            page_size = request.GET.get('per_page', 10)
            
            # 3. Use Django's built-in Paginator.
            #    It efficiently handles slicing the queryset for the correct page.
            paginator = Paginator(all_records_sqs, page_size)
            page_obj = paginator.get_page(page_number)

            # 4. Prepare the data for the JSON response.
            #    The page_obj.object_list contains a list of dictionaries 
            #    with the fields we requested.
            results = list(page_obj.object_list)

            # 5. Fix truncated url values for text_en fields (like 'url')
            #    .values() on analyzed text_en fields only returns the first token.
            #    Query the Django model directly using db_id to get the correct URL value.
            if results:
                # Collect all db_ids from the results
                db_ids = [r.get('db_id') for r in results if r.get('db_id')]
                
                if db_ids:
                    # Query the Django model directly to get correct URL values
                    # This bypasses Solr's tokenized storage and gets the actual value
                    from .models import Activity
                    activities = Activity.objects.filter(id__in=db_ids)
                    url_map = {str(act.id): act.url for act in activities if act.url}
                    
                    # Replace truncated url values with correct values from the database
                    for record in results:
                        db_id = record.get('db_id')
                        if db_id and str(db_id) in url_map:
                            record['url'] = url_map[str(db_id)]

            # 6. Construct a structured JSON response with pagination metadata.
            response_data = {
                'count': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': page_obj.number,
                'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
                'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
                'results': results
            }
            
            return Response(response_data)

        except (ValueError, EmptyPage) as e:
            # Handle cases where the page number is not an integer or is out of range.
            return Response({'error': f'Invalid page number: {str(e)}'}, status=400)
            
        except Exception as e:
            # Generic error handler for unexpected issues (e.g., Solr connection error).
            return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

class StackedDatasetView(APIView):
    queryset = SearchQuerySet().all().order_by('-start_date')
    permission_classes = [IsAuthenticated]
    SOLR_FIELDS_TO_RETRIEVE = [
        'id', 'country_exact', 'thematic_exact'
    ]

    def get(self, request):
        try:
            # 1. Start with a SearchQuerySet to get all documents.
            #    Using .values() is the key to selecting specific fields.
            base_sqs = _apply_common_filters(self.queryset, request)
            all_records_sqs = base_sqs.values(*self.SOLR_FIELDS_TO_RETRIEVE)
            # Convert ValuesSearchQuerySet to a list for JSON serialization
            results = list(all_records_sqs)
            
            # 2. Format data for stacked bar chart (countries on y-axis, thematic areas as stacks)
            #    Group by country and count thematic areas
            country_thematic_counts = {}
            all_thematic_areas = set()
            
            for record in results:
                country = record.get('country_exact')
                thematic = record.get('thematic_exact')
                
                # Skip records without required fields
                if not country or not thematic:
                    continue
                
                # Initialize country entry if needed
                if country not in country_thematic_counts:
                    country_thematic_counts[country] = {}
                
                # Count thematic areas per country
                country_thematic_counts[country][thematic] = \
                    country_thematic_counts[country].get(thematic, 0) + 1
                
                # Track all unique thematic areas
                all_thematic_areas.add(thematic)
            
            # 3. Sort countries and thematic areas for consistent ordering
            sorted_countries = sorted(country_thematic_counts.keys())
            sorted_thematic_areas = sorted(all_thematic_areas)
            
            # 4. Format as Chart.js-compatible structure for stacked bar chart
            #    labels = countries (y-axis), datasets = thematic areas (stacks)
            chart_data = {
                'labels': sorted_countries,
                'datasets': []
            }
            
            # Create a dataset for each thematic area
            for thematic_area in sorted_thematic_areas:
                dataset = {
                    'label': thematic_area,
                    'data': []
                }
                
                # For each country, add the count for this thematic area (0 if none)
                for country in sorted_countries:
                    count = country_thematic_counts[country].get(thematic_area, 0)
                    dataset['data'].append(count)
                
                chart_data['datasets'].append(dataset)
            
            return Response(chart_data)
        except Exception as e:
            return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

class ActivityById(RetrieveAPIView):
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, db_id):

        single_activity = get_object_or_404(Activity, pk=db_id)
        serializer = self.serializer_class(single_activity)
        resp_data = serializer.data

        return Response(resp_data)
    
class UpdateActivity(UpdateAPIView):
    """
    This view handles updating an Activity.
    - Send a PUT request with full data to update.
    - Send a PATCH request with partial data to update.
    """
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]
    
    # 1. Tell the view what data to look at
    queryset = Activity.objects.all()
    
    # 2. Tell the view which URL field contains the ID
    #    (This maps 'db_id' from your URL to the database 'pk')
    lookup_field = 'id'
    lookup_url_kwarg = 'db_id'

class DeleteActivity(DestroyAPIView):
    """
    Handles DELETE requests to delete a single Activity instance.
    """
    queryset = Activity.objects.all()
    permission_classes = [IsAuthenticated]
    
    lookup_field = 'id'
    lookup_url_kwarg = 'db_id'

# class ActivityCSVUploadView(APIView):
class BulkUploadActivitiesView(APIView):
    """
    Upload a CSV file and import rows into the Activity model.
    Uses pandas for robust parsing, handles encodings automatically,
    and returns a detailed summary of the import process.
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        
        file = request.FILES.get('file')

        if not file:
            return Response({"error": "No file uploaded."},
                            status=status.HTTP_400_BAD_REQUEST)

        if not file.name.lower().endswith('.csv'):
            return Response({"error": "Only CSV files are allowed."},
                            status=status.HTTP_400_BAD_REQUEST)
        

        try:
            # ------------------------------------------------------------------
            # 🔍 Step 1: Detect file encoding using chardet
            # ------------------------------------------------------------------
            raw_bytes = file.read()
            detected = chardet.detect(raw_bytes)
            encoding = detected.get("encoding", "utf-8") or "utf-8"
            file.seek(0)

            # ------------------------------------------------------------------
            # 📖 Step 2: Try reading CSV using pandas
            # ------------------------------------------------------------------
            try:
                df = pd.read_csv(file, encoding=encoding, dtype=str, keep_default_na=False)
                                                 
            except UnicodeDecodeError:
                
                # fallback encodings for Excel / Windows CSVs
                file.seek(0)
                df = pd.read_csv(file, encoding="cp1252", dtype=str, keep_default_na=False)
                encoding = "cp1252"
            except Exception as e:
                return Response(
                    {"error": f"Unable to read CSV: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ------------------------------------------------------------------
            # 🧹 Step 3: Normalize DataFrame
            # ------------------------------------------------------------------
            # Strip whitespace and replace fancy quotes
            df = df.applymap(lambda x: str(x).strip()
                             .replace('\u2019', "'")
                             .replace('\u201c', '"')
                             .replace('\u201d', '"')
                             if isinstance(x, str) else x)

            # Optional: normalize column names to lowercase
            df.columns = [c.strip().lower() for c in df.columns]

            # Optional: auto-map alternate column names (if needed)
            column_map = {
                'start': 'start_date',
                'startdate': 'start_date',
                'end': 'end_date',
                'enddate': 'end_date',
                'country name': 'country',
                'activity name': 'activity',
            }
            df.rename(columns=column_map, inplace=True)

            # ------------------------------------------------------------------
            # 🧩 Step 4: Parse rows into Activity objects
            # ------------------------------------------------------------------
            activities = []
            invalid_rows = []
            skipped_rows = 0

            def parse_date(value, row_num, field):
                if not value:
                    return None
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                    try:
                        return datetime.strptime(value.strip(), fmt).date()
                    except ValueError:
                        continue
                invalid_rows.append(
                    f"Row {row_num}: invalid {field} '{value}'")
                return None

            for i, row in df.iterrows():
                row_num = i + 2  # header is row 1
                try:
                    print(row.get('country'), row_num)
                    start_date = parse_date(row.get('start_date'), row_num, 'start_date')
                    end_date = parse_date(row.get('end_date'), row_num, 'end_date')
                    country = row.get('country', '').strip()
                    region = row.get('region', '').strip()
                    activity_name = row.get('activity', '').strip()

                    if not activity_name or not country:
                        skipped_rows += 1
                        continue

                    activities.append(Activity(
                        start_date=start_date,
                        end_date=end_date,
                        country=country,
                        region=region,
                        activity=activity_name,
                        objective=row.get('objective', '').strip(),
                        thematic=row.get('thematic', '').strip(),
                        directorate=row.get('directorate', '').strip(),
                        url=row.get('url', '').strip(),
                    ))
                except Exception as e:
                    invalid_rows.append(f"Row {row_num}: {str(e)}")

            # ------------------------------------------------------------------
            # 💾 Step 5: Bulk insert inside atomic transaction
            # ------------------------------------------------------------------
            with transaction.atomic():
                created = Activity.objects.bulk_create(
                    activities, ignore_conflicts=True
                )

            imported_count = len(created)

            # ------------------------------------------------------------------
            # 📊 Step 6: Build and return summary
            # ------------------------------------------------------------------
            summary = {
                "message": "Upload complete.",
                "imported": imported_count,
                "skipped": skipped_rows,
                "invalid_rows": invalid_rows,
                "encoding_used": encoding,
                "total_rows": len(df),
            }
            # ✅ Trigger partial reindex of just these records
            # backend = connections['default'].get_backend()
            # backend.update(Activity, created)

            return Response(summary, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
