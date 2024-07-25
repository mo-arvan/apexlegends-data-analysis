FROM python:3.11-slim

#RUN apt-get update && \
#    apt-get install ffmpeg libsm6 libxext6  -y
COPY requirements.txt /docker_build/

RUN pip install --upgrade pip && \
    pip install -r /docker_build/requirements.txt && \
    pip install requests plotly tqdm

# matplotlib seaborn scikit-learn beautifulsoup4 lxml opencv-python

# change the working directory to /opt/project

WORKDIR /opt/project