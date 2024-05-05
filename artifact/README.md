# Setup

## Build the Docker image
```bash

cd apexlegends-data-analysis # Go to the project root directory
docker build -t apex-dev -f artifact/Dockerfile .
```


## Run the Docker container
```bash
cd apexlegends-data-analysis # Go to the project root directory
docker run -v $(pwd):/opt/project --rm -it apex-dev python src/scrape_dgs.py
```


```