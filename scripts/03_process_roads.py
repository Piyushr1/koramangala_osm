import sys
import logging
from pathlib import Path
sys.path.append('scripts')
from utils.osm_helper import (load_config, extract_roads, clean_data, 
                             save_geospatial_data, save_tabular_data)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Processing roads for Koramangala")
    
    # Load config
    config = load_config()
    area_name = config['area']['name']
    output_dir = config['output_paths']['processed']
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Extract roads
    roads, nodes = extract_roads(area_name)
    if roads is None:
        logger.error("Failed to extract roads")
        return False
    
    # Clean data
    roads = clean_data(roads)
    nodes = clean_data(nodes)
    
    # Save roads
    save_geospatial_data(roads, 'koramangala_roads', output_dir)
    save_tabular_data(roads, 'koramangala_roads', output_dir)
    
    # Save nodes
    save_geospatial_data(nodes, 'koramangala_nodes', output_dir)
    save_tabular_data(nodes, 'koramangala_nodes', output_dir)
    
    # Print summary
    logger.info("Road Processing Summary:")
    logger.info(f"Road segments: {len(roads)}")
    logger.info(f"Intersections: {len(nodes)}")
    if 'highway' in roads.columns:
        logger.info(f"Road types: {roads['highway'].value_counts().head().to_dict()}")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)
