import os
import os

import boto3
import shutil
import subprocess
import zipfile
from pathlib import Path
from botocore.exceptions import NoCredentialsError

# initialize logger
# Logger()
# logger = Logger().get_logger()

def create_zip(zip_file, python_version = "3.10", requirements_file = Path("requirements.txt"), folder_path=os.getcwd()):        
    
    venv_dir = os.path.join(folder_path, "venv_lambda")
    target_dir = os.path.join(folder_path, "python")
    t_dir = os.path.join(target_dir, "lib")
    lib_path = os.path.join(venv_dir, "lib", f"python{python_version}" , "site-packages")
    m_path = os.path.join(venv_dir , "lib")

    # Step 1: Clean up old env and dirs
    print("Cleaning up old environment and folders...")
    shutil.rmtree(target_dir, ignore_errors=True)
    shutil.rmtree(venv_dir, ignore_errors=True)
    #zip_file.unlink(missing_ok=True)

    # Step 2: Create virtual environment
    print(f"Creating virtual environment with Python {python_version}...")
    subprocess.run([f"python{python_version}", "-m", "venv", str(venv_dir)], check=True)
    #subprocess.run([f"{venv_dir}/bin/activate"], check=True)
    # Step 3: Install packages into site-packages
    print("Installing dependencies to site-packages...")
    pip_path = os.path.join(venv_dir , "bin" , "pip")
    print(f"dff {pip_path} {requirements_file}")
    pip_install_cmd = [
        str(pip_path),
        "install",
        "-r", str(requirements_file),
        "--no-cache-dir",
        "--platform", "manylinux2014_x86_64",
        "--only-binary", ":all:",
        "--target", str(lib_path)
    ]
    
    subprocess.run(pip_install_cmd, check=True)

    # Step 4: Copy lib folder to ./python
    print("Copying packages to 'python/'...")
    shutil.copytree(m_path, t_dir, dirs_exist_ok=True)

    # Step 5: Zip the layer
    print("Zipping into layer_content.zip...")
    # with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as z:
    #     for path in target_dir.rglob("*"):
    #         z.write(path, path.relative_to(target_dir.parent))
    target_path = Path(target_dir)   # <- convert to Path
    zip_path = Path(zip_file)        # (optional) normalize too

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in target_path.rglob("*"):
            if path.is_file():
                z.write(path, arcname=str(path.relative_to(target_path.parent)))
            
    print("Lambda layer package created.")
    
    # remove 
    shutil.rmtree(venv_dir, ignore_errors=True)
    shutil.rmtree(target_dir, ignore_errors=True)

def upload(layer_name, layer_region, folder_path, compatible_runtimes = ["python3.10"], python_version = "3.10", requirements_file = Path("requirements.txt"), description = "", lambda_function=None, lambda_region=None):
    try:
        # Specify the zip file name
        file_name = layer_name.replace(" ","").replace("-","_")
        zip_name = f'lambda_layer_{file_name}.zip'
        print(f"Creating zip {zip_name}")
        
        # create layer zip file
        create_zip(zip_name, python_version, requirements_file, folder_path)

        # --- Upload ---
        lambda_client = boto3.client("lambda", region_name=layer_region)
        with open(zip_name, "rb") as f:
            zipped_bytes = f.read()

        response = lambda_client.publish_layer_version(
            LayerName=layer_name,
            Description=description,
            Content={"ZipFile": zipped_bytes},
            CompatibleRuntimes=compatible_runtimes
        )

        print(f"Layer uploaded. Layer ARN: {response['LayerVersionArn']}")
    except NoCredentialsError:
        print("AWS credentials not available.")
        raise
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise

if __name__=="__main__":
    # dividing file into 2 parts to overcome 50MB limit
    folder_path = os.getcwd()
    requirments_file_path = os.path.join(os.getcwd(),"dependencies","requirements_1.txt")
    upload("easyread-layer-1", "eu-north-1", requirements_file=requirments_file_path, folder_path=folder_path)
    
    requirments_file_path = os.path.join(os.getcwd(),"dependencies","requirements_2.txt")
    upload("easyread-layer-2", "eu-north-1", requirements_file=requirments_file_path, folder_path=folder_path)