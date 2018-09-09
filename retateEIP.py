########################################################################
# AWS Lambda function
# Description: Rotate EIP for EC2 instance and update Route53 record.
########################################################################
import boto3
import logging
import os
import json
from botocore.exceptions import ClientError


logger = logging.getLogger()
logger.setLevel(logging.INFO)

session = boto3.session.Session()
ec2 = session.client('ec2')
route53 = session.client('route53')


def lambda_handler(event, context):
    if os.environ['INSTANCE_ID']:
        instance_id = os.environ['INSTANCE_ID']
    else:
        logger.error('Cannot get INSTANCE_ID from ENV.')
        return 1
    if os.environ['HOSTED_ZONE_ID']:
        hosted_zone_id = os.environ['HOSTED_ZONE_ID']
    else:
        logger.error('Cannot get HOSTED_ZONE_ID from ENV.')
        return 1
    if os.environ['DNS_NAME']:
        dns_name = os.environ['DNS_NAME']
    else:
        logger.error('Cannot get DNS_NAME from ENV.')
        return 1

    # Get EIP
    association = get_association(instance_id)
    if association and 'PublicIp' in association:
        public_ip = association['PublicIp']
        logger.info('{} current public IP: {}'.format(instance_id, public_ip))

        # disassociate and release EIP
        try:
            addresses = ec2.describe_addresses(PublicIps=[public_ip, ])
            if len(addresses['Addresses']) == 1:
                address = addresses['Addresses'][0]
                if 'AssociationId' in addresses['Addresses'][0]:
                    association_id = address['AssociationId']
                    logger.info('Association Id: {}'.format(association_id))

                    logger.info('Disassociate {}'.format(public_ip))
                    ec2.disassociate_address(AssociationId=association_id)

                if 'AllocationId' in address:
                    allocation_id = address['AllocationId']
                    logger.info('Release {}'.format(public_ip))
                    ec2.release_address(AllocationId=allocation_id)
        except ClientError as e:
            logger.error(e)

    # Allocate new EIP
    address = ec2.allocate_address(Domain='vpc')
    allocation_id = address['AllocationId']
    public_ip = address['PublicIp']
    logger.info('Allocate new EIP: {}'.format(public_ip))

    # Associate EIP to instance
    logger.info('Associate EIP {} to instance {}'.format(public_ip,
                                                         instance_id))
    ec2.associate_address(
            AllocationId=allocation_id,
            InstanceId=instance_id,
    )

    # Get public DNS name
    association = get_association(instance_id)
    if association and 'PublicDnsName' in association:
        public_dns_name = association['PublicDnsName']

        # Update Route 53 record
        logger.info('Updating {} => {}'.format(dns_name, public_dns_name))
        route53.change_resource_record_sets(
                HostedZoneId=hosted_zone_id,
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'UPSERT',
                            'ResourceRecordSet': {
                                'Name': dns_name,
                                'Type': 'CNAME',
                                'TTL': 60,
                                'ResourceRecords': [
                                    {
                                        'Value': public_dns_name
                                    },
                                ],
                            }
                        },
                    ]
                }
        )

        logger.info('{} has been updated to {}'.format(dns_name,
                                                       public_dns_name))

    logger.info('Rotation done.')

    # Send SNS notificatin
    if os.environ['SNS_TOPIC']:
        sns = session.client('sns')
        sns_topic = os.environ['SNS_TOPIC']
        subject = '{} has been updated'.format(dns_name)
        message = '{} => {}\n'.format(dns_name, public_dns_name)

        sns.publish(
                TopicArn=sns_topic,
                Subject=subject,
                Message=message,
                MessageStructure='raw'
        )


def get_association(instance_id):
    instances = ec2.describe_instances(InstanceIds=[instance_id, ])
    if len(instances['Reservations']) == 1 and \
            len(instances['Reservations'][0]['Instances']) == 1:
        instance = instances['Reservations'][0]['Instances'][0]

        if len(instance['NetworkInterfaces']) == 1:
            if 'Association' in instance['NetworkInterfaces'][0]:
                return instance['NetworkInterfaces'][0]['Association']
            else:
                logger.info('No EIP attached with {}'.format(instance_id))
        else:
            logger.error('{} ENI with instance {}'.format(
                    len(instance['NetworkInterfaces']),
                    instance_id
            ))

        return None
