import sys
import logging
import pandas as pd
import geopandas as gpd
from pathlib import Path
sys.path.append('scripts')
from utils.osm_helper import load_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_restaurant_dataset(pois_gdf):
    """Create restaurant dataset"""
    restaurants = pois_gdf[pois_gdf['category'] == 'food_beverage'].copy()
    
    if len(restaurants) == 0:
        return None
    
    # Add restaurant-specific fields
    restaurants['cuisine'] = restaurants.get('cuisine', 'unknown')
    restaurants['opening_hours'] = restaurants.get('opening_hours', 'unknown')
    restaurants['phone'] = restaurants.get('phone', '')
    restaurants['website'] = restaurants.get('website', '')
    restaurants['takeaway'] = restaurants.get('takeaway', 'unknown')
    restaurants['delivery'] = restaurants.get('delivery', 'unknown')
    
    logger.info(f"Created restaurant dataset: {len(restaurants)} restaurants")
    return restaurants

def create_retail_dataset(pois_gdf):
    """Create retail dataset"""
    retail = pois_gdf[pois_gdf['category'] == 'retail'].copy()
    
    if len(retail) == 0:
        return None
    
    # Add retail-specific fields
    retail['shop_type'] = retail.get('shop', 'unknown')
    retail['brand'] = retail.get('brand', 'independent')
    retail['opening_hours'] = retail.get('opening_hours', 'unknown')
    
    logger.info(f"Created retail dataset: {len(retail)} shops")
    return retail

def create_healthcare_dataset(pois_gdf):
    """Create healthcare dataset"""
    healthcare = pois_gdf[pois_gdf['category'] == 'healthcare'].copy()
    
    if len(healthcare) == 0:
        return None
    
    # Add healthcare-specific fields
    healthcare['facility_type'] = healthcare.get('amenity', 'unknown')
    healthcare['emergency'] = healthcare.get('emergency', 'no')
    healthcare['opening_hours'] = healthcare.get('opening_hours', 'unknown')
    healthcare['phone'] = healthcare.get('phone', '')
    
    logger.info(f"Created healthcare dataset: {len(healthcare)} facilities")
    return healthcare

def save_business_dataset(gdf, name, output_dir):
    """Save business dataset in multiple formats"""
    if gdf is None or len(gdf) == 0:
        logger.warning(f"No data for {name}")
        return
    
    # Convert to DataFrame with coordinates
    df = gdf.copy()
    df['latitude'] = df.geometry.centroid.y
    df['longitude'] = df.geometry.centroid.x
    df = df.drop(columns=['geometry'])
    df = pd.DataFrame(df)
    
    # Save as CSV
    csv_path = Path(output_dir) / f"{name}.csv"
    df.to_csv(csv_path, index=False)
    
    # Save as Excel
    excel_path = Path(output_dir) / f"{name}.xlsx"
    df.to_excel(excel_path, index=False)
    
    logger.info(f"Saved {name}: {len(df)} records -> {csv_path}")

def main():
    logger.info("Creating business datasets for Koramangala")
    
    # Load config
    config = load_config()
    processed_dir = config['output_paths']['processed']
    output_dir = config['output_paths']['outputs']
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Load POI data
    pois_file = Path(processed_dir) / 'koramangala_pois.geojson'
    if not pois_file.exists():
        logger.error(f"POIs file not found: {pois_file}")
        logger.error("Please run 02_process_pois.py first")
        return False
    
    logger.info(f"Loading POIs from: {pois_file}")
    pois_gdf = gpd.read_file(pois_file)
    logger.info(f"Loaded {len(pois_gdf)} POIs")
    
    # Create specialized datasets
    datasets = {}
    
    # Restaurants
    datasets['restaurants'] = create_restaurant_dataset(pois_gdf)
    
    # Retail
    datasets['retail'] = create_retail_dataset(pois_gdf)
    
    # Healthcare
    datasets['healthcare'] = create_healthcare_dataset(pois_gdf)
    
    # Financial services
    financial = pois_gdf[pois_gdf['category'] == 'financial']
    if len(financial) > 0:
        datasets['financial'] = financial
        logger.info(f"Created financial dataset: {len(financial)} services")
    
    # Transport
    transport = pois_gdf[pois_gdf['category'] == 'transport']
    if len(transport) > 0:
        datasets['transport'] = transport
        logger.info(f"Created transport dataset: {len(transport)} facilities")
    
    # Business Intelligence (all business POIs)
    business_pois = pois_gdf[pois_gdf['category'] != 'other']
    if len(business_pois) > 0:
        datasets['business_intelligence'] = business_pois
        logger.info(f"Created business intelligence dataset: {len(business_pois)} POIs")
    
    # Save all datasets
    for name, dataset in datasets.items():
        if dataset is not None:
            save_business_dataset(dataset, f"koramangala_{name}", output_dir)
    
    # Create summary
    summary = {
        'area': config['area']['name'],
        'total_pois': len(pois_gdf),
        'datasets_created': len([d for d in datasets.values() if d is not None]),
        'breakdown': {name: len(dataset) if dataset is not None else 0 
                     for name, dataset in datasets.items()}
    }
    
    logger.info("Business Datasets Summary:")
    for name, count in summary['breakdown'].items():
        logger.info(f"  {name}: {count} records")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)