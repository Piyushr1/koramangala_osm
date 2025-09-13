import pandas as pd
import geopandas as gpd
import folium
from folium import plugins
import numpy as np
import rasterio
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_population_raster():
    """Load the population raster data for Koramangala"""
    raster_file = Path('data/worldpop/koramangala_total_population.tif')
    
    if not raster_file.exists():
        logger.error(f"Population raster not found: {raster_file}")
        return None, None, None
    
    with rasterio.open(raster_file) as src:
        population_data = src.read(1)
        bounds = src.bounds
        transform = src.transform
        
    logger.info(f"Loaded population raster: {population_data.shape}")
    return population_data, bounds, transform

def create_population_heatmap_data(population_data, bounds, transform):
    """Convert raster data to format suitable for folium heatmap"""
    
    heat_data = []
    
    # Get raster dimensions
    height, width = population_data.shape
    
    # Convert each cell to lat/lon coordinates with population value
    for row in range(height):
        for col in range(width):
            pop_value = population_data[row, col]
            
            # Skip cells with no population
            if pop_value <= 0:
                continue
            
            # Convert pixel coordinates to geographic coordinates
            lon, lat = rasterio.transform.xy(transform, row, col)
            
            # Add multiple points based on population density for better heatmap effect
            intensity = min(int(pop_value), 10)  # Cap intensity for visualization
            for _ in range(intensity):
                heat_data.append([lat, lon])
    
    logger.info(f"Created heatmap data with {len(heat_data)} points")
    return heat_data

def create_population_grid_overlay(population_data, bounds, transform):
    """Create a grid overlay showing population density"""
    
    height, width = population_data.shape
    grid_features = []
    
    # Sample every nth cell to avoid too many polygons
    step = max(1, min(height, width) // 20)  # Create roughly 20x20 grid
    
    for row in range(0, height, step):
        for col in range(0, width, step):
            # Get population value for this cell
            pop_values = population_data[row:row+step, col:col+step]
            avg_pop = np.mean(pop_values)
            
            if avg_pop <= 0:
                continue
            
            # Get cell bounds
            left, top = rasterio.transform.xy(transform, row, col)
            right, bottom = rasterio.transform.xy(transform, row+step, col+step)
            
            # Create rectangle coordinates
            coordinates = [
                [top, left],
                [top, right], 
                [bottom, right],
                [bottom, left],
                [top, left]
            ]
            
            # Determine color based on population density
            if avg_pop < 10:
                color = '#ffffcc'
                opacity = 0.3
            elif avg_pop < 30:
                color = '#fed976'
                opacity = 0.4
            elif avg_pop < 50:
                color = '#fd8d3c'
                opacity = 0.5
            else:
                color = '#e31a1c'
                opacity = 0.6
            
            grid_features.append({
                'coordinates': coordinates,
                'population': avg_pop,
                'color': color,
                'opacity': opacity
            })
    
    logger.info(f"Created {len(grid_features)} grid cells")
    return grid_features

def create_population_overlay_map():
    """Create the main map with population overlay"""
    
    # Load POI data
    pois_file = 'data/processed/koramangala_pois.geojson'
    if not Path(pois_file).exists():
        logger.error(f"POI file not found: {pois_file}")
        return None
    
    pois = gpd.read_file(pois_file)
    
    # Load population-enriched POI data
    poi_pop_file = 'data/outputs/koramangala_pois_with_population.csv'
    if Path(poi_pop_file).exists():
        poi_pop_data = pd.read_csv(poi_pop_file)
        # Merge population data with POIs
        pois = pois.reset_index()
        pois = pois.merge(poi_pop_data[['poi_id', 'total_population_in_buffer']], 
                         left_index=True, right_on='poi_id', how='left')
    
    # Get center point for map
    center_lat = pois.geometry.centroid.y.mean()
    center_lon = pois.geometry.centroid.x.mean()
    
    # Create base map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        tiles='OpenStreetMap'
    )
    
    # Load and add population raster overlay
    population_data, bounds, transform = load_population_raster()
    
    if population_data is not None:
        # Method 1: Add heatmap layer
        logger.info("Adding population heatmap layer...")
        heat_data = create_population_heatmap_data(population_data, bounds, transform)
        
        if heat_data:
            heat_map = plugins.HeatMap(
                heat_data,
                name='Population Density Heatmap',
                radius=15,
                blur=10,
                gradient={0.2: 'blue', 0.4: 'cyan', 0.6: 'lime', 0.8: 'yellow', 1.0: 'red'}
            )
            heat_map.add_to(m)
        
        # Method 2: Add grid overlay (alternative visualization)
        logger.info("Adding population grid overlay...")
        grid_features = create_population_grid_overlay(population_data, bounds, transform)
        
        # Create a feature group for grid cells
        grid_group = folium.FeatureGroup(name='Population Grid', show=False)
        
        for feature in grid_features:
            folium.Polygon(
                locations=feature['coordinates'],
                popup=f"Avg Population: {feature['population']:.1f}",
                color='black',
                weight=1,
                fillColor=feature['color'],
                fillOpacity=feature['opacity']
            ).add_to(grid_group)
        
        grid_group.add_to(m)
    
    # Add POI layer with population context
    logger.info("Adding POI layer with population data...")
    
    # Color mapping for POI categories
    category_colors = {
        'food_beverage': 'red',
        'retail': 'blue',
        'healthcare': 'green', 
        'financial': 'purple',
        'transport': 'orange',
        'education': 'darkblue',
        'other': 'gray'
    }
    
    # Create POI feature group
    poi_group = folium.FeatureGroup(name='Points of Interest')
    
    for idx, poi in pois.iterrows():
        # Get coordinates
        if poi.geometry.geom_type == 'Point':
            lat, lon = poi.geometry.y, poi.geometry.x
        else:
            centroid = poi.geometry.centroid
            lat, lon = centroid.y, centroid.x
        
        category = poi.get('category', 'other')
        color = category_colors.get(category, 'gray')
        
        # Get population data if available
        pop_buffer = poi.get('total_population_in_buffer', 0)
        
        # Create popup with population context
        popup_text = f"""
        <b>{poi.get('name', 'Unknown')}</b><br>
        Category: {category}<br>
        Type: {poi.get('amenity', poi.get('shop', 'Unknown'))}<br>
        <hr>
        <b>Population Context:</b><br>
        Population in 200m: {pop_buffer:.0f} people
        """
        
        # Adjust marker size based on population catchment
        if pop_buffer > 0:
            radius = max(6, min(15, pop_buffer / 50))  # Scale marker size
        else:
            radius = 6
        
        folium.CircleMarker(
            location=[lat, lon],
            radius=radius,
            popup=popup_text,
            color=color,
            fillColor=color,
            fillOpacity=0.7,
            weight=2
        ).add_to(poi_group)
    
    poi_group.add_to(m)
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 120px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><b>Population Overlay Legend</b></p>
    <p><span style="color:blue;">●</span> Low Density</p>
    <p><span style="color:cyan;">●</span> Medium Density</p>
    <p><span style="color:yellow;">●</span> High Density</p>
    <p><span style="color:red;">●</span> Very High Density</p>
    <p><i>POI size = population catchment</i></p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Save map
    map_path = 'data/outputs/koramangala_population_overlay_map.html'
    m.save(map_path)
    logger.info(f"Population overlay map saved: {map_path}")
    
    return map_path

