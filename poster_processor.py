import os
import re
import sys
import time
import requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# --- CORE CONFIGURATION (Pulled from Environment Variables) ---

# Mandatory API Key
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
if not TMDB_API_KEY:
    print("FATAL: TMDB_API_KEY environment variable not set. Exiting.")
    sys.exit(1)

# Main container variables
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "/app/data"))
# RESTORE_MODE: If True, copies original_poster.jpg to poster.jpg and exits
RESTORE_MODE = os.environ.get("RESTORE_MODE", "false").lower() == "true" 
MIN_VOTE_COUNT = int(os.environ.get("MIN_VOTE_COUNT", 500))

# --- STAGE 1: POSTER DOWNLOAD CONFIG ---
# TMDb URLs
TMDB_BASE_URL = "https://api.themoviedb.org/3/movie/"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/"
IMAGE_SIZE_PATH = "original" 
TARGET_SIZE = (1000, 1500)
TMDB_ID_REGEX = re.compile(r"\[tmdbid-(\d+)\]", re.IGNORECASE)
ORIGINAL_FOLDER_NAME = "original"
ORIGINAL_POSTER_NAME = "original_poster.jpg"
FINAL_POSTER_NAME = "poster.jpg"

# --- STAGE 2/3/4: OVERLAY CONFIG ---
# 1. Static Gradient/Logo Overlay
APPLY_STATIC_OVERLAY = os.environ.get("APPLY_STATIC_OVERLAY", "false").lower() == "true"
STATIC_OVERLAY_PATH = os.environ.get("STATIC_OVERLAY_PATH", "/app/overlays/static_overlay.png")

# 2. Dynamic TMDb Rating Overlay
APPLY_TMDB_RATING = os.environ.get("APPLY_TMDB_RATING", "false").lower() == "true"
TMDB_OVERLAY_DIR = Path(os.environ.get("TMDB_OVERLAY_DIR", "/app/overlays/tmdb_ratings"))

# 3. Dynamic IMDb Rating Overlay
APPLY_IMDB_RATING = os.environ.get("APPLY_IMDB_RATING", "false").lower() == "true"

# --- PLEX REFRESH CONFIG ---
PLEX_REFRESH = os.environ.get("PLEX_REFRESH", "false").lower() == "true"
PLEX_IP = os.environ.get("PLEX_IP")
PLEX_PORT = os.environ.get("PLEX_PORT")
PLEX_TOKEN = os.environ.get("PLEX_TOKEN")
# PLEX_LIBRARY_ID: Now supports comma-separated list
PLEX_LIBRARY_IDS = [id.strip() for id in os.environ.get("PLEX_LIBRARY_ID", "").split(',') if id.strip()]


# --- HELPER FUNCTIONS ---

def get_movie_details(tmdb_id: int):
    """Fetches full movie details from TMDb."""
    detail_url = f"{TMDB_BASE_URL}{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=external_ids"
    try:
        response = requests.get(detail_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"   [ERROR] Failed to fetch details for ID {tmdb_id}: {e}")
        return None

def fetch_poster(tmdb_id: int, movie_path: Path):
    """Downloads and saves the original poster."""
    output_dir = movie_path / ORIGINAL_FOLDER_NAME
    output_file = output_dir / ORIGINAL_POSTER_NAME

    if output_file.exists():
        return True # Poster already downloaded

    data = get_movie_details(tmdb_id)
    if not data:
        return False

    poster_path_suffix = data.get("poster_path")
    if not poster_path_suffix:
        print(f"   [WARN] No poster_path found for TMDb ID {tmdb_id}.")
        return False

    image_url = f"{TMDB_IMAGE_BASE_URL}{IMAGE_SIZE_PATH}{poster_path_suffix}"
    print(f"   -> Downloading original image from: {image_url}")

    try:
        image_response = requests.get(image_url, stream=True, timeout=20)
        image_response.raise_for_status()
        
        image = Image.open(BytesIO(image_response.content))
        
        output_dir.mkdir(parents=True, exist_ok=True)

        # Resize and save
        resized_image = image.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        resized_image.save(output_file, "JPEG", quality=90)
        print(f"   [SUCCESS] Saved original poster to: {output_file.name}")
        return True

    except Exception as e:
        print(f"   [ERROR] Could not process or save image for {movie_path.name}: {e}")
        return False

