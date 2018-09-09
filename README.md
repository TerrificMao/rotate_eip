##Rotate EIP

A Lambda function for rotating EIP of EC2 instance and 
update public DNS to Route 53 to a specified DNS name.

####Permissions
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "ec2:ReleaseAddress",
                "ec2:DisassociateAddress",
                "ec2:DescribeInstances",
                "ec2:DescribeAddresses",
                "sns:Publish",
                "ec2:AssociateAddress",
                "ec2:AllocateAddress"
            ],
            "Resource": "*"
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": "route53:ChangeResourceRecordSets",
            "Resource": "arn:aws:route53:::hostedzone/*"
        }
    ]
}
```

####Lambda Environment variables
* INSTANCE_ID
* HOSTED_ZONE_ID
* DNS_NAME
* SNS_TOPIC