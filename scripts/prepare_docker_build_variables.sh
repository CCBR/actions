#!/usr/bin/env bash
#
# This script has 2 arguments:
# 1. Dockerfile path
# 2. Suffix to add to image tag eg. "dev" to add "-dev"
#
# This script performs the following tasks:
# - Retrieves the Dockerfile path from the first argument.
# - Defines the Docker Hub account name.
# - Gets the current date and time in the format ddmmyyHHMMSS.
# - Extracts the basename of the Dockerfile.
# - Extracts the tag from the Dockerfile name.
# - Extracts the directory name of the Dockerfile.
# - Extracts the repository name from the directory name.
# - Gets the base image name from the Dockerfile.
# - Constructs the full image name for Docker Hub.
# - Sets environment variables for Dockerfile, image name, base image name, build date, build tag, and repository name.
# - Prints the extracted and constructed variables for debugging.

set -euo pipefail

# Get the Dockerfile path from the first argument
dockerfile=$1
# Get the suffix name from the second argument
suffix=$2
# Docker Hub account name (namespace)
dockerhub_account=$3

echo "Dockerfile: $dockerfile"
echo "suffix: $suffix" # remember .. no suffix is added if suffix is "main"

# Get the current date and time in the format yymmdd_HHMMSS
dt=$(date +"%Y-%m-%d_%H:%M:%S")

# Extract the basename of the Dockerfile (e.g., Dockerfile.v2)
bn_dockerfile=$(basename $dockerfile)

# Extract the tag from the Dockerfile name (e.g., if Dockerfile.v2, tag=v2)
tag=${bn_dockerfile##*.}

# Extract the directory name of the Dockerfile
dn_dockerfile=$(dirname $dockerfile)

# Extract the repository name from the directory name
reponame=$(basename $dn_dockerfile)

# Get the base image name from the Dockerfile (the image specified in the FROM instruction)
baseimagename=$(grep ^FROM $dockerfile | sed "s/FROM //g")

# Construct the full image name for Docker Hub
if [[ "$suffix" == "dev" ]]; then
  tag="${tag}-dev"
elif  [[ "$suffix" == "main" || "suffix" == "" ]]; then
  tag="${tag}"
else
  tag="${tag}-feat"
fi
imagename="${dockerhub_account}/${reponame}:${tag}"
mdfile="${dn_dockerfile}/${tag}.README.md"
artifact_name=$(echo $mdfile | sed 's|/|_|g')

# Output each variable to $GITHUB_ENV to pass it to the next steps
echo "DOCKERFILE=$dockerfile" >> $GITHUB_ENV
echo "CONTEXT=$(dirname $dockerfile)" >> $GITHUB_ENV
echo "IMAGENAME=$imagename" >> $GITHUB_ENV
echo "BASEIMAGENAME=$baseimagename" >> $GITHUB_ENV
echo "BUILD_DATE=$dt" >> $GITHUB_ENV
echo "BUILD_TAG=$tag" >> $GITHUB_ENV
echo "REPONAME=$reponame" >> $GITHUB_ENV
echo "MDFILE=$mdfile" >> $GITHUB_ENV
echo "ARTIFACT_NAME=$artifact_name" >> $GITHUB_ENV
