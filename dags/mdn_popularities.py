import datetime

from airflow import DAG
from airflow.providers.google.cloud.transfers.bigquery_to_gcs import BigQueryToGCSOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryDeleteTableOperator

from dags.utils.gcp import bigquery_etl_query
from utils.tags import Tag


DOCS = """\
Monthly data exports of MDN 'Popularities'. This aggregates and counts total \
page visits and normalizes them agains the max.
"""

# PROJECT_ID = "moz-fx-data-shared-prod"
PROJECT_ID = "mozdata"
DATASET_ID = "mdn_yari_derived"
TABLE_ID = "mdn_popularities_v1"

# MDN_PROJECT_ID = "moz-fx-dev-gsleigh-migration"
# MDN_BUCKET = "gs://mdn-gcp/"  # This bucket lives in moz-fx-dev-gsleigh-migration (Will later live in mdn-prod)
DESTINATION_PROJECT_ID = PROJECT_ID
DESTINATION_DATASET_ID = "tmp"
DESTINATION_BUCKET = "gs://mozdata-tmp"
DESTINATION_GCS_PATH = "mdn-dev/popularities/current"

DEFAULT_ARGS = {
    "owner": "fmerz@mozilla.com",
    "start_date": datetime.datetime(2023, 2, 1),
    "email": ["telemetry-alerts@mozilla.com", "mdn@mozilla.com"],
    "email_on_failure": True,
    "retries": 1,
    "retry_delay": datetime.timedelta(minutes=5),
}
TAGS = [Tag.ImpactTier.tier_3, "repo/telemetry-airflow", Tag.Triage.record_only]

DAG_ID = "mdn_popularities"

with DAG(
    DAG_ID,
    schedule_interval="@monthly",
    doc_md=DOCS,
    default_args=DEFAULT_ARGS,
    tags=TAGS,
) as dag:

    etl_query = bigquery_etl_query(
        task_id=f"{DAG_ID}_create_temp_table",
        project_id=DESTINATION_PROJECT_ID,
        dataset_id=DESTINATION_DATASET_ID,
        destination_table=TABLE_ID,
        date_partition_parameter=None,
        arguments=("--replace",),
        parameters=("submission_date:DATE:{{ds}}",),
        sql_file_path=f"sql/{PROJECT_ID}/{DATASET_ID}/{TABLE_ID}/query.sql",
        # TODO: remove the below before deploying to prod
        gcp_conn_id="google_cloud_gke_sandbox",
        gke_project_id="moz-fx-data-gke-sandbox",
        gke_cluster_name="kignasiak-gke-sandbox",
    )

    bq2gcs = BigQueryToGCSOperator(
        task_id=f"{DAG_ID}_temp_table_to_gcs",
        source_project_dataset_table=f"{DESTINATION_PROJECT_ID}.{DESTINATION_DATASET_ID}.{TABLE_ID}",
        destination_cloud_storage_uris=f"gs://{DESTINATION_BUCKET}/{DESTINATION_GCS_PATH}/{{{{ execution_date.strftime('%m-%Y') }}}}.json",
        export_format="JSON",
        print_header=False,
    )

etl_query >> bq2gcs
