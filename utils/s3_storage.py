import boto3
import os
from config import Config

s3 = boto3.client(
    's3',
    aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    region_name=Config.AWS_S3_REGION
)

def upload_to_s3(file_path, object_name):
    try:
        s3.upload_file(file_path, Config.AWS_S3_BUCKET, object_name)
        return f"https://{Config.AWS_S3_BUCKET}.s3.{Config.AWS_S3_REGION}.amazonaws.com/{object_name}"
    except Exception as e:
        print(f"S3 Upload Error: {e}")
        return None