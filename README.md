# water-bugs-2

Right now this just sets up a docker environment. As I work on this project I'll add more details.


## Setting up the environment:
Setting up all the tools and satisfying all the requirements to get Tensorflow
running with GPU support is a headache. Compatibility issues are a nightmare,
and at the end of it all you'll be hard pressed to replicate on another machine.
Fortunately Nvidia provides a docker image with everything installed and 
configured properly, which simplifies the problem IMMENSELY.

### Requirements:
- Docker

### Environment Variables:
- PERSISTENT_STORAGE_UUID: the UUID of the persistent storage volume.
- VOLUME_PATH: the path to the