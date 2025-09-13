import sys
import logging
from pathlib import Path
sys.path.append('scripts')
from utils.osm_helper import (load_config, extract_pois, categorize_pois, 
                             clean_data, save_geospatial_data, save_tabular_data)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Processing POIs for Koramangala")
    
    # Load config
    config = load_config()
    area_name = config['area']['name']
    output_dir = config['output_paths']['processed']
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Extract POIs
    pois = extract_pois(area_name)
    if pois is None:
        logger.error("Failed to extract POIs")
        return False
    
    # Categorize POIs
    pois = categorize_pois(pois)
    
    # Clean data
    pois = clean_data(pois)
    
    # Save data
    save_geospatial_data(pois, 'koramangala_pois', output_dir)
    save_tabular_data(pois, 'koramangala_pois', output_dir)
    
    # Print summary
    logger.info("POI Processing Summary:")
    logger.info(f"Total POIs: {len(pois)}")
    logger.info(f"Categories: {pois['category'].value_counts().to_dict()}")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)