def create_population_analysis_summary():
    """Create a summary analysis of population distribution and POIs"""
    
    # Load data
    poi_pop_file = 'data/outputs/koramangala_pois_with_population.csv'
    if not Path(poi_pop_file).exists():
        logger.error("Population-enriched POI data not found")
        return
    
    poi_pop_data = pd.read_csv(poi_pop_file)
    
    # Analysis by business category
    category_analysis = poi_pop_data.groupby('poi_category').agg({
        'total_population_in_buffer': ['mean', 'median', 'max'],
        'poi_id': 'count'
    }).round(1)
    
    logger.info("Population Analysis by Business Category:")
    logger.info("\n" + str(category_analysis))
    
    # Find highest population catchment POIs
    top_population_pois = poi_pop_data.nlargest(10, 'total_population_in_buffer')[
        ['poi_name', 'poi_category', 'total_population_in_buffer']
    ]
    
    logger.info("\nTop 10 POIs by Population Catchment:")
    for _, poi in top_population_pois.iterrows():
        logger.info(f"  {poi['poi_name']} ({poi['poi_category']}): {poi['total_population_in_buffer']:.0f} people")

def main():
    """Create population overlay visualization"""
    logger.info("Creating population distribution overlay map")
    
    # Create the overlay map
    map_path = create_population_overlay_map()
    
    if map_path:
        logger.info(f"Population overlay map created: {map_path}")
        
        # Create analysis summary
        create_population_analysis_summary()
        
        logger.info("Population overlay visualization complete!")
        logger.info("Open the HTML file in your browser to view the interactive map")
        
        return True
    else:
        logger.error("Failed to create population overlay map")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)