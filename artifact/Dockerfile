FROM python:3.11-slim

#RUN apt-get update && \
#    apt-get install ffmpeg libsm6 libxext6  -y
COPY requirements.txt /docker_build/

RUN pip install --upgrade pip && \
    pip install -r /docker_build/requirements.txt && \
    pip install numpy matplotlib pandas seaborn scikit-learn requests beautifulsoup4 lxml opencv-python bokeh==2.4.3 \
    plotly tqdm

# change the working directory to /opt/project

WORKDIR /opt/project