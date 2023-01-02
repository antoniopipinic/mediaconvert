import json
import boto3
import logging
import os
import cfnresponse
# Create empty responseData for CloudFormation respnse
responseData = {}

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Inside default lambda_handler...")
    
    print(json.dumps(event, indent=4))
    
    logger.info("Loading variables...")
    try:
        playout = event['ResourceProperties']['playout']
        kunde = event['ResourceProperties']['kunde']
        s3bucket = event['ResourceProperties']['s3bucket']
    except:
        logger.error("Invalid JSON payload has been provided")
        cfnresponse.send(event, context, cfnresponse.FAILED, responseData, "CustomResourcePhysicalID")
        return {
            'statusCode': 500,
            'body': 'Invalid JSON payload'
        }
    
    logger.info("Creating S3 connection")
    try:
        s3 = boto3.client('s3')
    except:
        logger.error("Couldn't connect to S3... Check IAM settings")
        cfnresponse.send(event, context, cfnresponse.FAILED, responseData, "CustomResourcePhysicalID")
        raise
    
    # Create directory structure for newly created user
    logger.info("Creating directory structure for new user")
    try:
        # Change to writable Lambda directory
        currdir=os.getcwd()
        os.chdir('/tmp')
        # Create README.md in user root directory
        with open('README.md', 'w') as file:
            fileContent = f"This is the root directory for user {kunde} of playout {playout}"
            file.write(fileContent)
        s3.upload_file("/tmp/README.md", s3bucket, playout + "/" + kunde + "/README.md")
        logger.info("Created README.md in playout root directory.")

        # Create README.md in user upload directory
        with open('README.md', 'w') as file:
            fileContent = f"This is the Upload directory for user {kunde} of playout {playout}"
            file.write(fileContent)
        s3.upload_file("/tmp/README.md", s3bucket, playout + "/" + kunde + "/Upload/README.md")
        logger.info("Created README.md in playout Upload directory.")

        # Create README.md in user download directory
        with open('README.md', 'w') as file:
            fileContent = f"This is the Download directory for user {kunde} of playout {playout}"
            file.write(fileContent)
        s3.upload_file("/tmp/README.md", s3bucket, playout + "/" + kunde + "/Download/README.md")
        logger.info("Created README.md in playout Download directory.")

        # Create README.md in user PostProcessing directory
        with open('README.md', 'w') as file:
            fileContent = f"This is the PostProcessing directory for user {kunde} of playout {playout}"
            file.write(fileContent)
        s3.upload_file("/tmp/README.md", s3bucket, playout + "/" + kunde + "/PostProcessing/README.md")
        logger.info("Created README.md in playout PostProcessing directory.")

        # Create job.json in user configuration directory
        newDest = "s3://" + s3bucket + "/" + playout + "/" + kunde + "/PostProcessing/"

        # Opening JSON file
        with open('/var/task/jobJson/job_template.json', 'r') as openfile:
            # Reading from json file
            json_object = json.load(openfile)
            json_object['OutputGroups'][0]['OutputGroupSettings']['FileGroupSettings']['Destination'] = newDest

        with open('/tmp/job.json', 'w') as openfileNew:
            json.dump(json_object, openfileNew)

        s3.upload_file("/tmp/job.json", s3bucket, playout + "/" + kunde + "/Configuration/job.json")
        logger.info("Created job.json in playout Configuration directory.")
        
        # Switch back to default Lambda runtime directory
        os.chdir(currdir)

    except:
        logger.error("Error creating directory structure for playout %s", playout)
        cfnresponse.send(event, context, cfnresponse.FAILED, responseData, "CustomResourcePhysicalID")
        raise
    
    # Get current Lifecycle-Policy
    logger.info("Reading current Lifecycle-Policy for bucket %s", s3bucket)
    try:
        s3GetBucketPolicy = s3.get_bucket_lifecycle_configuration(
            Bucket=s3bucket
            )
        existingRule = s3GetBucketPolicy['Rules']
        print(existingRule)
    except:
        logger.error("Error while trying to fetch the current Lifecycle-Policy...")
        cfnresponse.send(event, context, cfnresponse.FAILED, responseData, "CustomResourcePhysicalID")
        raise
    
    # Check if Lifecycle-Policy for newly created user already exists
    for filters in existingRule:
        if filters['ID'] == playout + "/" + kunde + "/Upload":
            error = f"Lifecycle-Policy with ID {playout}/{kunde}/Upload already exists!"
            logger.error(error)
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData, "CustomResourcePhysicalID")
            return {
                'statusCode': 500,
                'body': json.dumps(error)
            }
        if filters['ID'] == playout +"/" + kunde + "/Download":
            error = f"Lifecycle-Policy with ID {playout}/{kunde}/Download already exists!"
            logger.error(error)
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData, "CustomResourcePhysicalID")
            return {
                'statusCode': 500,
                'body': json.dumps(error)
            }
    
    # Append rules for newly created user
    newRule = existingRule
    newRule.append({"Expiration": {"Days": 7},"ID": playout + "/" + kunde + "/Upload","Filter": {"Prefix": playout + "/" + kunde + "/Upload"}, "Status": "Enabled", "NoncurrentVersionExpiration": {"NoncurrentDays": 1}})
    newRule.append({"Expiration": {"Days": 7},"ID": playout + "/" + kunde + "/Download","Filter": {"Prefix": playout + "/" + kunde + "/Download"}, "Status": "Enabled", "NoncurrentVersionExpiration": {"NoncurrentDays": 1}})
    newRule.append({"Expiration": {"Days": 7}, "ID": playout + "/" + kunde + "/PostProcessing","Filter": {"Prefix": playout + "/" + kunde + "/PostProcessing"}, "Status": "Enabled","NoncurrentVersionExpiration": {"NoncurrentDays": 1}})
    newLifeCyclePolicy = { 'Rules': newRule }
    logger.info("Prepared new Lifecycle-Policy:")
    logger.info(newLifeCyclePolicy)
    
    # Replace existing Lifecycle-Policy with new version
    try:
        s3PutBucketPolicy = s3.put_bucket_lifecycle_configuration(
          Bucket=s3bucket,
          LifecycleConfiguration=newLifeCyclePolicy
          )
        logger.info("Uploaded new Lifecycle-Policy...")
    except:
        logger.error("Error while trying to apply the new Lifecycle-Policy...")
        cfnresponse.send(event, context, cfnresponse.FAILED, responseData, "CustomResourcePhysicalID")
        raise
    
    response = f"Existing Lifecycle-Policy extended for user {kunde}"
    cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData, "CustomResourcePhysicalID")

    return {
        'statusCode': 200,
        'body': json.dumps(response)
    }
