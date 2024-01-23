resource "google_project_service" "project" {
  project = var.project_id
  service = "sqladmin.googleapis.com"

  disable_dependent_services = true
}

resource "google_sql_database_instance" "mysql_instance" {
    name    = "mysql-db-olist"
    database_version = "MYSQL_8_0"
    deletion_protection = false
      depends_on = [google_project_service.project]
    settings {
      tier = "db-g1-small"
      availability_type = "ZONAL"
      disk_autoresize = true 
      disk_size = 10
      disk_type = "PD_SSD"
      backup_configuration {
        enabled = true
        binary_log_enabled = true
        transaction_log_retention_days = 7
      }
      ip_configuration {
        ipv4_enabled = true
      }
  }
}



resource "google_sql_user" "mysql_user" {
    name = "mysqluser"
    instance = google_sql_database_instance.mysql_instance.name

    depends_on = [google_sql_database_instance.mysql_instance]
    host = "191.5.85.24"
    password = var.database_password
}

