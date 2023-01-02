import glob
import json
import os
import uuid
import boto3
import datetime
import random

from botocore.client import ClientError

def mediaconvert(event, context):

    print(str(event))
    assetID = str(uuid.uuid4())
    
    sourceS3Bucket = event['Records'][0]['s3']['bucket']['name']
    
    sourceS3Key = event['Records'][0]['s3']['object']['key']
    
    sourceS3 = 's3://'+ sourceS3Bucket + '/' + sourceS3Key
    
    print("sourceS3: " + sourceS3)

    sourceS3Basename = os.path.splitext(os.path.basename(sourceS3))[0]
    
    #destinationS3 = 's3://' + os.environ['DestinationBucket']
    
    destinationS3 = event['Records'][0]['s3']['bucket']['name']
    
    destinationS3basename = os.path.splitext(os.path.basename(destinationS3))[0]
    
    mediaConvertRole = os.environ['MEDIACONVERTROLE']
    
    region = os.environ['REGION']
    
    LAMBDA_NAME = os.environ['AWS_LAMBDA_FUNCTION_NAME']
    
    ACCOUNT_ID = os.environ['ACCOUNT_NUMBER']
    
    NameofUploadCustomer=sourceS3Key.split('/')
    
    statusCode = 200
    
    body = {}
    
    # Use MediaConvert SDK UserMetadata to tag jobs with the assetID 
    # Events from MediaConvert will have the assetID in UserMedata
    jobMetadata = {'assetID': assetID}

    
    ######## Publish to SNS #############
    
    ZISSNSTopic='arn:aws:sns:eu-central-1:350474878483:zisnotificationservice'
    
    clientSNS = boto3.client('sns')

    #####################################


    ######################################################################################
    ####    PREREQUISTIS FOR PROCESSING THE MEDIA CONVERT JOB    #########################
    
    # 1) Check if video is in an Upload folder. The Customerfolder initial check comes from S3 trigger
    
    if sourceS3Key.find('Upload') != -1:
        CHECKUPLOADFOLDEROK = True
    else:
        CHECKUPLOADFOLDEROK = False
        returnfoldercheckstatement = sourceS3Key+' was not uploaded to customers Upload folder'
        
        message = {
            'AWS_Account_ID': ACCOUNT_ID,
            'Source': LAMBDA_NAME,
            'CustomerName': NameofUploadCustomer[1],
            'Error': 'UPLOAD_FOLDER_NOK',
            'Error Message': returnfoldercheckstatement
        }
        
        # Pulish to ZIS SNS Topic
        response = clientSNS.publish(
            TargetArn=ZISSNSTopic,
            Message=json.dumps(message)
        )
        
        return returnfoldercheckstatement
        sys.exit
        
    print(CHECKUPLOADFOLDEROK)
    
    # 2) Check if the filesize is less than FILESIZEMAXBYTES (default 5GB = 5000000000)
    
    FILESIZEMAXBYTES = 5000000000
    FILESIZEOK = 'notdefined'
    
    object_key_ul_file = sourceS3Key
    print(object_key_ul_file)
   
    bucket = sourceS3Bucket
    key = object_key_ul_file
    
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket = bucket, Key = key)
    
    size = response['ContentLength']
    print(size)
    
    if size <= FILESIZEMAXBYTES:
        FILESIZEOK = True
    else:
        FILESIZEOK = False
        returnsizestatement = object_key_ul_file+' is too big, max '+str(FILESIZEMAXBYTES)+' Bytes allowed'
        
        message = {
            'AWS_Account_ID': ACCOUNT_ID,
            'Source': LAMBDA_NAME,
            'CustomerName': NameofUploadCustomer[1],
            'Error': 'FILESIZE_NOK',
            'Error Message': returnsizestatement
        }
        
        # Pulish to ZIS SNS Topic
        response = clientSNS.publish(
            TargetArn=ZISSNSTopic,
            Message=json.dumps(message)
        )

        return returnsizestatement
        sys.exit
      
    print(FILESIZEOK) 
    
    
    ################################
    ################################
    
    
    #get folder from event, cut off after last "/""
    S3CustomerUploadFolder=sourceS3Key[0:sourceS3Key.rfind("/")]
    
    # replace Upload with Configuration folder 
    S3CustomerConfigFolder=S3CustomerUploadFolder.replace("Upload","Configuration")
    print(S3CustomerConfigFolder)
    
    S3CustomerCfgJSON=sourceS3Key[0:sourceS3Key.rfind("/")]+'/job.json'
  
    
    ##### Read from Customer Configuration JSON file
    
    object_key = (S3CustomerConfigFolder+'/job.json') # replace object key
    # print(object_key)
   
    bucket = sourceS3Bucket
    key = object_key
    
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket = bucket, Key = key)
    content = response['Body']
    jsonObject = json.loads(content.read())
    print(jsonObject)
    

    try:
        # Job settings are in the lambda zip file in the current working directory
        #with open('job.json') as json_data:
            #jobSettings = json.load(json_data)
        jobSettings = jsonObject

        # get the account-specific mediaconvert endpoint for this region
        mc_client = boto3.client('mediaconvert', region_name=region)
        endpoints = mc_client.describe_endpoints()

        # add the account-specific endpoint to the client session 
        client = boto3.client('mediaconvert', region_name=region, endpoint_url=endpoints['Endpoints'][0]['Url'], verify=False)

        # Update the job settings with the source video from the S3 event and destination 
        # paths for converted videos
        
        jobSettings['Inputs'][0]['FileInput'] = sourceS3
        
        #S3KeyHLS = assetID + "" + sourceS3Basename
        #jobSettings['OutputGroups'][0]['OutputGroupSettings']['HlsGroupSettings']['Destination'] \
        #    = destinationS3 + '/' + S3KeyHLS
        #
        #jobSettings['OutputGroups'][0]['OutputGroupSettings']['HlsGroupSettings']['Destination'] \
        #    = destinationS3
        
         
        #S3KeyWatermark = assetID + "" + sourceS3Basename
        #jobSettings['OutputGroups'][1]['OutputGroupSettings']['FileGroupSettings']['Destination'] \
        #    = destinationS3 + '/' + S3KeyWatermark
        #
        #
        #S3KeyThumbnails = assetID + "" + sourceS3Basename
        #jobSettings['OutputGroups'][2]['OutputGroupSettings']['FileGroupSettings']['Destination'] \
        #    = destinationS3 + '/' + S3KeyThumbnails     
        
        print('jobSettings:')
        print(json.dumps(jobSettings))

        # Convert the video using AWS Elemental MediaConvert
        job = client.create_job(Role=mediaConvertRole, UserMetadata=jobMetadata, Settings=jobSettings)
        print (json.dumps(job, default=str))

    except Exception as e:
        print ('Exception: %s' % e)
        statusCode = 500
        raise

    finally:
        
        message = {
            'AWS_Account_ID': ACCOUNT_ID,
            'Source': LAMBDA_NAME,
            'CustomerName': NameofUploadCustomer[1],
            'Error': 'NO',
        }
        
        # Pulish to ZIS SNS Topic
        response = clientSNS.publish(
            TargetArn=ZISSNSTopic,
            Message=json.dumps(message)
        )
        
        return {
            'statusCode': statusCode,
            'body': json.dumps(body),
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        }