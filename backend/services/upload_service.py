import cloudinary.uploader

def upload_to_cloudinary(file):
    result = cloudinary.uploader.upload(file)

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"]
    }