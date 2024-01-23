resource "google_pubsub_topic" "pubsub-stream" {
  name = "pubsub-stream"
  message_retention_duration = "604800s"
}

resource "google_storage_bucket" "stream-cdc" {
  name          = "stream-cdc-breno-account"
  location      = "EU"
  force_destroy = true
  storage_class = "STANDARD"
}

data "google_storage_project_service_account" "gcs_account" {
}

resource "google_pubsub_topic_iam_binding" "permission" {
  topic   = google_pubsub_topic.pubsub-stream.id
  role    = "roles/pubsub.publisher"
  members = ["serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"]
  depends_on = [google_pubsub_topic.pubsub-stream, google_storage_bucket.stream-cdc]
}

resource "google_storage_notification" "notification-pubsub-stream" {
  bucket         = google_storage_bucket.stream-cdc.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.pubsub-stream.id
  event_types    = ["OBJECT_FINALIZE"]
  depends_on = [google_pubsub_topic.pubsub-stream, google_storage_bucket.stream-cdc, google_pubsub_topic_iam_binding.permission ]
}


data "google_secret_manager_secret_version" "mysql_credentials" {
 secret   = "mysql-creds"
}

locals {
creds = jsondecode(data.google_secret_manager_secret_version.mysql_credentials.secret_data)
}

resource "google_datastream_connection_profile" "source_connection_profile" {
    display_name          = "cdc-mysql"
    connection_profile_id = "cdc-mysql"
    location              = "us-central1"

    mysql_profile {
        hostname = local.creds.host
        username = local.creds.user 
        password = local.creds.password
    }
}

resource "google_datastream_connection_profile" "destination_connection_profile" {
    display_name          = "cdc-cloud-storage"
    location              = "us-central1"
    connection_profile_id = "cdc-cloud-storage"

    gcs_profile {
        bucket    = google_storage_bucket.stream-cdc.name
        root_path = "/cdc-stream"
    }
    depends_on = [google_storage_bucket.stream-cdc ]
}



resource "google_storage_bucket" "data-stream-storage" {
  name          = "data-flow-files-breno-account"
  location      = "US"
  force_destroy = true
  storage_class = "STANDARD"
}

# resource "google_storage_bucket_object" "data-stream-storage-bucket" {
#  name         = "dataflow-cdc-stream.py"
#  source       = "../src/dataflow-cdc-stream.py"
#  bucket       = google_storage_bucket.data-stream-storage.id
#      depends_on = [
#         google_storage_bucket.data-stream-storage
#     ]
# }

resource "google_storage_bucket_object" "schema-json" {
 name         = "data-stream.json"
 source       = "../src/data-stream.json"
 bucket       = google_storage_bucket.data-stream-storage.id
     depends_on = [
        google_storage_bucket.data-stream-storage
    ]
}

resource "google_dataflow_job" "big_data_job" {
  name              = "dataflow-cdc-stream"
  template_gcs_path = "gs://data-flow-files-breno-account/templates/dataflow-cdc-stream.json"
  temp_gcs_location = "gs://${google_storage_bucket.data-stream-storage.name}/tmp_dir"
  depends_on = [ google_storage_bucket_object.data-stream-storage-bucket, 
                 google_storage_bucket_object.schema-json,
                 google_storage_bucket_object.data-stream-storage-bucket
  ]

  parameters = {
    pubsub_topic = google_pubsub_topic.pubsub-stream.id 
    region = var.region  
    staging_location = "gs://${google_storage_bucket.data-stream-storage.name}/stage_fold" 
    temp_location = "gs://${google_storage_bucket.data-stream-storage.name}/temp_fold" 
    temp_fold_script = "gs://${google_storage_bucket.data-stream-storage.name}/temp_fold"  
    project_id = var.project_id 
    bucket_name_schema = google_storage_bucket.data-stream-storage.name  
    source_schema_path = google_storage_bucket_object.schema-json.name  
    runner = "DataflowRunner"
  }

}

resource "google_datastream_stream" "cdc-data-stream" {
    depends_on = [
        google_datastream_connection_profile.source_connection_profile,
        google_datastream_connection_profile.destination_connection_profile,
        google_dataflow_job.big_data_job
    ]
    stream_id = "cdc-data-stream-v2"
    display_name = "my stream"
    location = "us-central1"
    desired_state = "NOT_STARTED"

    source_config {
        source_connection_profile = google_datastream_connection_profile.source_connection_profile.id
        mysql_source_config {
            include_objects {
                mysql_databases {
                    database = "olist"
                    mysql_tables {
                        table = "users"
                    }
                }
                mysql_databases {
                    database = "olist"
                    mysql_tables {
                        table = "produtos"
                    }
                }
            }
        }
    }
    destination_config {
        destination_connection_profile = google_datastream_connection_profile.destination_connection_profile.id
        gcs_destination_config {
            path = "cdc-stream"
            json_file_format {
                schema_file_format = "NO_SCHEMA_FILE"
                compression = "GZIP"
            }
        }
    }

    backfill_all {
    }
}