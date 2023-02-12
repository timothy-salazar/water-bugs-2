FROM nvcr.io/nvidia/tensorflow:22.12-tf2-py3

RUN pip install git+https://github.com/keras-team/keras-tuner.git \
	&& pip install autokeras \
	&& pip install mlflow[tensorflow]

