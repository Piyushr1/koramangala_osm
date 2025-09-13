import sys
import logging
from pathlib import Path
sys.path.append('scripts')
from utils.osm_helper import load_config, extract_pois, extract_roads

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Testing OSM data extraction for Koramangala")
    
    # Load config
    config = load_config()
    area_name = config['area']['name']
    
    logger.info(f"Target area: {area_name}")
    
    # Test POI extraction
    logger.info("Testing POI extraction...")
    pois = extract_pois(area_name)
    if pois is not None:
        logger.info(f"✓ POIs: {len(pois)} features")
    else:
        logger.error("✗ POI extraction failed")
        return False
    
    # Test road extraction
    logger.info("Testing road extraction...")
    roads, nodes = extract_roads(area_name)
    if roads is not None:
        logger.info(f"✓ Roads: {len(roads)} edges, {len(nodes)} nodes")
    else:
        logger.error("✗ Road extraction failed")
        return False
    
    logger.info("All extractions successful! Ready for processing.")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)