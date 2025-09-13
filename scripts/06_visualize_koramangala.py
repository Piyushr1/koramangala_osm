import sys
import logging
import pandas as pd
import geopandas as gpd
import folium
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_interactive_map():
    """Create an interactive Folium map with all data layers"""
    logger.info("Creating interactive map...")
    
    # Load data
    pois = gpd.read_file('data/processed/koramangala_pois.geojson')
    roads = gpd.read_file('data/processed/koramangala_roads.geojson')
    buildings = gpd.read_file('data/processed/koramangala_buildings.geojson')
    
    # Get center point
    center_lat = pois.geometry.centroid.y.mean()
    center_lon = pois.geometry.centroid.x.mean()
    
    # Create base map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        tiles='OpenStreetMap'
    )
    
    # Add buildings layer (as background)
    logger.info("Adding buildings layer...")
    buildings_sample = buildings.sample(min(1000, len(buildings)))  # Sample for performance
    for idx, building in buildings_sample.iterrows():
        if building.geometry.geom_type == 'Polygon':
            # Convert to GeoJSON-like format
            coords = [[list(coord) for coord in building.geometry.exterior.coords]]
            folium.Polygon(
                locations=[[coord[1], coord[0]] for coord in coords[0]],
                color='gray',
                weight=1,
                fillColor='lightgray',
                fillOpacity=0.3,
                popup=f"Building: {building.get('building', 'Unknown')}<br>Area: {building.get('area_sqm', 0):.0f} sqm"
            ).add_to(m)
    
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
    
    # Add POIs layer (handle mixed geometry types)
    logger.info("Adding POIs layer...")
    for idx, poi in pois.iterrows():
        category = poi.get('category', 'other')
        color = category_colors.get(category, 'gray')
        
        # Get coordinates (handle both points and polygons)
        if poi.geometry.geom_type == 'Point':
            lat, lon = poi.geometry.y, poi.geometry.x
        else:
            # Use centroid for polygons
            centroid = poi.geometry.centroid
            lat, lon = centroid.y, centroid.x
        
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            popup=f"<b>{poi.get('name', 'Unknown')}</b><br>"
                  f"Category: {category}<br>"
                  f"Type: {poi.get('amenity', poi.get('shop', 'Unknown'))}",
            color=color,
            fillColor=color,
            fillOpacity=0.7
        ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Save map
    map_path = 'data/outputs/koramangala_interactive_map.html'
    m.save(map_path)
    logger.info(f"Interactive map saved: {map_path}")
    
    return map_path

def create_business_charts():
    """Create business analysis charts"""
    logger.info("Creating business analysis charts...")
    
    # Load business data
    restaurants = pd.read_csv('data/outputs/koramangala_restaurants.csv')
    retail = pd.read_csv('data/outputs/koramangala_retail.csv')
    
    # Set up the plotting style
    plt.style.use('default')
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Koramangala Business Analysis', fontsize=16, fontweight='bold')
    
    # 1. POI Categories Distribution
    pois = gpd.read_file('data/processed/koramangala_pois.geojson')
    category_counts = pois['category'].value_counts()
    
    axes[0,0].pie(category_counts.values, labels=category_counts.index, autopct='%1.1f%%')
    axes[0,0].set_title('POI Categories Distribution')
    
    # 2. Restaurant Types
    if len(restaurants) > 0 and 'amenity' in restaurants.columns:
        restaurant_types = restaurants['amenity'].value_counts().head(8)
        axes[0,1].bar(range(len(restaurant_types)), restaurant_types.values)
        axes[0,1].set_xticks(range(len(restaurant_types)))
        axes[0,1].set_xticklabels(restaurant_types.index, rotation=45, ha='right')
        axes[0,1].set_title('Restaurant Types')
        axes[0,1].set_ylabel('Count')
    
    # 3. Retail Shop Types
    if len(retail) > 0 and 'shop_type' in retail.columns:
        shop_types = retail['shop_type'].value_counts().head(10)
        axes[1,0].barh(range(len(shop_types)), shop_types.values)
        axes[1,0].set_yticks(range(len(shop_types)))
        axes[1,0].set_yticklabels(shop_types.index)
        axes[1,0].set_title('Top 10 Retail Shop Types')
        axes[1,0].set_xlabel('Count')
    
    # 4. Building Categories
    buildings = gpd.read_file('data/processed/koramangala_buildings.geojson')
    building_cats = buildings['building_category'].value_counts()
    
    axes[1,1].bar(range(len(building_cats)), building_cats.values)
    axes[1,1].set_xticks(range(len(building_cats)))
    axes[1,1].set_xticklabels(building_cats.index, rotation=45, ha='right')
    axes[1,1].set_title('Building Categories')
    axes[1,1].set_ylabel('Count')
    
    plt.tight_layout()
    
    # Save chart
    chart_path = 'data/outputs/koramangala_business_analysis.png'
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    logger.info(f"Business analysis chart saved: {chart_path}")
    
    return chart_path