def apply_imdb_rating_overlay(base_img: Image.Image, tmdb_id: int, movie_path: Path) -> Image.Image:
    """Fetches TMDb rating and draws the yellow box overlay (styled as IMDb)."""
    print("   -> Fetching IMDb rating...")
    
    # ... (rating fetch and check logic remains the same)

    # Use TMDb rating rounded to one decimal place for display
    imdb_rating = round(vote_average, 1) 
    rating_text = f"{imdb_rating}"
    
    # Define box dimensions and font
    width, height = base_img.size
    box_size = (180, 80) # Keep box size consistent or adjust if needed
    padding = 20
    
    # Bottom Right position
    x0 = width - box_size[0] - padding
    y0 = height - box_size[1] - padding
    x1 = width - padding
    y1 = height - padding
    
    # Create a transparent layer for drawing
    overlay = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # 1. Draw the yellow box (IMDb color)
    draw.rectangle([x0, y0, x1, y1], fill=(245, 197, 24, 255)) # IMDb Yellow

    # 2. Draw the text
    try:
        # FONT SIZE CHANGED TO 80
        font_rating = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
    except IOError:
        print("   [WARN] Default font not found, using generic font.")
        font_rating = ImageFont.load_default()
    
    # FIX: Use textbbox to find exact text size for centering
    try:
        # Calculate text bounding box (left, top, right, bottom)
        bbox = draw.textbbox((0, 0), rating_text, font=font_rating)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception as e:
        print(f"   [ERROR] Failed to calculate text dimensions using textbbox: {e}")
        text_w = box_size[0] * 0.5
        text_h = box_size[1] * 0.5
    
    # FIX: Centering Calculation - Use the box center point for vertical centering
    
    # Calculate box center coordinates
    box_center_x = x0 + box_size[0] / 2
    box_center_y = y0 + box_size[1] / 2
    
    # Position text based on its size relative to the box center
    text_x = box_center_x - (text_w / 2)
    text_y = box_center_y - (text_h / 2)
    
    # Adjust for Pillow's baseline issue (adds a small offset to visually center)
    # This value is often necessary when dealing with large fonts
    baseline_offset = 5 
    text_y += baseline_offset 
    
    draw.text((text_x, text_y), rating_text, font=font_rating, fill=(0, 0, 0, 255))
    
    # Composite the overlay onto the base image
    base_img.alpha_composite(overlay)
    print(f"   [SUCCESS] Applied IMDb-style rating: {rating_text}")
    return base_img

def process_movie_folder(movie_path: Path, tmdb_id: int):
    """Runs the full processing pipeline for one movie."""
    print("-" * 40)
    print(f"Found movie folder: {movie_path.name}")
    
    original_poster_path = movie_path / ORIGINAL_FOLDER_NAME / ORIGINAL_POSTER_NAME
    final_poster_path = movie_path / FINAL_POSTER_NAME
    
    # 1. POSTER DOWNLOAD (if needed)
    if not fetch_poster(tmdb_id, movie_path):
        return # Skip if download failed

    # 2. LOAD BASE IMAGE (The original poster for all subsequent processing)
    try:
        # Load the base image and prepare for compositing
        base_img = Image.open(original_poster_path).convert("RGBA")
    except Exception as e:
        print(f"   [FATAL] Could not load base image {original_poster_path}: {e}")
        return

    # --- APPLY OVERLAYS IN ORDER ---
    
    # 3. OVERLAY 1: STATIC GRADIENT/LOGO
    if APPLY_STATIC_OVERLAY:
        print("   -> Applying Static Overlay...")
        if not Path(STATIC_OVERLAY_PATH).is_file():
            print(f"   [FATAL] Static overlay file not found at {STATIC_OVERLAY_PATH}. Skipping static overlay.")
        else:
            try:
                overlay_img = Image.open(STATIC_OVERLAY_PATH).convert("RGBA")
                if base_img.size != overlay_img.size:
                    overlay_img = overlay_img.resize(base_img.size, Image.Resampling.LANCZOS)
                base_img.alpha_composite(overlay_img)
                print("   [SUCCESS] Static overlay applied.")
            except Exception as e:
                print(f"   [ERROR] Failed to apply static overlay: {e}")

    # 4. OVERLAY 2: DYNAMIC TMDB RATING
    if APPLY_TMDB_RATING:
        print("   -> Determining and applying TMDb Rating Overlay...")
        data = get_movie_details(tmdb_id)
        if data:
            vote_average = data.get("vote_average", 0.0)
            vote_count = data.get("vote_count", 0)
            
            if vote_count < MIN_VOTE_COUNT:
                 print(f"   [INFO] TMDb vote count ({vote_count}) below threshold ({MIN_VOTE_COUNT}). Skipping TMDb overlay.")
            else:
                rating_percent = max(0, min(100, int(round(vote_average * 10))))
                overlay_filename = f"r{rating_percent}.png"
                overlay_path = TMDB_OVERLAY_DIR / overlay_filename
                
                if not overlay_path.is_file():
                    print(f"   [FATAL] TMDb overlay file not found: {overlay_filename} in {TMDB_OVERLAY_DIR}. Skipping TMDb overlay.")
                else:
                    try:
                        overlay_img = Image.open(overlay_path).convert("RGBA")
                        if base_img.size != overlay_img.size:
                            overlay_img = overlay_img.resize(base_img.size, Image.Resampling.LANCZOS)
                        base_img.alpha_composite(overlay_img)
                        print(f"   [SUCCESS] Applied TMDb rating overlay: {rating_percent}%.")
                    except Exception as e:
                        print(f"   [ERROR] Failed to apply TMDb rating overlay: {e}")

    # 5. OVERLAY 3: DYNAMIC IMDB RATING (Yellow Box)
    if APPLY_IMDB_RATING:
        base_img = apply_imdb_rating_overlay(base_img, tmdb_id, movie_path)

    # 6. SAVE FINAL POSTER
    try:
        # Convert final composite image back to RGB/JPEG
        final_image = base_img.convert("RGB")
        final_image.save(final_poster_path, "JPEG", quality=95)
        print(f"   [FINAL] Saved final poster to: {final_poster_path.name}")
    except Exception as e:
        print(f"   [ERROR] Failed to save final poster for {movie_path.name}: {e}")

