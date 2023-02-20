import datetime

from airflow import DAG
from airflow.providers.google.cloud.transfers.bigquery_to_gcs import BigQueryToGCSOperator
from dags.utils.gcp import bigquery_etl_query

from utils.tags import Tag


DOCS = """\
Monthly data exports of MDN 'Popularities'. This aggregates and counts total page visits and normalizes them agains the max. 
"""

default_args = {
    "owner": "fmerz@mozilla.com",
    "start_date": datetime.datetime(2023, 3, 1),
    "email": ["telemetry-alerts@mozilla.com", "mdn@mozilla.com"],
    "email_on_failure": True,
    "email_on_retry": True,
    "depends_on_past": False,
    # If a task fails, retry it once after waiting at least 5 minutes
    "retries": 1,
    "retry_delay": datetime.timedelta(minutes=5),
}

project_id = "moz-fx-data-shared-prod"
dataset_id = "mdn-dataset"  # ?TODO
dag_name = "mdn_popularities"
tags = [Tag.ImpactTier.tier_3]
bucket = "gs://mdn-gcp/"  # This bucket lives in moz-fx-dev-gsleigh-migration (Will later live in mdn-prod)
gcp_conn_id = "TODO"

with DAG(
    dag_name, schedule_interval="0 0 1 * *", doc_md=DOCS, default_args=default_args, tags=tags,
) as dag:

    bq_extract_table = "mdn_popularities_v1"
    etl_query = bigquery_etl_query(
        task_id="mdn_popularities_extract",
        destination_table=bq_extract_table,
        dataset_id=dataset_id,
        project_id=project_id,
        date_partition_parameter=None,
        arguments=("--replace",),
        # TODO , correct file path? 
        sql_file_path="sql/moz-fx-data-shared-prod/{}/query.sql".format(
            dataset_id
        ),
        dag=dag,
    )

    gcs_destination = "gs://{bucket}/popularities/current/{date}.json".format(
        bucket=bucket, date=datetime.date.today().strftime("%m-%Y")
    )

    bq2gcs = BigQueryToGCSOperator(
        task_id="mdn_popularities_to_gcs",
        source_project_dataset_table="{}.{}.{}".format(
            project_id, dataset_id, bq_extract_table
        ),
        destination_cloud_storage_uris=gcs_destination,
        gcp_conn_id=gcp_conn_id,
        export_format="JSON",
        print_header=False,
        dag=dag,
    )
