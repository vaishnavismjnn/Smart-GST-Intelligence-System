from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Secure connection - no hardcoded passwords!
client = MongoClient(os.getenv("MONGO_URI"))

db = client["invoice_db"]
collection = db["invoices"]

dataset_root = "Datasets"

def upload_images():
    for root, dirs, files in os.walk(dataset_root):
        for file in files:
            if file.endswith((".png", ".jpg", ".jpeg")):
                file_path = os.path.join(root, file)

                with open(file_path, "rb") as f:
                    image_data = f.read()

                doc = {
                    "filename": file,
                    "path": file_path,
                    "source_folder": root,
                }

                collection.insert_one(doc)
                print(f"Uploaded: {file}")

upload_images()
print("✅ ALL DATA UPLOADED SUCCESSFULLY")