#!/bin/bash
#

set -e

function usage {
    echo ""
    echo "Usage: $(basename "$0") [<options>]"
    echo "Available options:"
    echo "    -h, --help            Display this message"
    echo "    --aws-profile         (Optional) AWS Profile"
    echo "    --document-name       SSM Document Name to be used"
    echo "    --tags                Tag of the instances to be patched"
    echo "    --accounts            Comma separated account list"
    echo "    --prefix              Lambda function prefix"
    echo ""
    echo "Samples:"
    echo "./hotfix-run.sh --tags ssm-rhel,dev5 --accounts 2343412 --document-name AWS-PatchInstanceWithRollback --prefix core-hotfix"
}

function on_exit {
    EXIT_CODE=$?
    [ $EXIT_CODE -eq 0 ] || echo -e "\nERROR: Encountered an error. See logs for details."
    exit $EXIT_CODE
}
trap on_exit EXIT

# Process script parameters
while test $# -gt 0; do
    case "$1" in
        -h|--help)
            usage; exit 0
            ;;
        --aws-profile)
            shift; AWS_PROFILE=$1; shift
            ;;
        --document-name)
            shift; DocumentName=$1; shift
            ;;    
        --tags)
            shift; Tags=$1; shift
            ;;
        --accounts)
            shift; Accounts=$1; shift
            ;;
        --prefix)
            shift; Prefix=$1; shift
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ ! -z "$AWS_PROFILE" ]; then
  AWS_CLI_ARGS="--profile $AWS_PROFILE"
fi

# Find the AWS CLI path
[[ ! -x "$AWS_CLI" ]] && AWS_CLI=`which aws || echo ""`
[[ ! -x "$AWS_CLI" ]] && AWS_CLI="/usr/local/bin/aws"
[[ ! -x "$AWS_CLI" ]] && echo "ERROR: Could not find AWS CLI" && exit 1

cat > hotfix-payload.txt << EOF
{
    "Task": "hotfix",
    "hotfixmentDetails": {
        "DocumentName": "${Prefix}-${DocumentName}",
        "Tags": "$Tags",
        "Accounts": "$Accounts"
    }
}
EOF
cat hotfix-payload.txt

rm -f hotfix-response.txt
$AWS_CLI lambda $AWS_CLI_ARGS invoke \
    --invocation-type "RequestResponse" \
    --function-name "${Prefix}-${DocumentName}" \
    --payload "file://hotfix-payload.txt" \
    "hotfix-response.txt" > /dev/null
