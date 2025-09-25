import os
from playground_python_commons.deploy_lambda.deploy_lambda_code import upload

if __name__=="__main__":
    path = os.getcwd()
    upload("easyread-backend", "eu-north-1", path)