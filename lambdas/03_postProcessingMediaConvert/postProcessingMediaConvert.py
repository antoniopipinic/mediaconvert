import boto3
import botocore
import os

def lambda_handler(event, context):
    s3 = boto3.resource('s3')
    KEY = event['Records'][0]['s3']['object']['key']
    s3BUCKET = event['Records'][0]['s3']['bucket']['name']
    FILE = KEY.rsplit('/', 1)[-1]
    PATH = KEY.rsplit('/', 2)[0]

    try:
        s3.Bucket(s3BUCKET).download_file(KEY, '/tmp/' + FILE)
        os.system('ffmpeg_binary/ffmpeg -flags +genpts -i /tmp/' + FILE + ' -c copy ' + '/tmp/' + FILE[:-3] + '_final.ts')
        s3.meta.client.upload_file('/tmp/' + FILE[:-3] + '_final.ts' , s3BUCKET, PATH + "/Download/" + FILE[:-3] + '_final.ts')

    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            print("The object does not exist.")
        else:
            raise