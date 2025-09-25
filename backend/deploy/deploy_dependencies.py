import os
from playground_python_commons.deploy_lambda.deploy_lambda_layer import upload

if __name__=="__main__":
    # dividing file into 2 parts to overcome 50MB limit
    folder_path = os.getcwd()
    requirments_file_path = os.path.join(os.getcwd(),"dependencies","requirements_1.txt")
    upload("easy-read-layer-1", "eu-north-1", requirements_file=requirments_file_path, folder_path=folder_path)
    
    requirments_file_path = os.path.join(os.getcwd(),"dependencies","requirements_2.txt")
    upload("easy-read-layer-2", "eu-north-1", requirements_file=requirments_file_path, folder_path=folder_path)