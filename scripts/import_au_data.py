import csv
import os
from activities.models import Activity
from django.conf import settings
from datetime import datetime

def parse_date(value):
    """
    Converts '1/10/2021' or '01-10-2021' → datetime.date(2021, 10, 1)
    Returns None if empty or invalid.
    """
    if not value:
        return None

    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    print(f"⚠️ Skipping invalid date: {value}")
    return None


def run():
    """
    Imports AU activity data from a CSV file into the Activity model.
    Expects a CSV with columns: country, audb.thematic, count
    """
    csv_path = os.path.join(settings.BASE_DIR, 'resources', 'au-data-test.csv')

    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found at {csv_path}")
        return

    print(f"📂 Importing data from {csv_path} ... 💕")

    Activity.objects.all().delete()  # optional: clear previous data

    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        total = 0

        for row in reader:
            start_date = parse_date(row.get('start_date', '').strip())
            end_date = parse_date(row.get('end_date', '').strip())
            country = row.get('country', '').strip()
            region = row.get('region', '').strip()
            activity = row.get('activity', '').strip()
            objective = row.get('objective', '').strip()
            directorate = row.get('directorate', '').strip()
            thematic = row.get('thematic', '').strip()
            url = row.get('url', '').strip() or 0

            Activity.objects.create(
                start_date=start_date,
                end_date=end_date,
                country=country,
                region=region,
                activity=activity,
                objective=objective,
                directorate=directorate,
                thematic=thematic,
                url=url
            )
            total += 1

    print(f"✅ Successfully imported {total} records.")
