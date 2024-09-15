from flask import Flask, request, jsonify, render_template
import requests
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

OPENAI_API_KEY = "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"
OPENAI_UPLOAD_URL = "https://api.openai.com/v1/files"
OPENAI_RETRIEVE_CONTENT_URL = "https://api.openai.com/v1/files/{file_id}/content"

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# iLovePDF API keys
PUBLIC_KEY = 'project_public_82dab4b6a689ce7ffc4b62cfa15e1b8a_bZSLIfc826f70e0379aea86fd24c5202db7f9'
SECRET_KEY = 'secret_key_8b30519731ee08742205ab40eec2ab78_JMsbM672f6a8ac23d7273fd9b92f65d2a973d'

# iLovePDF API endpoint
API_URL = 'https://api.ilovepdf.com/v1/start'

# Function to upload PDF and convert to PNG using iLovePDF

@app.route('/convert', methods=['GET', 'POST'])
def convert_pdf_to_png(pdf_path):
    API_URL = 'https://api.ilovepdf.com/v1/start'

    # Start a task for image conversion
    response = requests.post(
        API_URL, 
        json={"task": "imagepdf"}, 
        headers={"Authorization": f"Bearer {PUBLIC_KEY}"}
    )
    
    task_data = response.json()
    task_id = task_data['server_filename']

    # Upload the PDF file
    files = {
        'file': open(pdf_path, 'rb')
    }
    upload_url = f'https://{task_data["server"]}/v1/upload'
    requests.post(upload_url, files=files, headers={"Authorization": f"Bearer {PUBLIC_KEY}"})

    # Execute the task to convert to PNG
    process_url = f'https://{task_data["server"]}/v1/process'
    requests.post(process_url, json={"task": task_id, "output": "png"}, headers={"Authorization": f"Bearer {PUBLIC_KEY}"})

    # Download the converted PNG
    download_url = f'https://{task_data["server"]}/v1/download'
    download_response = requests.get(download_url, stream=True, headers={"Authorization": f"Bearer {PUBLIC_KEY}"})

    # Save the PNG file locally
    output_file = os.path.splitext(pdf_path)[0] + '.png'
    with open(output_file, 'wb') as f:
        for chunk in download_response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

    return output_file

@app.route('/process', methods=['GET', 'POST'])
def process_file_with_openai(filepath, filename, purpose):
    try:
        # Upload file to OpenAI
        with open(filepath, "rb") as file_to_upload:
            openai_upload_response = requests.post(
                OPENAI_UPLOAD_URL,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": (filename, file_to_upload), "purpose": (None, purpose)}
            )
        
        if openai_upload_response.status_code != 200:
            raise Exception(f"File upload to OpenAI failed: {openai_upload_response.text}")
        
        file_id = openai_upload_response.json()['id']
        
        response_data = {
            "message": "File processed successfully",
            "file_id": file_id,
            "purpose": purpose
        }
        

        # Only try to retrieve content if purpose allows it
        if purpose != 'assistants':
            try:
                openai_retrieve_response = requests.get(
                    OPENAI_RETRIEVE_CONTENT_URL.format(file_id=file_id),
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
                )
                
                if openai_retrieve_response.status_code == 200:
                    file_content = openai_retrieve_response.content
                    content_preview = file_content[:100].decode('utf-8', errors='ignore')
                    response_data["content_preview"] = content_preview
                else:
                    response_data["retrieval_note"] = "Content retrieval not allowed or failed"
            except Exception as retrieval_error:
                response_data["retrieval_error"] = str(retrieval_error)
        else:
            response_data["retrieval_note"] = "Content retrieval not attempted for 'assistants' purpose"
        
        return response_data, 200
        
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/upload', methods=['GET', 'POST'])
def upload_and_process_file():
    if request.method == 'POST':
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        
        # Check if a file is selected
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        if file and allowed_file(file.filename):
            # Secure the filename and save to the uploads folder
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Convert the PDF to PNG
            try:
                png_file_path = convert_pdf_to_png(filepath)
                            # Process the PNG file with OpenAI after conversion
                purpose = request.form.get('purpose', 'assistants')  # Optionally get 'purpose'
                result, status_code = process_file_with_openai(png_file_path, filename, purpose)
            
                return jsonify({"message": "File converted successfully", "image_path": png_file_path}), 200
            except Exception as e:
                return jsonify({"error": f"Conversion failed: {str(e)}"}), 500
        else:
            return jsonify({"error": "File type not allowed"}), 400

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)