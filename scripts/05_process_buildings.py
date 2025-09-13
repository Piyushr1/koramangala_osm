import sys
import logging
import osmnx as ox
import pandas as pd
import geopandas as gpd
from pathlib import Path
sys.path.append('scripts')
from utils.osm_helper import (load_config, clean_data, 
                             save_geospatial_data, save_tabular_data)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_buildings(area_name):
    """Extract building footprints for the area"""
    logger.info(f"Extracting buildings for: {area_name}")
    
    # Define building tags
    building_tags = {
        'building': True  # All buildings
    }
    
    try:
        buildings = ox.geometries_from_place(area_name, building_tags)
        logger.info(f"Extracted {len(buildings)} buildings")
        return buildings
    except Exception as e:
        logger.error(f"Error extracting buildings: {e}")
        return None

def categorize_buildings(buildings_gdf):
    """Add categories to buildings based on building type"""
    if buildings_gdf is None or len(buildings_gdf) == 0:
        return buildings_gdf
    
    df = buildings_gdf.copy()
    df['building_category'] = 'unknown'
    
    # Building type mapping
    building_categories = {
        'residential': ['house', 'apartments', 'residential', 'detached', 'terrace', 'bungalow'],
        'commercial': ['commercial', 'office', 'retail', 'shop', 'warehouse'],
        'institutional': ['school', 'university', 'hospital', 'government', 'public'],
        'religious': ['church', 'mosque', 'temple', 'cathedral', 'synagogue'],
        'industrial': ['industrial', 'factory', 'manufacturing'],
        'recreational': ['sports_hall', 'stadium', 'gym', 'community_centre']
    }
    
    # Categorize based on building type
    if 'building' in df.columns:
        for category, types in building_categories.items():
            mask = df['building'].isin(types)
            df.loc[mask, 'building_category'] = category
        
        # Set generic 'yes' buildings as residential (common in residential areas)
        df.loc[df['building'] == 'yes', 'building_category'] = 'residential'
    
    logger.info(f"Building categories: {df['building_category'].value_counts().to_dict()}")
    return df

def add_building_metrics(buildings_gdf):
    """Add useful metrics to buildings"""
    if buildings_gdf is None or len(buildings_gdf) == 0:
        return buildings_gdf
    
    df = buildings_gdf.copy()
    
    # Calculate area in square meters (convert to local CRS for accuracy)
    logger.info("Calculating building areas...")
    df_projected = df.to_crs('EPSG:32643')  # UTM Zone 43N for India
    df['area_sqm'] = df_projected.geometry.area
    
    # Add building levels if available
    if 'building:levels' in df.columns:
        df['levels'] = pd.to_numeric(df['building:levels'], errors='coerce')
    else:
        df['levels'] = None
    
    # Calculate approximate floor area (area * levels)
    df['estimated_floor_area_sqm'] = df['area_sqm'] * df['levels'].fillna(1)
    
    # Add height if available
    if 'height' in df.columns:
        df['height_meters'] = pd.to_numeric(df['height'].str.replace(' m', ''), errors='coerce')
    else:
        df['height_meters'] = None
    
    # Add address information if available
    address_fields = ['addr:street', 'addr:housenumber', 'addr:postcode']
    df['has_address'] = df[address_fields].notna().any(axis=1)
    
    return df

def create_building_summary(buildings_gdf):
    """Create a summary of building statistics"""
    if buildings_gdf is None or len(buildings_gdf) == 0:
        return {}
    
    summary = {
        'total_buildings': len(buildings_gdf),
        'total_area_sqm': buildings_gdf['area_sqm'].sum(),
        'average_area_sqm': buildings_gdf['area_sqm'].mean(),
        'building_categories': buildings_gdf['building_category'].value_counts().to_dict(),
        'buildings_with_address': buildings_gdf['has_address'].sum(),
        'buildings_with_levels': buildings_gdf['levels'].notna().sum()
    }
    
    if 'height_meters' in buildings_gdf.columns:
        summary['buildings_with_height'] = buildings_gdf['height_meters'].notna().sum()
        summary['average_height_meters'] = buildings_gdf['height_meters'].mean()
    
    return summary

def main():
    logger.info("Processing buildings for Koramangala")
    
    # Load config
    config = load_config()
    area_name = config['area']['name']
    output_dir = config['output_paths']['processed']
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Extract buildings
    buildings = extract_buildings(area_name)
    if buildings is None:
        logger.error("Failed to extract buildings")
        return False
    
    # Categorize buildings
    buildings = categorize_buildings(buildings)
    
    # Add building metrics
    buildings = add_building_metrics(buildings)
    
    # Clean data
    buildings = clean_data(buildings)
    
    # Save data
    save_geospatial_data(buildings, 'koramangala_buildings', output_dir)
    save_tabular_data(buildings, 'koramangala_buildings', output_dir)
    
    # Create and print summary
    summary = create_building_summary(buildings)
    
    logger.info("Building Processing Summary:")
    logger.info(f"Total buildings: {summary['total_buildings']:,}")
    logger.info(f"Total area: {summary['total_area_sqm']:,.0f} sqm ({summary['total_area_sqm']/10000:.1f} hectares)")
    logger.info(f"Average building size: {summary['average_area_sqm']:.0f} sqm")
    logger.info(f"Buildings with addresses: {summary['buildings_with_address']}")
    logger.info(f"Building categories: {summary['building_categories']}")
    
    # Save summary as JSON
    import json
    summary_path = Path(output_dir) / 'koramangala_buildings_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info(f"Saved building summary: {summary_path}")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)