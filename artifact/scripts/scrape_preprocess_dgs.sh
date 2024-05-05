docker run -v $(pwd):/opt/project --rm apex-dev python src/scrape_dgs.py

docker run -v $(pwd):/opt/project --rm apex-dev python src/preprocess_player_events.py

docker run -v $(pwd):/opt/project --rm apex-dev python src/process_fights_breakdown.py

docker run -v $(pwd):/opt/project --rm apex-dev python src/process_events.py