from flask import Flask, request, jsonify, render_template
import requests
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_UPLOAD_URL = "https://api.openai.com/v1/files"
OPENAI_RETRIEVE_CONTENT_URL = "https://api.openai.com/v1/files/{file_id}/content"

GCLOUD_PATH = '/tmp/uploads'

UPLOAD_FOLDER = os.path.join(os.getcwd(), GCLOUD_PATH)
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Create the upload folder if it doesn't exist
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            file.save(filepath)
            
            # Get the purpose from form data, default to 'assistants'
            purpose = request.form.get('purpose', 'assistants')
            
            # Process the file with OpenAI
            result, status_code = process_file_with_openai(filepath, filename, purpose)
            
            # Add local file info to the response
            result['local_filename'] = filename
            result['local_filepath'] = filepath
            
            return jsonify(result), status_code
        else:
            return jsonify({"error": "File type not allowed"}), 400
    return jsonify({"message": "Please use POST method to upload files"}), 400


if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)