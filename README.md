# Patching system

## What is this?

Critical Patching system for immediate patching of critical security events in a running fleet

## How

Uses a CodeBuild job in automation account to run a bash script that uses awscli to trigger ssm command in targets/instances
