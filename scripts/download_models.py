import os
import httpx

# Directory where models will be stored
MODEL_DIR = "/app/models"

# URLs for the model files to download
MODEL_URLS = {
    "mistral-7b-instruct-v0.2.Q4_K_M.gguf": "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
    "codellama-7b.Q4_K_M.gguf": "https://huggingface.co/TheBloke/CodeLlama-7B-GGUF/resolve/main/codellama-7b.Q4_K_M.gguf",
    "llava-v1.5-7b-Q4_K.gguf": "https://huggingface.co/mys/ggml_llava-v1.5-7b/resolve/main/ggml-model-Q4_K.gguf",
    "mmproj-model-f16.gguf": "https://huggingface.co/mys/ggml_llava-v1.5-7b/resolve/main/mmproj-model-f16.gguf"
}

def download_file(url, filename, destination_dir):
    """Download a file from a URL to the specified directory."""
    destination_path = os.path.join(destination_dir, filename)
    
    # Check if file already exists and is of expected size
    expected_sizes = {
        "mistral-7b-instruct-v0.2.Q4_K_M.gguf": 4.4 * 1024 * 1024 * 1024,  # ~4.4GB
        "codellama-7b.Q4_K_M.gguf": 4.1 * 1024 * 1024 * 1024,              # ~4.1GB
        "llava-v1.5-7b-Q4_K.gguf": 4.0 * 1024 * 1024 * 1024,               # ~4.0GB
        "mmproj-model-f16.gguf": 0.5 * 1024 * 1024 * 1024                  # ~0.5GB
    }
    
    if os.path.exists(destination_path):
        file_size = os.path.getsize(destination_path)
        if filename in expected_sizes and file_size >= expected_sizes[filename] * 0.9:  # Allow 10% variance
            print(f"File {filename} already exists and is of sufficient size ({file_size / (1024*1024)} MB). Skipping download.")
            return
        else:
            print(f"File {filename} exists but is too small ({file_size / (1024*1024)} MB). Redownloading.")

    print(f"Downloading {filename} from {url}...")
    with httpx.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        downloaded_size = 0
        
        with open(destination_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=1024*1024):
                f.write(chunk)
                downloaded_size += len(chunk)
                if total_size > 0:
                    percent = (downloaded_size / total_size) * 100
                    print(f"\rDownloading {filename}: {percent:.1f}% ({downloaded_size / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB)", end="")
                else:
                    print(f"\rDownloading {filename}: {downloaded_size / (1024*1024):.1f} MB downloaded", end="")
        print(f"\nDownload of {filename} completed.")

def main():
    """Main function to download model files."""
    # Create model directory if it doesn't exist
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    print(f"Downloading models to {MODEL_DIR}")
    for model_name, model_url in MODEL_URLS.items():
        download_file(model_url, model_name, MODEL_DIR)
    print("All model downloads completed.")

if __name__ == "__main__":
    main()