def run_plex_refresh():
    """Triggers a library scan on Plex via API for one or more library IDs."""
    if not PLEX_REFRESH or not PLEX_IP or not PLEX_PORT or not PLEX_TOKEN or not PLEX_LIBRARY_IDS:
        print("[WARN] Plex Refresh is enabled but connection details are incomplete. Skipping refresh.")
        return
    
    print("Attempting Plex Library Refresh...")

    for library_id in PLEX_LIBRARY_IDS:
        plex_url = f"http://{PLEX_IP}:{PLEX_PORT}/library/sections/{library_id}/refresh?X-Plex-Token={PLEX_TOKEN}"
        print(f"   -> Triggering refresh for section ID: {library_id}")
        
        try:
            response = requests.get(plex_url, timeout=15)
            response.raise_for_status()
            print(f"   [SUCCESS] Plex refresh initiated for ID {library_id}.")
        except requests.exceptions.RequestException as e:
            print(f"   [ERROR] Failed to call Plex refresh API for ID {library_id}: {e}")

def restore_posters():
    """Restores poster.jpg from original/original_poster.jpg."""
    print("=" * 40)
    print("!!! RESTORE MODE ACTIVATED !!!")
    
    found_restores = 0
    # ... (rest of the restore_posters function remains the same)
    for movie_path in MEDIA_ROOT.rglob('*'):
        if movie_path.is_dir() and movie_path.name.lower() != ORIGINAL_FOLDER_NAME:
            source = movie_path / ORIGINAL_FOLDER_NAME / ORIGINAL_POSTER_NAME
            target = movie_path / FINAL_POSTER_NAME
            
            if source.is_file():
                try:
                    import shutil
                    shutil.copyfile(source, target)
                    print(f"   [RESTORE] Copied {source.name} to {target.name} for: {movie_path.name}")
                    found_restores += 1
                except Exception as e:
                    print(f"   [ERROR] Failed to restore for {movie_path.name}: {e}")
            else:
                pass # No original poster, nothing to restore
                
    print("=" * 40)
    print(f"Restore finished. Restored {found_restores} posters.")
    print("=" * 40)
    
def main():
    """Main execution function."""
    
    if not MEDIA_ROOT.is_dir():
        print(f"FATAL: The mounted directory {MEDIA_ROOT} does not exist.")
        sys.exit(1)
        
    if RESTORE_MODE:
        restore_posters()
        if PLEX_REFRESH:
            run_plex_refresh()
        return

    print("=" * 40)
    print(f"Starting Consolidated Poster Processor in root directory: {MEDIA_ROOT}")
    print("=" * 40)

    found_movies = 0
    
    # Find all movie folders
    for movie_path in MEDIA_ROOT.rglob('*'):
        if movie_path.is_dir() and movie_path.name.lower() != ORIGINAL_FOLDER_NAME:
            match = TMDB_ID_REGEX.search(movie_path.name)
            
            if match:
                found_movies += 1
                tmdb_id = int(match.group(1))
                
                # Check for minimum requirements for IMDB rating overlay (Font)
                if APPLY_IMDB_RATING:
                    if not Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf").is_file():
                        print("[FATAL] Font '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' required for IMDB overlay is missing. Please use a Python image with fonts installed or disable IMDB overlay.")
                        sys.exit(1)

                process_movie_folder(movie_path, tmdb_id)
                time.sleep(0.5) # Be kind to the TMDb API rate limits

    print("=" * 40)
    print(f"Scan finished. Processed {found_movies} movie folders.")
    
    if PLEX_REFRESH:
        run_plex_refresh()
        
    print("=" * 40)

if __name__ == "__main__":
    main()
