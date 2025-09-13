import yaml
import pandas as pd
import geopandas as gpd
import osmnx as ox
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure OSMnx
ox.config(use_cache=True, log_console=False)

def load_config():
    """Load configuration"""
    with open('config/koramangala_config.yaml', 'r') as f:
        return yaml.safe_load(f)

def save_geospatial_data(gdf, filename, output_dir):
    """Save GeoDataFrame as GeoJSON"""
    if gdf is None or len(gdf) == 0:
        logger.warning(f"No data to save for {filename}")
        return
    
    output_path = Path(output_dir) / f"{filename}.geojson"
    gdf.to_file(output_path, driver='GeoJSON')
    logger.info(f"Saved {filename}: {len(gdf)} features -> {output_path}")

def save_tabular_data(gdf, filename, output_dir):
    """Convert GeoDataFrame to CSV with coordinates"""
    if gdf is None or len(gdf) == 0:
        logger.warning(f"No data to save for {filename}")
        return
    
    # Create tabular version
    df = gdf.copy()
    
    # Extract coordinates
    if 'Point' in df.geometry.type.values:
        point_mask = df.geometry.type == 'Point'
        df.loc[point_mask, 'longitude'] = df.loc[point_mask, 'geometry'].x
        df.loc[point_mask, 'latitude'] = df.loc[point_mask, 'geometry'].y
    
    # For other geometries, use centroid
    non_point_mask = df.geometry.type != 'Point'
    if non_point_mask.any():
        centroids = df.loc[non_point_mask, 'geometry'].centroid
        df.loc[non_point_mask, 'longitude'] = centroids.x
        df.loc[non_point_mask, 'latitude'] = centroids.y
    
    # Drop geometry and save
    df = df.drop(columns=['geometry'])
    df = pd.DataFrame(df)
    
    output_path = Path(output_dir) / f"{filename}.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"Saved {filename} CSV: {len(df)} records -> {output_path}")

def extract_pois(area_name):
    """Extract Points of Interest for the area"""
    logger.info(f"Extracting POIs for: {area_name}")
    
    # Define POI tags
    poi_tags = {
        'amenity': ['restaurant', 'cafe', 'bar', 'fast_food', 'food_court', 
                   'hospital', 'clinic', 'pharmacy', 'dentist',
                   'school', 'university', 'college', 'library',
                   'bank', 'atm', 'fuel', 'parking', 'bus_station'],
        'shop': True,  # All shop types
        'tourism': ['hotel', 'guest_house']
    }
    
    try:
        pois = ox.geometries_from_place(area_name, poi_tags)
        logger.info(f"Extracted {len(pois)} POIs")
        return pois
    except Exception as e:
        logger.error(f"Error extracting POIs: {e}")
        return None

def extract_roads(area_name):
    """Extract road network for the area"""
    logger.info(f"Extracting roads for: {area_name}")
    
    try:
        # Try different network types
        for net_type in ['drive', 'all']:
            try:
                G = ox.graph_from_place(area_name, network_type=net_type)
                logger.info(f"Successfully extracted roads with network_type='{net_type}'")
                break
            except:
                continue
        else:
            raise Exception("Failed to extract roads with any network type")
        
        # Convert to GeoDataFrames
        nodes, edges = ox.graph_to_gdfs(G)
        
        # Clean up any list columns in edges
        for col in edges.columns:
            if edges[col].dtype == 'object':
                try:
                    if any(isinstance(x, list) for x in edges[col].dropna().head(10)):
                        edges[col] = edges[col].apply(lambda x: str(x) if isinstance(x, list) else x)
                except:
                    pass
        
        logger.info(f"Extracted {len(edges)} road edges and {len(nodes)} nodes")
        return edges, nodes
        
    except Exception as e:
        logger.error(f"Error extracting roads: {e}")
        return None, None

def categorize_pois(pois_gdf):
    """Add categories to POIs"""
    if pois_gdf is None or len(pois_gdf) == 0:
        return pois_gdf
    
    df = pois_gdf.copy()
    df['category'] = 'other'
    
    # Categorize based on amenity
    if 'amenity' in df.columns:
        df.loc[df['amenity'].isin(['restaurant', 'cafe', 'bar', 'fast_food', 'food_court']), 'category'] = 'food_beverage'
        df.loc[df['amenity'].isin(['hospital', 'clinic', 'pharmacy', 'dentist']), 'category'] = 'healthcare'
        df.loc[df['amenity'].isin(['school', 'university', 'college', 'library']), 'category'] = 'education'
        df.loc[df['amenity'].isin(['bank', 'atm']), 'category'] = 'financial'
        df.loc[df['amenity'].isin(['fuel', 'parking', 'bus_station']), 'category'] = 'transport'
    
    # Categorize shops
    if 'shop' in df.columns:
        df.loc[df['shop'].notna(), 'category'] = 'retail'
    
    logger.info(f"Categorized POIs: {df['category'].value_counts().to_dict()}")
    return df

def clean_data(gdf):
    """Basic data cleaning"""
    if gdf is None or len(gdf) == 0:
        return gdf
    
    initial_count = len(gdf)
    
    # Remove invalid geometries
    gdf = gdf[gdf.geometry.is_valid]
    
    # Remove duplicates
    gdf = gdf.drop_duplicates(subset=['geometry'])
    
    # Clean text fields
    text_columns = gdf.select_dtypes(include=['object']).columns
    for col in text_columns:
        if col != 'geometry':
            try:
                gdf[col] = gdf[col].astype(str).str.strip()
            except:
                pass
    
    cleaned_count = len(gdf)
    if initial_count != cleaned_count:
        logger.info(f"Cleaned data: {initial_count} -> {cleaned_count} features")
    
    return gdf