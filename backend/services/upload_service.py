import cloudinary.uploader

def upload_to_cloudinary(file, public_id):
    result = cloudinary.uploader.upload(
        file,
        public_id=public_id,
        overwrite=False
    )

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"]
    }