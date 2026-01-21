
import json
from datetime import datetime
from botocore.exceptions import ClientError

import boto3

class AWSAutomation:
   

    def __init__(self, region='us-east-1'):
        """Initialize AWS clients for different services."""
        self.region = region
        self.ec2 = boto3.client('ec2', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.iam = boto3.client('iam')
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.sns = boto3.client('sns', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.rds = boto3.client('rds', region_name=region)

    # EC2 AUTOMATION

    def create_ec2_instance(self, instance_name, instance_type='t2.micro'):
        """Create and tag an EC2 instance."""
        try:
            # Get latest Amazon Linux 2 AMI
            images = self.ec2.describe_images(
                Owners=['amazon'],
                Filters=[
                    {'Name': 'name', 'Values': ['amzn2-ami-hvm-*-x86_64-gp2']},
                    {'Name': 'state', 'Values': ['available']}
                ]
            )
            latest_ami = sorted(
                images['Images'],
                key=lambda x: x['CreationDate'],
                reverse=True
            )[0]['ImageId']

            response = self.ec2.run_instances(
                ImageId=latest_ami,
                InstanceType=instance_type,
                MinCount=1,
                MaxCount=1,
                TagSpecifications=[{
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Name', 'Value': instance_name},
                        {'Key': 'Environment', 'Value': 'Development'},
                        {'Key': 'ManagedBy', 'Value': 'Boto3Automation'}
                    ]
                }]
            )
            instance_id = response['Instances'][0]['InstanceId']
            print(f"Created EC2 instance: {instance_id}")
            return instance_id
        except ClientError as e:
            print(f"EC2 Error: {e}")
            return None
    
    def list_ec2_instances(self):
        """List all EC2 instances with their status."""
        try:
            response = self.ec2.describe_instances()
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instances.append({
                        'InstanceId': instance['InstanceId'],
                        'State': instance['State']['Name'],
                        'Type': instance['InstanceType']
                    })
            print(f"Found {len(instances)} EC2 instances")
            return instances
        except ClientError as e:
            print(f"Error listing instances: {e}")
            return []

    def stop_instance(self, instance_id):
        """Stop an EC2 instance."""
        try:
            self.ec2.stop_instances(InstanceIds=[instance_id])
            print(f"Stopped instance: {instance_id}")
            return True
        except ClientError as e:
            print(f"Error stopping instance: {e}")
            return False

    # S3 AUTOMATION
    def create_s3_bucket(self, bucket_name):
        """Create an S3 bucket with versioning and encryption enabled."""
        try:
            if self.region == 'us-east-1':
                self.s3.create_bucket(Bucket=bucket_name)
            else:
                self.s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )

            # Enable versioning
            self.s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )

            # Add encryption
            self.s3.put_bucket_encryption(
                Bucket=bucket_name,
                ServerSideEncryptionConfiguration={
                    'Rules': [{'ApplyServerSideEncryptionByDefault':
                              {'SSEAlgorithm': 'AES256'}}]
                }
            )
            print(f"Created S3 bucket: {bucket_name}")
            return True
        except ClientError as e:
            print(f"S3 Error: {e}")
            return False

    def upload_to_s3(self, bucket_name, file_name, content):
        """Upload content to S3 bucket."""
        try:
            self.s3.put_object(
                Bucket=bucket_name,
                Key=file_name,
                Body=content,
                ServerSideEncryption='AES256'
            )
            print(f"Uploaded {file_name} to {bucket_name}")
            return True
        except ClientError as e:
            print(f"Upload Error: {e}")
            return False

    def list_s3_objects(self, bucket_name):
        """List all objects in an S3 bucket."""
        try:
            response = self.s3.list_objects_v2(Bucket=bucket_name)
            objects = response.get('Contents', [])
            print(f"Found {len(objects)} objects in {bucket_name}")
            return [obj['Key'] for obj in objects]
        except ClientError as e:
            print(f"Error listing objects: {e}")
            return []

    # IAM AUTOMATION
    def create_iam_role(self, role_name, service='lambda.amazonaws.com'):
        """Create an IAM role for AWS services."""
        try:
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": service},
                    "Action": "sts:AssumeRole"
                }]
            }

            response = self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='Role created by boto3 automation'
            )
            print(f"Created IAM role: {role_name}")
            return response['Role']['Arn']
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                print(f"Role {role_name} already exists")
                response = self.iam.get_role(RoleName=role_name)
                return response['Role']['Arn']
            print(f"IAM Error: {e}")
            return None

    # SNS AUTOMATION
    def create_sns_topic(self, topic_name):
        """Create an SNS topic for notifications."""
        try:
            response = self.sns.create_topic(Name=topic_name)
            topic_arn = response['TopicArn']
            print(f"Created SNS topic: {topic_name}")
            return topic_arn
        except ClientError as e:
            print(f"SNS Error: {e}")
            return None

    def subscribe_email_to_topic(self, topic_arn, email):
        """Subscribe an email to SNS topic."""
        try:
            self.sns.subscribe(
                TopicArn=topic_arn,
                Protocol='email',
                Endpoint=email
            )
            print(f"Subscribed {email} to topic (check email to confirm)")
            return True
        except ClientError as e:
            print(f"Subscription Error: {e}")
            return False

    # CLOUDWATCH AUTOMATION
    def create_cloudwatch_alarm(self, alarm_name, instance_id, sns_topic_arn):
        """Create a CloudWatch alarm for EC2 CPU utilization."""
        try:
            self.cloudwatch.put_metric_alarm(
                AlarmName=alarm_name,
                ComparisonOperator='GreaterThanThreshold',
                EvaluationPeriods=2,
                MetricName='CPUUtilization',
                Namespace='AWS/EC2',
                Period=300,
                Statistic='Average',
                Threshold=80.0,
                ActionsEnabled=True,
                AlarmActions=[sns_topic_arn],
                AlarmDescription='Alert when CPU exceeds 80%',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}]
            )
            print(f"Created CloudWatch alarm: {alarm_name}")
            return True
        except ClientError as e:
            print(f"CloudWatch Error: {e}")
            return False

    # RDS AUTOMATION
    def create_rds_snapshot(self, db_instance_id, snapshot_id):
        """Create a snapshot of RDS instance."""
        try:
            response = self.rds.create_db_snapshot(
                DBSnapshotIdentifier=snapshot_id,
                DBInstanceIdentifier=db_instance_id
            )
            print(f"Creating RDS snapshot: {snapshot_id}")
            return snapshot_id
        except ClientError as e:
            print(f"RDS Error: {e}")
            return None

    # CLEANUP AUTOMATION

    def cleanup_resources(self, bucket_name=None, instance_id=None):
        """Clean up created resources."""
        print("\nStarting cleanup...")

        if instance_id:
            try:
                self.ec2.terminate_instances(InstanceIds=[instance_id])
                print(f"Terminated instance: {instance_id}")
            except ClientError as e:
                print(f"Cleanup Error: {e}")

        if bucket_name:
            try:
                # Delete all objects first
                objects = self.s3.list_objects_v2(Bucket=bucket_name)
                if 'Contents' in objects:
                    for obj in objects['Contents']:
                        self.s3.delete_object(Bucket=bucket_name, Key=obj['Key'])
                self.s3.delete_bucket(Bucket=bucket_name)
                print(f"Deleted bucket: {bucket_name}")
            except ClientError as e:
                print(f"Cleanup Error: {e}")


