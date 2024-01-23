import apache_beam as beam
from apache_beam.transforms.trigger import AfterWatermark, AfterProcessingTime, AccumulationMode, AfterCount, Repeatedly
from apache_beam.options import pipeline_options
from apache_beam.options.pipeline_options import GoogleCloudOptions

from google.cloud import storage
from apache_beam import window
from datetime import datetime as dt
from apache_beam. runners import DataflowRunner
import json
from google.cloud import storage
import logging
import argparse
  
class ProcessMessage(beam.DoFn):
    '''A transform function to process messages.'''
    def process(self, message):
        '''
        Processes a message from Pub/Sub.
        Args:
            element (dict): A dictionary representing a Pub/Sub message.
        Yields:
            str: The processed file path.
        '''
        try:
            path = message.get('name')
            bucket = message.get('bucket')
            file_path = f"gs://{bucket}/{path}"
            yield file_path 
        except Exception as e:
            raise Exception(e)
            
class ProcessCloudStorage(beam.DoFn):
    '''A transform function to process log data from Cloud Storage.'''
    def __init__(self, project_id, bucket_name_schema, source_schema_path, options, temp_fold_script):
        '''
        Initializes the ProcessCloudStorage transform.
        Args:
            project_id (str): Google Cloud Project ID.
            bucket_name_schema (str): Bucket name for JSON schema in Cloud Storage.
            source_schema_path (str): Path for JSON schema in Cloud Storage.
            options (PipelineOptions): Apache Beam PipelineOptions.
            temp_fold_script (str): Temporary folder for script execution.
        '''
        self.project_id = project_id
        self.bucket_name_schema = bucket_name_schema
        self.source_schema_path = source_schema_path
        self.options = options
        self.temp_fold_script = temp_fold_script  
        
    def start_bundle(self):
        '''Starts the processing bundle.'''
        self.storage_client = storage.Client(project=self.project_id)

    def process(self, log):
        '''
        Processes a log entry from Cloud Storage.
        Args:
            element (str): A string representing a log entry.
        Raises:
            Exception: If an error occurs during processing.
        '''
        try:
            json_data = json.loads(log)
            json_line = json_data['payload'] 
            json_line ['action'] = json_data['source_metadata']['change_type']
            json_line ['update_date'] = json_data['source_timestamp']
            json_line = {key: value for key, value in json_line.items() if value is not None}
            object_name = json_data['object']
            
            bucket = self.storage_client.bucket(self.bucket_name_schema)
            blob = bucket.blob(self.source_schema_path)
            json_content = blob.download_as_text()
            json_data = json.loads(json_content)
        
            dict_table = json_data.get(object_name)
            
            if dict_table is not None:
                json_schema = dict_table['schema']
                table = dict_table['table_name']
                       
                p1 = beam.Pipeline(options=self.options)
                part1 = (
                p1 
                 | "criando um pcollection a partir do dicionario json_line" >> beam.Create([json_line])
                 | "Write to Big Query" >> beam.io.WriteToBigQuery(
                table=table,
                schema= json_schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                custom_gcs_temp_location=self.temp_fold_script 
                )
                ) 
                p1.run()
            
            else:
                print(f"The '{object_name}' not mapped on json schema ")

        except Exception as e:
            raise Exception(e)
                
def run(
    pubsub_topic,
    region, 
    staging_location, 
    temp_location, 
    temp_fold_script, 
    project_id, 
    bucket_name_schema, 
    source_schema_path,
    pipeline_args=None):
    ''' 
    Runs the Beam pipeline.
    Args:
        pubsub_topic (str): Pub/Sub topic name.
        region (str): Region for Dataflow job.
        staging_location (str): GCS staging location for Dataflow job.
        temp_location (str): GCS temp location for Dataflow job.
        temp_fold_script (str): Temporary folder for script execution.
        project_id (str): Google Cloud Project ID.
        bucket_name_schema (str): Bucket name for JSON schema in Cloud Storage.
        source_schema_path (str): Path for JSON schema in Cloud Storage.
        pipeline_args (List[str], optional): Additional command-line arguments.

    Raises:
        Exception: If an error occurs during pipeline execution.
    '''
    
    options = pipeline_options.PipelineOptions(pipeline_args, streaming=True, save_main_session=True)

    options.view_as (GoogleCloudOptions).region = region
    options.view_as(GoogleCloudOptions).staging_location = staging_location
    options.view_as(GoogleCloudOptions).temp_location = temp_location

    with beam.Pipeline(options=options) as p:
        (
         p  
            | "Read Events stream data from Topic" >> beam.io.ReadFromPubSub(topic=pubsub_topic)
            | "Convert from Bytes to String" >> beam.Map(lambda s: s.decode("utf-8"))
            | "Parse JSON" >> beam.Map(json.loads)
            | "Process Message" >> beam.ParDo(ProcessMessage())
            | "Read file" >> beam.io.ReadAllFromText()
            | "Process Log from Cloud Storage" >> beam.ParDo(ProcessCloudStorage(
                project_id = project_id,
                bucket_name_schema = bucket_name_schema,
                source_schema_path = source_schema_path,
                options = options,
                temp_fold_script = temp_fold_script
            ))
        )   
    
if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)

    parser = argparse.ArgumentParser()    
    parser.add_argument('--pubsub_topic', required=True )
    parser.add_argument('--region', required=True )
    parser.add_argument('--staging_location', required=True )
    parser.add_argument('--temp_location', required=True )
    parser.add_argument('--temp_fold_script', required=True )
    parser.add_argument('--project_id', required=True )
    parser.add_argument('--bucket_name_schema', required=True ) 
    parser.add_argument('--source_schema_path', required=True ) 

    known_args, pipeline_args = parser.parse_known_args()

    run(
        pubsub_topic= known_args.pubsub_topic,
        region = known_args.region,
        staging_location = known_args.staging_location,
        temp_location = known_args.temp_location,
        temp_fold_script =known_args.temp_fold_script,
        project_id = known_args.project_id,
        bucket_name_schema = known_args.bucket_name_schema,
        source_schema_path = known_args.source_schema_path,
        pipeline_args = pipeline_args
    )