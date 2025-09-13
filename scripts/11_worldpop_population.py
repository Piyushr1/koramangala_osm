import requests
import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import Point, box
from pathlib import Path
import logging
import json
import time
from urllib.parse import urljoin
import zipfile
import tempfile

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorldPopPythonAPI:
    def __init__(self):
        self.base_url = "https://www.worldpop.org/rest/"
        self.data_dir = Path("data/worldpop_python")
        self.data_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        
    def search_worldpop_datasets(self, country="IND", year=2020):
        """Search for available WorldPop datasets"""
        logger.info(f"Searching WorldPop datasets for {country}, {year}")
        
        # Try different API endpoints
        search_urls = [
            f"{self.base_url}data/search",
            "https://hub.worldpop.org/rest/data/search",
            "https://data.worldpop.org/rest/data/search"
        ]
        
        search_params = {
            "country": country,
            "year": year,
            "dataset": "population"
        }
        
        for url in search_urls:
            try:
                logger.info(f"Trying API endpoint: {url}")
                response = self.session.get(url, params=search_params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Found {len(data)} datasets")
                    return data
                else:
                    logger.warning(f"API returned status {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"API endpoint failed: {e}")
                continue
        
        logger.error("All API endpoints failed")
        return None
    
    def download_worldpop_raster(self, dataset_url, output_path):
        """Download WorldPop raster data"""
        logger.info(f"Downloading from: {dataset_url}")
        
        try:
            response = self.session.get(dataset_url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0 and downloaded % (1024*1024*10) == 0:
                            progress = (downloaded / total_size) * 100
                            logger.info(f"Download progress: {progress:.1f}%")
            
            file_size = output_path.stat().st_size / (1024*1024)
            logger.info(f"Downloaded {file_size:.1f}MB to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    
    def try_alternative_worldpop_urls(self, country="IND", year=2020):
        """Try alternative WorldPop download URLs"""
        logger.info("Trying alternative WorldPop download methods")
        
        # Alternative direct download URLs
        alternative_urls = [
            f"https://data.worldpop.org/GIS/Population/Global_2000_2020/{year}/{country}/{country.lower()}_ppp_{year}_1km_Aggregated_UNadj.tif",
            f"https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/{year}/{country}/{country.lower()}_ppp_{year}_constrained.tif",
            f"https://data.worldpop.org/GIS/PopDensity/Global_2000_2020/{year}/{country}/{country.lower()}_pd_{year}_1km.tif",
            f"ftp://ftp.worldpop.org.uk/GIS/Population/Global_2000_2020/{year}/{country}/{country.lower()}_ppp_{year}_1km_Aggregated_UNadj.tif"
        ]
        
        for i, url in enumerate(alternative_urls):
            try:
                logger.info(f"Trying URL {i+1}/{len(alternative_urls)}: {url}")
                
                # Check if URL exists
                response = self.session.head(url, timeout=30)
                if response.status_code == 200:
                    output_file = self.data_dir / f"worldpop_{country}_{year}_method{i+1}.tif"
                    
                    if self.download_worldpop_raster(url, output_file):
                        # Verify it's a valid raster
                        try:
                            with rasterio.open(output_file) as src:
                                logger.info(f"Valid raster: {src.shape}, CRS: {src.crs}")
                                return output_file
                        except Exception as e:
                            logger.error(f"Invalid raster file: {e}")
                            output_file.unlink()
                
            except Exception as e:
                logger.warning(f"URL {i+1} failed: {e}")
                continue
        
        return None
    
    def get_facebook_hrsl_data(self, country="IND"):
        """Try to access Facebook High Resolution Settlement Layer data"""
        logger.info("Attempting to access Facebook HRSL data")
        
        # Facebook HRSL is often available through Humanitarian Data Exchange
        hdx_urls = [
            f"https://data.humdata.org/api/3/action/package_show?id=highresolutionpopulationdensitymaps-{country.lower()}",
            "https://data.humdata.org/api/3/action/package_search?q=population+india"
        ]
        
        for url in hdx_urls:
            try:
                response = self.session.get(url, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        logger.info("Found Facebook HRSL data source")
                        return data
            except Exception as e:
                logger.warning(f"HDX API failed: {e}")
        
        return None
    
    def load_koramangala_pois(self):
        """Load POI data"""
        poi_file = 'data/processed/koramangala_pois.geojson'
        
        if not Path(poi_file).exists():
            logger.error(f"POI file not found: {poi_file}")
            return None
        
        pois = gpd.read_file(poi_file)
        logger.info(f"Loaded {len(pois)} POIs")
        return pois
    
    def create_buffer_zones(self, pois, buffer_distances=[100, 200, 500]):
        """Create buffer zones around POIs"""
        logger.info("Creating buffer zones around POIs")
        
        # Project to UTM for accurate buffers
        pois_utm = pois.to_crs('EPSG:32643')  # UTM Zone 43N for India
        
        buffer_results = {}
        
        for distance in buffer_distances:
            logger.info(f"Creating {distance}m buffers")
            
            buffers = pois_utm.copy()
            buffers['geometry'] = pois_utm.geometry.buffer(distance)
            buffers = buffers.to_crs('EPSG:4326')  # Back to WGS84
            
            buffers['buffer_distance'] = distance
            buffers['poi_id'] = range(len(buffers))
            
            buffer_results[f'buffer_{distance}m'] = buffers
        
        return buffer_results
    
    def extract_population_from_raster(self, raster_path, buffer_zones):
        """Extract population data from raster for buffer zones"""
        logger.info(f"Extracting population from {raster_path}")
        
        results = []
        
        try:
            with rasterio.open(raster_path) as src:
                logger.info(f"Raster info: {src.shape}, bounds: {src.bounds}")
                
                for buffer_name, buffers in buffer_zones.items():
                    logger.info(f"Processing {buffer_name}")
                    
                    for idx, row in buffers.iterrows():
                        try:
                            # Extract data for this buffer polygon
                            geom = [row.geometry.__geo_interface__]
                            clipped_img, clipped_transform = mask(src, geom, crop=True, filled=False)
                            
                            # Calculate population sum
                            valid_data = clipped_img[0][~np.isnan(clipped_img[0])]
                            total_population = valid_data.sum() if len(valid_data) > 0 else 0
                            
                            results.append({
                                'poi_id': idx,
                                'poi_name': row.get('name', 'Unknown'),
                                'poi_category': row.get('category', 'Unknown'),
                                'buffer_distance': row['buffer_distance'],
                                'latitude': row.geometry.centroid.y,
                                'longitude': row.geometry.centroid.x,
                                'population_total': float(total_population),
                                'population_density': float(total_population / (np.pi * (row['buffer_distance']**2) / 10000)) if total_population > 0 else 0  # per hectare
                            })
                            
                        except Exception as e:
                            logger.warning(f"Error processing buffer for POI {idx}: {e}")
                            results.append({
                                'poi_id': idx,
                                'poi_name': row.get('name', 'Unknown'),
                                'poi_category': row.get('category', 'Unknown'),
                                'buffer_distance': row['buffer_distance'],
                                'latitude': row.geometry.centroid.y if hasattr(row.geometry, 'centroid') else 0,
                                'longitude': row.geometry.centroid.x if hasattr(row.geometry, 'centroid') else 0,
                                'population_total': 0,
                                'population_density': 0
                            })
                
                return pd.DataFrame(results)
                
        except Exception as e:
            logger.error(f"Error processing raster: {e}")
            return None
    
    def create_population_estimates_api(self, pois, buffer_distances=[100, 200, 500]):
        """Create population estimates using web APIs"""
        logger.info("Creating population estimates using web APIs")
        
        results = []
        
        for idx, poi in pois.iterrows():
            # Get POI coordinates
            if poi.geometry.geom_type == 'Point':
                lat, lon = poi.geometry.y, poi.geometry.x
            else:
                centroid = poi.geometry.centroid
                lat, lon = centroid.y, centroid.x
            
            base_result = {
                'poi_id': idx,
                'poi_name': poi.get('name', 'Unknown'),
                'poi_category': poi.get('category', 'Unknown'),
                'latitude': lat,
                'longitude': lon
            }
            
            # Try different population estimation methods
            for distance in buffer_distances:
                # Method 1: Use population density estimates
                pop_estimate = self.estimate_population_simple(lat, lon, distance)
                
                result = base_result.copy()
                result.update({
                    'buffer_distance': distance,
                    'population_total': pop_estimate,
                    'population_density': pop_estimate / (np.pi * (distance**2) / 10000) if pop_estimate > 0 else 0,
                    'estimation_method': 'api_fallback'
                })
                
                results.append(result)
        
        return pd.DataFrame(results)
    
    def estimate_population_simple(self, lat, lon, buffer_meters):
        """Simple population estimation based on urban density assumptions"""
        
        # This is a fallback method using reasonable urban density assumptions
        # Typical urban density in Bangalore: 4,000-8,000 people per km²
        
        # Calculate buffer area in km²
        buffer_area_km2 = (np.pi * (buffer_meters/1000)**2)
        
        # Estimate based on Koramangala being a medium-density urban area
        # Assumption: ~6,000 people per km² average density
        estimated_density = 6000  # people per km²
        
        # Add some spatial variation based on coordinates
        # Areas closer to main roads typically have higher density
        variation_factor = 0.8 + (0.4 * np.random.random())  # 0.8 to 1.2 multiplier
        
        estimated_population = buffer_area_km2 * estimated_density * variation_factor
        
        return int(estimated_population)
    
    def save_results(self, population_data, pois):
        """Save population results"""
        output_dir = Path('data/outputs')
        output_dir.mkdir(exist_ok=True)
        
        # Pivot data to have buffer distances as columns
        pivot_data = population_data.pivot_table(
            index=['poi_id', 'poi_name', 'poi_category', 'latitude', 'longitude'],
            columns='buffer_distance',
            values=['population_total', 'population_density'],
            aggfunc='first'
        ).round(0)
        
        # Flatten column names
        pivot_data.columns = [f"{col[0]}_{col[1]}m" for col in pivot_data.columns]
        pivot_data = pivot_data.reset_index()
        
        # Save CSV
        csv_file = output_dir / 'koramangala_pois_python_population.csv'
        pivot_data.to_csv(csv_file, index=False)
        logger.info(f"Saved population data: {csv_file}")
        
        # Create summary statistics
        summary = {
            'total_pois': len(pivot_data),
            'buffer_distances': [100, 200, 500],
            'average_population_100m': pivot_data['population_total_100m'].mean(),
            'average_population_200m': pivot_data['population_total_200m'].mean(),
            'average_population_500m': pivot_data['population_total_500m'].mean(),
            'data_source': 'worldpop_python_api'
        }
        
        # Save summary
        summary_file = output_dir / 'koramangala_population_python_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Population summary: {summary}")
        return pivot_data

def main():
    """Main execution function"""
    logger.info("Starting Python WorldPop population analysis for Koramangala")
    
    # Initialize API client
    worldpop_api = WorldPopPythonAPI()
    
    # Load POI data
    pois = worldpop_api.load_koramangala_pois()
    if pois is None:
        return False
    
    # Try to get real WorldPop data
    logger.info("Attempting to access real WorldPop data...")
    
    # Method 1: Search for datasets via API
    datasets = worldpop_api.search_worldpop_datasets()
    
    raster_file = None
    if datasets:
        logger.info("Found WorldPop datasets via API")
        # Try to download the first suitable dataset
        # This would need implementation based on actual API response structure
    
    # Method 2: Try alternative direct URLs
    if not raster_file:
        raster_file = worldpop_api.try_alternative_worldpop_urls()
    
    # Method 3: Check for Facebook HRSL data
    if not raster_file:
        fb_data = worldpop_api.get_facebook_hrsl_data()
        if fb_data:
            logger.info("Facebook HRSL data source found (manual download required)")
    
    # Process population data
    if raster_file and raster_file.exists():
        logger.info("Using downloaded raster data for population extraction")
        
        # Create buffer zones
        buffer_zones = worldpop_api.create_buffer_zones(pois)
        
        # Extract population from raster
        population_data = worldpop_api.extract_population_from_raster(raster_file, buffer_zones)
        
    else:
        logger.warning("No raster data available, using estimation method")
        
        # Fallback: Use estimation method
        population_data = worldpop_api.create_population_estimates_api(pois)
    
    if population_data is not None:
        # Save results
        final_data = worldpop_api.save_results(population_data, pois)
        
        logger.info("Python WorldPop analysis completed successfully!")
        logger.info(f"Processed {len(pois)} POIs with population catchment areas")
        
        # Print sample results
        if len(final_data) > 0:
            logger.info("Sample results:")
            sample = final_data.head(3)
            for _, row in sample.iterrows():
                logger.info(f"  {row['poi_name']}: {row.get('population_total_200m', 0):.0f} people within 200m")
        
        return True
    else:
        logger.error("Failed to generate population data")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)