def main():
    """Main execution flow demonstrating all automation capabilities."""
    print("=" * 60)
    print("AWS AUTOMATION PROJECT - BOTO3 DEMONSTRATION")
    print("=" * 60)

    # Initialize automation
    aws = AWSAutomation(region='us-east-1')

    # Generate unique names with timestamp
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    bucket_name = f'boto3-demo-bucket-{timestamp}'
    instance_name = f'boto3-demo-instance-{timestamp}'
    topic_name = f'boto3-demo-topic-{timestamp}'

    # 1. EC2 Operations
    print("\nEC2 AUTOMATION")
    print("-" * 60)
    instance_id = aws.create_ec2_instance(instance_name)
    aws.list_ec2_instances()

    # 2. S3 Operations
    print("\nS3 AUTOMATION")
    print("-" * 60)
    aws.create_s3_bucket(bucket_name)
    aws.upload_to_s3(bucket_name, 'demo.txt', 'Hello from boto3!')
    aws.upload_to_s3(
        bucket_name,
        'data.json',
        json.dumps({'status': 'active', 'timestamp': timestamp})
    )
    aws.list_s3_objects(bucket_name)

    # 3. IAM Operations
    print("\nIAM AUTOMATION")
    print("-" * 60)
    role_arn = aws.create_iam_role(f'boto3-demo-role-{timestamp}')

    # 4. SNS Operations
    print("\nSNS AUTOMATION")
    print("-" * 60)
    topic_arn = aws.create_sns_topic(topic_name)

    # 5. CloudWatch Operations
    print("\nCLOUDWATCH AUTOMATION")
    print("-" * 60)
    if instance_id and topic_arn:
        aws.create_cloudwatch_alarm(
            f'high-cpu-{timestamp}',
            instance_id,
            topic_arn
        )

    print("\n" + "=" * 60)
    print("AUTOMATION COMPLETE!")
    print("=" * 60)
    print(f"\nCreated Resources:")
    print(f"  - EC2 Instance: {instance_id}")
    print(f"  - S3 Bucket: {bucket_name}")
    print(f"  - SNS Topic: {topic_arn}")
    print(f"\nRemember to run cleanup to avoid charges!")

    # Uncomment to auto-cleanup (wait for resources to initialize first)
    # time.sleep(5)
    # aws.cleanup_resources(bucket_name, instance_id)


if __name__ == "__main__":
    main()