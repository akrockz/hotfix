#!/bin/bash

set -e

echo "core-hotfix package script running."

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" # this script's directory
STAGING="${DIR}/../_staging"
echo "STAGING=${STAGING}"

# Setup, cleanup.
cd $DIR
mkdir -p $STAGING # files dir for lambdas
rm -rf $STAGING/*

# Copy deployspec and CFN templates into staging folder.
cp -pr $DIR/../*.yaml $STAGING/

# Package lambdas folder into zip files.
cd $DIR/../lambdas/AWS-PatchInstanceWithRollback
zip --symlinks -r9 $STAGING/AWS-PatchInstanceWithRollback.zip *

# Package scripts folder into zip files.
cd $DIR/../scripts
zip --symlinks -r9 $STAGING/scripts.zip *

echo "core-hotfix package step complete, run.sh can be executed now."
