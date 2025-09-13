import requests
import rasterio
from rasterio.mask import mask
import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from shapely.geometry import box
import matplotlib.pyplot as plt
import zipfile
import os
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RealWorldPopProcessor:
    def __init__(self):
        # Updated URLs for WorldPop data
        self.base_url = "https://data.worldpop.org/GIS/"
        self.data_dir = Path("data/worldpop_real")
        self.data_dir.mkdir(exist_ok=True)
        
    def get_koramangala_bounds(self):
        """Get bounding box for Koramangala from POI data"""
        pois_file = 'data/processed/koramangala_pois.geojson'
        if not Path(pois_file).exists():
            logger.error(f"POI file not found: {pois_file}")
            return None
        
        pois = gpd.read_file(pois_file)
        bounds = pois.total_bounds
        
        # Add small buffer around the bounds
        buffer = 0.01  # roughly 1km
        bounds = [bounds[0] - buffer, bounds[1] - buffer,
                 bounds[2] + buffer, bounds[3] + buffer]
        
        logger.info(f"Koramangala bounds: {bounds}")
        return bounds
    
    def download_real_worldpop_data(self, year=2020):
        """Download actual WorldPop population data for India"""
        
        # Real WorldPop dataset URLs for India (updated for 2020)
        datasets = {
            'total_population': {
                'url': f"https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/maxar_v1/IND/ind_ppp_2020_UNadj_constrained.tif",
                'description': "Population count (constrained)"
            },
            'population_density': {
                'url': f"https://data.worldpop.org/GIS/PopDensity/Global_2000_2020_Constrained/2020/IND/ind_pd_2020_1km_UNadj.tif", 
                'description': "Population density per km²"
            }
        }
        
        downloaded_files = {}
        
        for dataset_name, dataset_info in datasets.items():
            output_file = self.data_dir / f"{dataset_name}_{year}.tif"
            
            if output_file.exists():
                # Check if file is reasonable size (>10MB for real data)
                file_size = output_file.stat().st_size / (1024*1024)  # MB
                if file_size > 10:
                    logger.info(f"Real data file already exists: {output_file} ({file_size:.1f}MB)")
                    downloaded_files[dataset_name] = output_file
                    continue
                else:
                    logger.warning(f"Existing file too small ({file_size:.1f}MB), re-downloading")
                    output_file.unlink()
            
            url = dataset_info['url']
            logger.info(f"Downloading {dataset_info['description']} from WorldPop...")
            logger.info(f"URL: {url}")
            
            try:
                # Check if URL exists
                response = requests.head(url, timeout=30)
                if response.status_code != 200:
                    logger.error(f"URL not accessible: {response.status_code}")
                    continue
                
                # Download with progress indication
                response = requests.get(url, stream=True, timeout=300)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                logger.info(f"Downloading {total_size/(1024*1024):.1f}MB...")
                
                downloaded = 0
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                if downloaded % (1024*1024*10) == 0:  # Log every 10MB
                                    logger.info(f"Progress: {progress:.1f}%")
                
                file_size = output_file.stat().st_size / (1024*1024)  # MB
                logger.info(f"Downloaded: {output_file} ({file_size:.1f}MB)")
                
                # Verify this is actually a GeoTIFF
                try:
                    with rasterio.open(output_file) as src:
                        logger.info(f"Verified GeoTIFF: {src.shape} pixels, CRS: {src.crs}")
                    downloaded_files[dataset_name] = output_file
                except Exception as e:
                    logger.error(f"Downloaded file is not a valid GeoTIFF: {e}")
                    output_file.unlink()
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to download {dataset_name}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error downloading {dataset_name}: {e}")
                continue
        
        if not downloaded_files:
            logger.error("No WorldPop data could be downloaded. Check internet connection and URLs.")
            return None
        
        return downloaded_files
    
    def get_alternative_data_sources(self):
        """Provide alternative data source suggestions if WorldPop fails"""
        alternatives = {
            "Facebook High Resolution Settlement Layer": {
                "url": "https://data.humdata.org/dataset/highresolutionpopulationdensitymaps-ind",
                "description": "Population density maps from Facebook"
            },
            "GPWv4 Population Density": {
                "url": "https://sedac.ciesin.columbia.edu/data/set/gpw-v4-population-density-rev11",
                "description": "Gridded Population of the World from SEDAC"
            },
            "LandScan Population": {
                "url": "https://landscan.ornl.gov/",
                "description": "Oak Ridge National Laboratory population data"
            },
            "Manual Download": {
                "url": "https://www.worldpop.org/geodata/summary?id=24777",
                "description": "Manual download from WorldPop website for India 2020"
            }
        }
        
        logger.info("Alternative population data sources:")
        for source, info in alternatives.items():
            logger.info(f"  {source}: {info['description']}")
            logger.info(f"    URL: {info['url']}")
        
        return alternatives
    
    def clip_real_data_to_koramangala(self, raster_files, bounds):
        """Clip real WorldPop rasters to Koramangala area"""
        
        if not raster_files:
            logger.error("No raster files to process")
            return None
        
        # Create bounding box geometry
        bbox_geom = [box(*bounds)]
        
        clipped_data = {}
        
        for dataset_name, file_path in raster_files.items():
            logger.info(f"Clipping {dataset_name} to Koramangala...")
            
            try:
                with rasterio.open(file_path) as src:
                    logger.info(f"Original raster info: {src.shape} pixels, bounds: {src.bounds}")
                    
                    # Check if our bounds intersect with the raster
                    if not src.bounds.left <= bounds[2] and src.bounds.bottom <= bounds[3] and \
                           src.bounds.right >= bounds[0] and src.bounds.top >= bounds[1]:
                        logger.error(f"Bounds do not intersect with raster: {src.bounds} vs {bounds}")
                        continue
                    
                    # Clip raster to bounds
                    clipped_img, clipped_transform = mask(src, bbox_geom, crop=True, filled=False)
                    
                    if clipped_img.size == 0:
                        logger.error(f"Clipping resulted in empty array for {dataset_name}")
                        continue
                    
                    clipped_meta = src.meta.copy()
                    
                    # Update metadata
                    clipped_meta.update({
                        "driver": "GTiff",
                        "height": clipped_img.shape[1],
                        "width": clipped_img.shape[2], 
                        "transform": clipped_transform
                    })
                    
                    # Save clipped raster
                    clipped_file = self.data_dir / f"koramangala_{dataset_name}_real.tif"
                    with rasterio.open(clipped_file, "w", **clipped_meta) as dest:
                        dest.write(clipped_img)
                    
                    clipped_data[dataset_name] = {
                        'file': clipped_file,
                        'data': clipped_img[0],  # Remove band dimension
                        'transform': clipped_transform,
                        'bounds': bounds,
                        'original_bounds': src.bounds,
                        'resolution': src.res
                    }
                    
                    # Log statistics
                    non_zero_cells = np.count_nonzero(clipped_img[0])
                    total_pop = np.sum(clipped_img[0][~np.isnan(clipped_img[0])])
                    
                    logger.info(f"Clipped {dataset_name}: {clipped_img.shape}")
                    logger.info(f"  Non-zero cells: {non_zero_cells}")
                    logger.info(f"  Total population: {total_pop:.0f}")
                    logger.info(f"  Resolution: {src.res[0]:.6f} degrees")
                    
            except Exception as e:
                logger.error(f"Error clipping {dataset_name}: {e}")
                continue
        
        return clipped_data
    
    def create_poi_population_analysis(self, clipped_data):
        """Extract real population data around each POI location"""
        
        if not clipped_data:
            logger.error("No clipped population data available")
            return None
        
        # Load POI data
        pois = gpd.read_file('data/processed/koramangala_pois.geojson')
        
        poi_population_data = []
        
        for idx, poi in pois.iterrows():
            # Get POI coordinates
            if poi.geometry.geom_type == 'Point':
                poi_x, poi_y = poi.geometry.x, poi.geometry.y
            else:
                centroid = poi.geometry.centroid
                poi_x, poi_y = centroid.x, centroid.y
            
            poi_data = {
                'poi_id': idx,
                'poi_name': poi.get('name', 'Unknown'),
                'poi_category': poi.get('category', 'Unknown'),
                'latitude': poi_y,
                'longitude': poi_x
            }
            
            # Extract population data from each raster
            for dataset_name, data_info in clipped_data.items():
                try:
                    transform = data_info['transform']
                    col, row = ~transform * (poi_x, poi_y)
                    col, row = int(col), int(row)
                    
                    data = data_info['data']
                    
                    # Get population value at POI location
                    if 0 <= row < data.shape[0] and 0 <= col < data.shape[1]:
                        pop_value = data[row, col]
                        if np.isnan(pop_value):
                            pop_value = 0
                        poi_data[f'{dataset_name}_at_location'] = float(pop_value)
                        
                        # Calculate population in buffer area
                        # Buffer size depends on resolution
                        resolution = data_info['resolution'][0]  # degrees
                        buffer_cells = max(1, int(0.002 / resolution))  # ~200m buffer
                        
                        r_min = max(0, row - buffer_cells)
                        r_max = min(data.shape[0], row + buffer_cells + 1)
                        c_min = max(0, col - buffer_cells)
                        c_max = min(data.shape[1], col + buffer_cells + 1)
                        
                        buffer_data = data[r_min:r_max, c_min:c_max]
                        buffer_sum = np.sum(buffer_data[~np.isnan(buffer_data)])
                        poi_data[f'{dataset_name}_in_buffer'] = float(buffer_sum)
                    else:
                        poi_data[f'{dataset_name}_at_location'] = 0.0
                        poi_data[f'{dataset_name}_in_buffer'] = 0.0
                        
                except Exception as e:
                    logger.warning(f"Error extracting {dataset_name} for POI {idx}: {e}")
                    poi_data[f'{dataset_name}_at_location'] = 0.0
                    poi_data[f'{dataset_name}_in_buffer'] = 0.0
            
            poi_population_data.append(poi_data)
        
        return pd.DataFrame(poi_population_data)

