from pymongo import MongoClient
import os

# 🔴 PASTE YOUR CONNECTION STRING HERE
client = MongoClient("mongodb+srv://shanthalamn63_db:Shanthala123@newcluster.pknmchg.mongodb.net/?retryWrites=true&w=majority&appName=NewCluster")

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