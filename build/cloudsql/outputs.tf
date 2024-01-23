
output "id" {
  description = "Endereço IP Publico do Banco"
  value       = google_sql_database_instance.mysql_instance.public_ip_address
}