#!/usr/bin/python3
# To run PatchInstancdesWithRollBack in all other accounts from automation account
# 1. parse the variables
# 2. Assume role to each of the accounts
# 3. Get filtered inventory by provided tags
# 4. Execute the patch against the filtered inventory
#
# To test locally:
# export AWS_PROFILE=saml
# python AWS-PatchInstancesWithRollBack.py --tags ssm-rhel,dev5 --accounts 23432432

import boto3
import os
import json

def __assume_role(RoleArn, session_name):

    if RoleArn is None:
        return None

    sts_client = boto3.client('sts')
    sts_response = sts_client.assume_role(
            RoleArn=RoleArn,
            RoleSessionName=session_name
        )
    credentials = sts_response['Credentials']

    return credentials

def __ssm_client(RoleArn,session_name,region="ap-southeast-1"):

    credentials = __assume_role(RoleArn,session_name)
    client = boto3.client(
        'ssm',
        region_name=region,
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )
    return client

def __ec2_client(RoleArn,session_name,region="ap-southeast-1"):

    credentials = __assume_role(RoleArn,session_name)
    client = boto3.client(
        'ec2',
        region_name=region,
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )
    return client

def __get_non_patched_instances(RoleArn, AssumeRoleName, InstanceIds):
    ssm_client = __ssm_client(
            RoleArn=RoleArn,
            session_name=AssumeRoleName
        )
    FilteredInstanceIds = []

    # Looping all instances and filter out all patched instances
    nextToken = 1
    while(nextToken):
        if nextToken == 1:
            response = ssm_client.describe_instance_patch_states(
                InstanceIds=InstanceIds,
                MaxResults=50
            )
        else:
            response = ssm_client.describe_instance_patch_states(
                InstanceIds=InstanceIds,
                MaxResults=50,
                NextToken=nextToken
            )
        for instance in response['InstancePatchStates']:
            # Filtered out all Patched instances
            if instance['MissingCount'] > 0:
                FilteredInstanceIds.append(instance['Id'])
        if 'NextToken' in response:
            nextToken = response['NextToken']
        else:
            nextToken = 0

    print("List of Un-Patched instanceIds: {}".format(FilteredInstanceIds))
    return FilteredInstanceIds

def __get_managed_instanceIds(RoleArn, AssumeRoleName):
    ssm_client = __ssm_client(
            RoleArn=RoleArn,
            session_name=AssumeRoleName
        )
    InstanceIds = []

    nextToken = 1
    while(nextToken):
        if nextToken == 1:
            response = ssm_client.get_inventory(
                MaxResults=50
            )
        else:
            response = ssm_client.get_inventory(
                MaxResults=50,
                NextToken=nextToken
            )

        for instance in response['Entities']:
            if 'InstanceStatus' not in instance['Data']['AWS:InstanceInformation']['Content'][0]:
                InstanceIds.append(instance['Id'])
        if 'NextToken' in response:
            nextToken = response['NextToken']
        else:
            nextToken = 0
    
    print("List of active managed instanceIds: {}".format(InstanceIds))
    return InstanceIds

def __apply_patch_tag(RoleArn, InstanceIds, Tags, AssumeRoleName):
    tags_to_patch = []
    ec2_client = __ec2_client(
            RoleArn=RoleArn,
            session_name=AssumeRoleName
        )
    for InstanceId in InstanceIds:
        response = ec2_client.describe_tags(
            Filters=[
                {
                    'Name': 'resource-id',
                    'Values': [
                        InstanceId,
                    ],
                },
            ],
        )

        # TODO - There is a chance for enhancing Big O here
        Instance_tags = []
        for tag in response['Tags']:
            if tag["Key"] == 'Portfolio':
                portfolio = tag["Value"]
            if tag["Key"] == 'App':
                app = tag["Value"]
            if tag["Key"] == 'Branch':
                branch = tag["Value"]
            if tag["Key"] == 'Build':
                build = tag["Value"]
            Instance_tags.append(tag["Value"])

        toAdd = True
        for Tag in Tags:
            if Tag not in Instance_tags:
                toAdd = False
        if toAdd:
            # Create a patchgroup tag for the InstanceId
            TagValue = '{}-{}-{}-{}'.format(portfolio, app, branch, build)
            response = ec2_client.create_tags(
                Resources=[
                    InstanceId,
                ],
                Tags=[
                    {
                        'Key': '{}'.format(os.environ.get("hotfixPatchGroupName", None)),
                        'Value': TagValue
                    },
                ],
            )
            tags_to_patch.append(TagValue)

    print("List of filtered Tags to be Patched: {}".format(tags_to_patch))
    return tags_to_patch

def __start_automation_execution(RoleArn, TagstoPatch, AssumeRoleName):
    ssm_client = __ssm_client(
            RoleArn=RoleArn,
            session_name=AssumeRoleName
        )
    for tagValue in TagstoPatch:
        response = ssm_client.start_automation_execution(
            DocumentName=os.environ.get("SSMDocumentName", None),
            # TODO - Enable saving to S3 the compliance report once SSM support "Name" parameter in AWS::SSM::Document
            # Parameters={
            #     'ReportS3Bucket': [
            #         os.environ.get("ReportBucket", None)
            #     ]
            # },
            TargetParameterName='InstanceId',
            Targets=[
                {
                    'Key': 'tag:{}'.format(os.environ.get("hotfixPatchGroupName", None)),
                    'Values': [
                        tagValue
                    ]
                },
            ],
            MaxConcurrency='{}'.format(os.environ.get("hotfixMaxConcurrency", None)),
            MaxErrors='{}'.format(os.environ.get("hotfixMaxErrors", None))
        )
        print(response)  

def main(args):
    #Parameter declaration
    TAGS = args['tags'].replace(" ", "").split(",")
    ACCOUNTS = args['accounts'].replace(" ", "").split(",")
    AssumeRoleName = os.environ.get("AssumeRoleName", None)
    print(TAGS)
    print(ACCOUNTS)

    for accountNo in ACCOUNTS:
        RoleArn = "arn:aws:iam::{}:role/{}".format(accountNo, AssumeRoleName)
        print(RoleArn)

        # GET FILTERED INVENTORY => INVENTORY LIST GROUP BY "Portfolio-App-Branch-Build" Tag (add this tag to all patched resources)
        InstanceIds = __get_managed_instanceIds(RoleArn, AssumeRoleName)
        InstanceIds = __get_non_patched_instances(RoleArn, AssumeRoleName, InstanceIds)

        # If there is InstanceIds to be patched
        if len(InstanceIds) > 0:
            # apply patch tag to the instance
            TagstoPatch = __apply_patch_tag(RoleArn, InstanceIds, TAGS, AssumeRoleName) 

            # RUN PATCHBASELINE AUTOMATION for each tag - concurrency is 1 by default 
            __start_automation_execution(RoleArn, TagstoPatch, AssumeRoleName)

def handler(event, context):
    """Lambda handler function."""
    print('handler event={}'.format(json.dumps(event)))

    return main({
        "tags": event["hotfixmentDetails"]["Tags"],
        "accounts": event["hotfixmentDetails"]["Accounts"]
    })

if __name__ == "__main__":
    args = _get_args()
    main(args)


      
