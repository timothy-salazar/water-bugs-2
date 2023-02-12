#!/bin/bash

#############
# VARIABLES
#############

# This is the name of the docker container
CONTAINER_NAME=tf-notebook

# If the jupyter notebook server isn't available, the script will
# sleep for an amount of time specified by SLEEP_INTERVAL, and then
# it will retry. It will make a number of attempts equal to RETRY_COUNT
SLEEP_INTERVAL=1
RETRY_COUNT=4

# check to see that the PERSISTENT_STORAGE_PATH environment variable
# has been set
if [ -n "$PERSISTENT_STORAGE_PATH" ]; then
  echo "Will attempt to mount drive $PERSISTENT_STORAGE_PATH as persistent storage"
else
  echo "The PERSISTENT_STORAGE_PATH environment variable has not been set. Exiting."
  exit 1
fi

# Mounts a drive containing a directory that I want to be accessible to the container
mount_persistent_storage() {
  MOUNT_POINT_PATTERN='(?<=\s{4}MountPoints:\s{8})\S+'
  MOUNT_POINT=$(udisksctl info -b $PERSISTENT_STORAGE_PATH | grep -o -P $MOUNT_POINT_PATTERN)
  if [ $? -gt 0 ]; then
    echo "Mounting disk for persistent storage"
    udisksctl mount -b $PERSISTENT_STORAGE_PATH
  else
    echo "Disk is already mounted"
  fi
}

# tries to get the token from the Jupyter notebook server.
# The server is likely to be unavailable at first, so it sleeps and retries
# if this is the case.
wait_for_notebook() {
  wait $!
  for (( i=0; i<$RETRY_COUNT; ++i )); do
    TOKEN=$(docker exec -it $CONTAINER_NAME jupyter notebook list --json | jq '.token' -j -r)
    if [ -n "$TOKEN" ]; then
      break
    else
      echo "waiting for notebook server to come up..."
      sleep $SLEEP_INTERVAL
    fi
  done
}

mount_persistent_storage
docker compose build
docker compose up -d
wait_for_notebook
URL='http://localhost:8888/?token='$TOKEN
python3 -m webbrowser $URL