def create_spatial_distribution_map():
    """Create a heatmap-style visualization of business density"""
    logger.info("Creating spatial distribution visualization...")
    
    # Load POI data
    pois = gpd.read_file('data/processed/koramangala_pois.geojson')
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Plot buildings as background
    buildings = gpd.read_file('data/processed/koramangala_buildings.geojson')
    buildings.plot(ax=ax, color='lightgray', alpha=0.5, edgecolor='gray', linewidth=0.5)
    
    # Plot POIs by category with different colors
    categories = pois['category'].unique()
    colors = plt.cm.Set3(range(len(categories)))
    
    for i, category in enumerate(categories):
        category_pois = pois[pois['category'] == category]
        if len(category_pois) > 0:
            category_pois.plot(ax=ax, color=colors[i], markersize=30, 
                             alpha=0.7, label=f"{category} ({len(category_pois)})")
    
    ax.set_title('Koramangala: Spatial Distribution of Businesses', fontsize=14, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.set_axis_off()
    
    plt.tight_layout()
    
    # Save map
    spatial_path = 'data/outputs/koramangala_spatial_distribution.png'
    plt.savefig(spatial_path, dpi=300, bbox_inches='tight')
    logger.info(f"Spatial distribution map saved: {spatial_path}")
    
    return spatial_path

def create_summary_dashboard():
    """Create a summary dashboard with key metrics"""
    logger.info("Creating summary dashboard...")
    
    # Load all data
    pois = gpd.read_file('data/processed/koramangala_pois.geojson')
    buildings = gpd.read_file('data/processed/koramangala_buildings.geojson')
    roads = gpd.read_file('data/processed/koramangala_roads.geojson')
    
    # Calculate metrics
    metrics = {
        'total_pois': len(pois),
        'total_buildings': len(buildings),
        'total_roads': len(roads),
        'restaurants': len(pois[pois['category'] == 'food_beverage']),
        'retail_outlets': len(pois[pois['category'] == 'retail']),
        'healthcare_facilities': len(pois[pois['category'] == 'healthcare']),
        'total_building_area_sqm': buildings['area_sqm'].sum(),
        'avg_building_size_sqm': buildings['area_sqm'].mean(),
        'commercial_buildings': len(buildings[buildings['building_category'] == 'commercial']),
        'residential_buildings': len(buildings[buildings['building_category'] == 'residential'])
    }
    
    # Create dashboard
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Koramangala Urban Data Dashboard', fontsize=18, fontweight='bold')
    
    # Key metrics text
    ax1.text(0.1, 0.8, f"Total POIs: {metrics['total_pois']:,}", fontsize=16, transform=ax1.transAxes)
    ax1.text(0.1, 0.6, f"Total Buildings: {metrics['total_buildings']:,}", fontsize=16, transform=ax1.transAxes)
    ax1.text(0.1, 0.4, f"Total Roads: {metrics['total_roads']:,}", fontsize=16, transform=ax1.transAxes)
    ax1.text(0.1, 0.2, f"Built-up Area: {metrics['total_building_area_sqm']/10000:.1f} hectares", fontsize=16, transform=ax1.transAxes)
    ax1.set_title('Key Metrics')
    ax1.axis('off')
    
    # Business breakdown
    business_data = [metrics['restaurants'], metrics['retail_outlets'], metrics['healthcare_facilities']]
    business_labels = ['Restaurants', 'Retail', 'Healthcare']
    ax2.pie(business_data, labels=business_labels, autopct='%1.1f%%')
    ax2.set_title('Business Breakdown')
    
    # Building types
    building_data = [metrics['residential_buildings'], metrics['commercial_buildings']]
    building_labels = ['Residential', 'Commercial']
    ax3.bar(building_labels, building_data)
    ax3.set_title('Building Types')
    ax3.set_ylabel('Count')
    
    # POI density map
    pois.plot(ax=ax4, markersize=1, alpha=0.6)
    ax4.set_title('POI Locations')
    ax4.set_axis_off()
    
    plt.tight_layout()
    
    # Save dashboard
    dashboard_path = 'data/outputs/koramangala_dashboard.png'
    plt.savefig(dashboard_path, dpi=300, bbox_inches='tight')
    logger.info(f"Dashboard saved: {dashboard_path}")
    
    return dashboard_path, metrics

def main():
    """Create all visualizations"""
    logger.info("Creating Koramangala data visualizations")
    
    # Create output directory
    Path('data/outputs').mkdir(exist_ok=True)
    
    # Check if data files exist
    required_files = [
        'data/processed/koramangala_pois.geojson',
        'data/processed/koramangala_buildings.geojson',
        'data/processed/koramangala_roads.geojson'
    ]
    
    for file_path in required_files:
        if not Path(file_path).exists():
            logger.error(f"Required file not found: {file_path}")
            logger.error("Please run the processing scripts first")
            return False
    
    # Create visualizations
    try:
        # Interactive map
        map_path = create_interactive_map()
        
        # Business charts
        chart_path = create_business_charts()
        
        # Spatial distribution
        spatial_path = create_spatial_distribution_map()
        
        # Summary dashboard
        dashboard_path, metrics = create_summary_dashboard()
        
        # Summary
        logger.info("Visualization Creation Complete!")
        logger.info(f"Created {len([map_path, chart_path, spatial_path, dashboard_path])} visualizations:")
        logger.info(f"  1. Interactive map: {map_path}")
        logger.info(f"  2. Business charts: {chart_path}")
        logger.info(f"  3. Spatial distribution: {spatial_path}")
        logger.info(f"  4. Summary dashboard: {dashboard_path}")
        
        # Print key metrics
        logger.info("\nKey Findings:")
        logger.info(f"  • {metrics['total_pois']:,} points of interest mapped")
        logger.info(f"  • {metrics['total_buildings']:,} buildings covering {metrics['total_building_area_sqm']/10000:.1f} hectares")
        logger.info(f"  • {metrics['restaurants']} restaurants, {metrics['retail_outlets']} shops, {metrics['healthcare_facilities']} healthcare facilities")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating visualizations: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)