def main():
    """Main processing function with real data only"""
    logger.info("Starting REAL WorldPop data integration for Koramangala")
    logger.info("This script will only use actual WorldPop data - no simulated fallbacks")
    
    # Initialize processor
    processor = RealWorldPopProcessor()
    
    # Get Koramangala bounds
    bounds = processor.get_koramangala_bounds()
    if bounds is None:
        return False
    
    # Download real WorldPop data
    logger.info("Attempting to download real WorldPop data...")
    raster_files = processor.download_real_worldpop_data(year=2020)
    
    if not raster_files:
        logger.error("Failed to download any real WorldPop data")
        logger.info("Consider these alternatives:")
        processor.get_alternative_data_sources()
        return False
    
    # Clip to Koramangala area
    logger.info("Clipping real data to Koramangala area...")
    clipped_data = processor.clip_real_data_to_koramangala(raster_files, bounds)
    
    if not clipped_data:
        logger.error("Failed to clip any data to Koramangala area")
        return False
    
    # Create POI-population dataset with real data
    logger.info("Extracting real population data for POI locations...")
    poi_pop_data = processor.create_poi_population_analysis(clipped_data)
    
    if poi_pop_data is None:
        logger.error("Failed to create POI population analysis")
        return False
    
    # Save POI population data
    output_file = 'data/outputs/koramangala_pois_with_REAL_population.csv'
    poi_pop_data.to_csv(output_file, index=False)
    logger.info(f"Real POI population data saved: {output_file}")
    
    # Create summary
    summary = {}
    for dataset_name, data_info in clipped_data.items():
        data = data_info['data']
        summary[dataset_name] = {
            'total_population': float(np.sum(data[~np.isnan(data)])),
            'max_density': float(np.max(data[~np.isnan(data)])),
            'mean_density': float(np.mean(data[~np.isnan(data)])),
            'resolution_degrees': data_info['resolution'][0],
            'resolution_meters': data_info['resolution'][0] * 111000  # approximate
        }
    
    # Save summary
    summary_file = 'data/outputs/koramangala_REAL_population_summary.json'
    import json
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    # Print results
    logger.info("REAL Population Data Analysis Summary:")
    for dataset_name, stats in summary.items():
        logger.info(f"  {dataset_name}:")
        logger.info(f"    Total population: {stats['total_population']:.0f}")
        logger.info(f"    Resolution: {stats['resolution_meters']:.0f}m")
        logger.info(f"    Max density: {stats['max_density']:.1f}")
    
    logger.info(f"Real population data integration complete!")
    logger.info(f"Files created:")
    logger.info(f"  - {output_file}")
    logger.info(f"  - {summary_file}")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        logger.error("Failed to process real WorldPop data")
        logger.info("You may need to manually download data from worldpop.org")
        exit(1)