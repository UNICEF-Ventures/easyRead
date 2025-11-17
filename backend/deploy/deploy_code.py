# from playground_python_commons.logger.Logger import Logger
import os
import zipfile
import boto3
from botocore.exceptions import NoCredentialsError

# initialize logger
# Logger()
# logger = Logger().get_logger()

def zip_folder(folder_path, zipf, file_exts_to_keep, is_recursive=True, keep_folder=True):
    """
    Zip selected files from folder_path into zipf with stable paths,
    regardless of current working directory.

    keep_folder=True -> include the top-level folder name in the archive.
    """
    base = os.path.abspath(folder_path)

    def should_keep(fname: str) -> bool:
        return fname.endswith(tuple(file_exts_to_keep))

    if is_recursive:
        walker = os.walk(base)
    else:
        walker = [(base, [], os.listdir(base))]

    for root, _, files in walker:
        for file in files:
            if not should_keep(file):
                continue
            file_path = os.path.join(root, file)
            rel = os.path.relpath(file_path, base)     # ← relative to folder being zipped
            # Optionally include the top-level folder name in the zip
            arcname = os.path.join(os.path.basename(base), rel) if keep_folder else rel
            zipf.write(file_path, arcname.replace(os.sep, "/"))  # normalize separators

def create_zip(zip_name, folder_path, dir_to_skip, file_exts_to_keep):
    """
    Zips specific folders and files into a zip archive.

    Args:
        zip_name (str): Name of the output zip file.
    """
    current_dir = folder_path
    # Create a zip file with compression
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # pandoc not present in source code
        
        # Step 1: Add .py files from the root directory (non-recursive)
        zip_folder(current_dir, zipf, file_exts_to_keep, is_recursive=False, keep_folder=False)

        # Step 2: Add subdirectories recursively (e.g., 'lambda-layer/')
        dirs = [e.name for e in os.scandir(current_dir) if e.is_dir()]
        for directory in dirs:
            if directory not in dir_to_skip:
                subfolder = os.path.join(current_dir, directory)
                if os.path.exists(subfolder):
                    zip_folder(subfolder, zipf, file_exts_to_keep, is_recursive=True, keep_folder=True)

        # lambda_entrypoint = 'lambda_function.py'
        # lambda_file = os.path.join(current_dir, 'deploy', 'lambda', lambda_dir, lambda_entrypoint)
        # if os.path.isfile(lambda_file):
        #     zipf.write(lambda_file, lambda_entrypoint)
   
    #logger.info(f"Files zipped successfully into '{zip_name}'.")

def upload(lambda_name, lambda_region, folder_path, dir_to_skip=['__pycache__','dependencies','deploy','tests','test','venv'], file_exts_to_keep=[".csv", ".py", ".yaml", ".yml", ".json"]):
    # Specify the zip file name
    file_name = lambda_name.replace(" ","").replace("-","_")
    zip_name = f'lambda_function_{file_name}.zip'
    #logger.info(f"Creating zip {zip_name}")
    
    if os.path.exists(zip_name):
        os.remove(zip_name)
    
    # Call the function to zip the folder
    create_zip(zip_name, folder_path, dir_to_skip, file_exts_to_keep)
        
    # Upload the zip file to AWS Lambda
    #upload_zip_to_lambda(zip_name, LAMBDA_FUNCTION_NAME)
    client = boto3.client('lambda', region_name=lambda_region)

    try:
        with open(zip_name, 'rb') as zip_file:
            zip_content = zip_file.read()

        response = client.update_function_code(
            FunctionName=lambda_name,
            ZipFile=zip_content
        )
        print(f"Successfully uploaded the zip to Lambda function '{lambda_name}'.")
        os.remove(zip_name)
        return response
    except NoCredentialsError:
        #logger.error("AWS credentials not available.")
        raise
    except Exception as e:
        #logger.error(f"An error occurred: {str(e)}")
        raise


import os

if __name__=="__main__":
    path = os.getcwd()
    upload("easyread-backend", "eu-north-1", path)
