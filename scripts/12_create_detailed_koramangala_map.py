import pandas as pd
import geopandas as gpd
import folium
from folium import plugins
import numpy as np
import json
from pathlib import Path
import logging
import branca.colormap as cm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DetailedKoramangalaMap:
    def __init__(self):
        self.output_dir = Path('data/outputs')
        self.output_dir.mkdir(exist_ok=True)
        
        # Define category colors and icons
        self.category_config = {
            'food_beverage': {
                'color': '#E74C3C',  # Red
                'icon': 'cutlery',
                'prefix': 'fa',
                'label': 'Restaurants & Cafes'
            },
            'retail': {
                'color': '#3498DB',  # Blue
                'icon': 'shopping-cart',
                'prefix': 'fa',
                'label': 'Retail & Shopping'
            },
            'healthcare': {
                'color': '#27AE60',  # Green
                'icon': 'plus-square',
                'prefix': 'fa',
                'label': 'Healthcare'
            },
            'financial': {
                'color': '#9B59B6',  # Purple
                'icon': 'university',
                'prefix': 'fa',
                'label': 'Financial Services'
            },
            'education': {
                'color': '#F39C12',  # Orange
                'icon': 'graduation-cap',
                'prefix': 'fa',
                'label': 'Education'
            },
            'transport': {
                'color': '#E67E22',  # Dark Orange
                'icon': 'bus',
                'prefix': 'fa',
                'label': 'Transport'
            },
            'other': {
                'color': '#95A5A6',  # Gray
                'icon': 'circle',
                'prefix': 'fa',
                'label': 'Other Services'
            }
        }
    
    def load_data(self):
        """Load POI and population data"""
        logger.info("Loading POI and population data...")
        
        # Load POI data with population
        pop_file = self.output_dir / 'koramangala_pois_python_population.csv'
        
        if not pop_file.exists():
            logger.error(f"Population data file not found: {pop_file}")
            return None, None
        
        pop_data = pd.read_csv(pop_file)
        logger.info(f"Loaded population data for {len(pop_data)} POIs")
        
        # Load original POI geodata for geometry
        poi_file = 'data/processed/koramangala_pois.geojson'
        if not Path(poi_file).exists():
            logger.error(f"POI GeoJSON file not found: {poi_file}")
            return None, None
        
        pois_gdf = gpd.read_file(poi_file)
        logger.info(f"Loaded {len(pois_gdf)} POIs with geometry")
        
        return pop_data, pois_gdf
    
    def estimate_1km_population(self, pop_500m):
        """Estimate 1km population from 500m data"""
        # Rough estimation: 1km radius has ~4x the area of 500m radius
        # But population density typically decreases with distance
        # Use factor of 3.2 instead of 4 to account for density falloff
        return pop_500m * 3.2
    
    def merge_population_data(self, pop_data, pois_gdf):
        """Merge population data with POI geometry"""
        logger.info("Merging population data with POI geometry...")
        
        # Reset index to ensure proper merging
        pois_gdf = pois_gdf.reset_index()
        pop_data = pop_data.reset_index()
        
        # Merge on index (poi_id)
        merged = pois_gdf.merge(pop_data, left_index=True, right_on='poi_id', how='left')
        
        # Estimate 1km population
        merged['population_1km'] = merged['population_total_500m'].apply(
            lambda x: self.estimate_1km_population(x) if pd.notna(x) else 0
        )
        
        # Clean up category data
        merged['category'] = merged['category'].fillna('other')
        merged['poi_name'] = merged['poi_name'].fillna(merged['name']).fillna('Unknown')
        
        logger.info(f"Merged data for {len(merged)} POIs")
        return merged
    
    def create_population_heatmap_data(self, merged_data):
        """Create heatmap data points for population visualization"""
        logger.info("Creating population heatmap data...")
        
        heat_data = []
        
        for _, poi in merged_data.iterrows():
            # Get coordinates
            if poi.geometry.geom_type == 'Point':
                lat, lon = poi.geometry.y, poi.geometry.x
            else:
                centroid = poi.geometry.centroid
                lat, lon = centroid.y, centroid.x
            
            # Use 200m population for heatmap intensity
            pop_200m = poi.get('population_total_200m', 0)
            
            if pop_200m > 0:
                # Add multiple points based on population for better heatmap effect
                intensity = min(int(pop_200m / 100), 15)  # Scale for visualization
                for _ in range(intensity):
                    # Add small random offset for better distribution
                    lat_offset = lat + np.random.normal(0, 0.0002)  # ~20m variation
                    lon_offset = lon + np.random.normal(0, 0.0002)
                    heat_data.append([lat_offset, lon_offset])
        
        logger.info(f"Created heatmap with {len(heat_data)} data points")
        return heat_data
    
    def create_poi_popup(self, poi):
        """Create detailed popup for POI"""
        # Get basic info
        name = poi.get('poi_name', 'Unknown')
        category = poi.get('category', 'other')
        amenity = poi.get('amenity', poi.get('shop', 'Unknown'))
        
        # Population data
        pop_100m = int(poi.get('population_total_100m', 0))
        pop_200m = int(poi.get('population_total_200m', 0))
        pop_500m = int(poi.get('population_total_500m', 0))
        pop_1km = int(poi.get('population_1km', 0))
        
        # Additional details
        phone = poi.get('phone', 'Not available')
        website = poi.get('website', 'Not available')
        opening_hours = poi.get('opening_hours', 'Not available')
        address = poi.get('addr:street', 'Not available')
        
        # Create popup HTML
        popup_html = f"""
        <div style="width: 300px; font-family: Arial, sans-serif;">
            <h3 style="margin: 0 0 10px 0; color: {self.category_config[category]['color']};">
                <i class="fa fa-{self.category_config[category]['icon']}"></i> {name}
            </h3>
            
            <div style="margin-bottom: 10px;">
                <strong>Category:</strong> {self.category_config[category]['label']}<br>
                <strong>Type:</strong> {amenity}
            </div>
            
            <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                <h4 style="margin: 0 0 8px 0; color: #333;">Population Catchment Areas</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; font-size: 12px;">
                    <div><strong>100m:</strong> {pop_100m:,} people</div>
                    <div><strong>200m:</strong> {pop_200m:,} people</div>
                    <div><strong>500m:</strong> {pop_500m:,} people</div>
                    <div style="grid-column: 1/3; background-color: #e9ecef; padding: 5px; border-radius: 3px;">
                        <strong>1km:</strong> {pop_1km:,} people
                    </div>
                </div>
            </div>
            
            <div style="font-size: 12px; color: #666;">
                <div><strong>Address:</strong> {address}</div>
                <div><strong>Phone:</strong> {phone}</div>
                <div><strong>Hours:</strong> {opening_hours}</div>
                {f'<div><strong>Website:</strong> <a href="{website}" target="_blank">Link</a></div>' if website != 'Not available' else ''}
            </div>
        </div>
        """
        
        return popup_html
    
    def create_category_legend(self):
        """Create legend HTML for POI categories"""
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 200px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px; border-radius: 5px;
                    box-shadow: 0 0 15px rgba(0,0,0,0.2);">
        <h4 style="margin-top: 0;">POI Categories</h4>
        '''
        
        for category, config in self.category_config.items():
            legend_html += f'''
            <p style="margin: 5px 0;">
                <i class="fa fa-{config['icon']}" style="color: {config['color']}; width: 15px;"></i>
                {config['label']}
            </p>
            '''
        
        legend_html += '''
        <hr style="margin: 10px 0;">
        <p style="margin: 5px 0; font-size: 11px; color: #666;">
            <strong>Heatmap:</strong> Population density<br>
            <strong>Click markers</strong> for detailed info
        </p>
        </div>
        '''
        
        return legend_html
    
    def create_detailed_map(self):
        """Create the main detailed interactive map"""
        logger.info("Creating detailed interactive map...")
        
        # Load data
        pop_data, pois_gdf = self.load_data()
        if pop_data is None or pois_gdf is None:
            return None
        
        # Merge data
        merged_data = self.merge_population_data(pop_data, pois_gdf)
        
        # Calculate map center
        center_lat = merged_data.geometry.centroid.y.mean()
        center_lon = merged_data.geometry.centroid.x.mean()
        
        # Create base map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=15,
            tiles=None
        )
        
        # Add different tile layers
        folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)
        folium.TileLayer(
            tiles='https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
            attr='&copy; OpenStreetMap contributors, Tiles style by Humanitarian OpenStreetMap Team',
            name='Humanitarian',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Add satellite imagery
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Create population heatmap
        logger.info("Adding population heatmap...")
        heat_data = self.create_population_heatmap_data(merged_data)
        
        if heat_data:
            heatmap = plugins.HeatMap(
                heat_data,
                name='Population Density',
                radius=25,
                blur=15,
                gradient={
                    0.0: 'blue',
                    0.3: 'cyan', 
                    0.5: 'lime',
                    0.7: 'yellow',
                    1.0: 'red'
                },
                max_zoom=18
            )
            heatmap.add_to(m)
        
        # Create feature groups for each category
        category_groups = {}
        for category in self.category_config.keys():
            category_groups[category] = folium.FeatureGroup(
                name=self.category_config[category]['label']
            )
        
        # Add POI markers by category
        logger.info("Adding POI markers...")
        
        for _, poi in merged_data.iterrows():
            # Get coordinates
            if poi.geometry.geom_type == 'Point':
                lat, lon = poi.geometry.y, poi.geometry.x
            else:
                centroid = poi.geometry.centroid
                lat, lon = centroid.y, centroid.x
            
            category = poi.get('category', 'other')
            config = self.category_config[category]
            
            # Create popup
            popup_html = self.create_poi_popup(poi)
            popup = folium.Popup(popup_html, max_width=320)
            
            # Create marker
            marker = folium.Marker(
                location=[lat, lon],
                popup=popup,
                icon=folium.Icon(
                    color='white',
                    icon_color=config['color'],
                    icon=config['icon'],
                    prefix=config['prefix']
                )
            )
            
            # Add to appropriate category group
            marker.add_to(category_groups[category])
        
        # Add all category groups to map
        for group in category_groups.values():
            group.add_to(m)
        
        # Add statistics overlay
        self.add_statistics_panel(m, merged_data)
        
        # Add custom legend
        legend_html = self.create_category_legend()
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Add layer control
        folium.LayerControl(position='topleft').add_to(m)
        
        # Add fullscreen button
        plugins.Fullscreen().add_to(m)
        
        # Add search functionality
        plugins.Search(
            layer=category_groups['food_beverage'],
            search_label='name',
            placeholder='Search restaurants...',
            collapsed=True
        ).add_to(m)
        
        return m
    
    def add_statistics_panel(self, map_obj, data):
        """Add statistics panel to the map"""
        
        # Calculate statistics
        total_pois = len(data)
        category_counts = data['category'].value_counts()
        avg_pop_1km = data['population_1km'].mean()
        max_pop_1km = data['population_1km'].max()
        
        stats_html = f'''
        <div style="position: fixed; 
                    bottom: 10px; left: 10px; width: 250px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px; border-radius: 5px;
                    box-shadow: 0 0 15px rgba(0,0,0,0.2);">
        <h4 style="margin-top: 0;">Koramangala Statistics</h4>
        
        <div style="margin-bottom: 8px;">
            <strong>Total POIs:</strong> {total_pois:,}
        </div>
        
        <div style="margin-bottom: 8px;">
            <strong>Average 1km Population:</strong> {avg_pop_1km:,.0f}
        </div>
        
        <div style="margin-bottom: 8px;">
            <strong>Highest 1km Catchment:</strong> {max_pop_1km:,.0f}
        </div>
        
        <div style="font-size: 11px; color: #666;">
            <strong>Category Breakdown:</strong><br>
        '''
        
        for category, count in category_counts.head(5).items():
            config = self.category_config.get(category, self.category_config['other'])
            stats_html += f'''
            <div style="margin: 2px 0;">
                <i class="fa fa-{config['icon']}" style="color: {config['color']}; width: 12px;"></i>
                {config['label']}: {count}
            </div>
            '''
        
        stats_html += '''
        </div>
        </div>
        '''
        
        map_obj.get_root().html.add_child(folium.Element(stats_html))

def main():
    """Create the detailed Koramangala map"""
    logger.info("Starting detailed Koramangala map creation")
    
    # Initialize map creator
    map_creator = DetailedKoramangalaMap()
    
    # Create the map
    detailed_map = map_creator.create_detailed_map()
    
    if detailed_map:
        # Save the map
        output_file = map_creator.output_dir / 'koramangala_detailed_interactive_map.html'
        detailed_map.save(str(output_file))
        
        logger.info(f"Detailed interactive map created: {output_file}")
        logger.info("Map features:")
        logger.info("  - POI markers categorized by type with custom icons")
        logger.info("  - Population density heatmap overlay")
        logger.info("  - Detailed popups with 1km catchment population")
        logger.info("  - Multiple map layers (Street, Humanitarian, Satellite)")
        logger.info("  - Interactive legend and statistics panel")
        logger.info("  - Search functionality for POIs")
        logger.info("  - Fullscreen mode")
        
        return True
    else:
        logger.error("Failed to create detailed map")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)