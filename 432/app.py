from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import datetime
import os
import json
from PIL import Image, ImageFilter
import io
import base64
import uuid

app = Flask(__name__)

# Configuration
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET', 'super-secret-key')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'flask-super-secret-key')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

jwt = JWTManager(app)

# In-memory user storage
users = {
    "user1": {"password": "password1", "role": "user"},
    "admin1": {"password": "adminpass", "role": "admin"}
}

# Simple in-memory data storage
tasks = {}
files = {}

# Web interface routes
@app.route('/')
def index():
    return render_template('index.html', token=session.get('token'), current_user=session.get('username'))

@app.route('/web/login', methods=['POST'])
def web_login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if username in users and users[username]['password'] == password:
        # Create JWT token
        access_token = create_access_token(
            identity=username,
            expires_delta=datetime.timedelta(hours=24)
        )
        session['token'] = access_token
        session['username'] = username
        return redirect(url_for('index'))
    else:
        return render_template('index.html', error="Invalid credentials")

@app.route('/web/logout')
def web_logout():
    session.pop('token', None)
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/web/test-endpoints')
@jwt_required()
def web_test_endpoints():
    current_user = get_jwt_identity()
    return render_template('index.html', 
                         token=session.get('token'),
                         current_user=current_user,
                         test_results={"message": "Ready to test endpoints"})

# API routes
@app.route('/api/')
def api_root():
    return jsonify({"message": "Welcome to the CAB432 API Server"})

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    if not request.is_json:
        return jsonify({"msg": "Missing JSON in request"}), 400
        
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    
    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400
        
    if username not in users or users[username]['password'] != password:
        return jsonify({"msg": "Bad username or password"}), 401
        
    access_token = create_access_token(
        identity=username,
        expires_delta=datetime.timedelta(hours=24)
    )
    
    return jsonify(access_token=access_token), 200

@app.route('/api/protected', methods=['GET'])
@jwt_required()
def api_protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user, message="This is a protected endpoint"), 200

@app.route('/api/process', methods=['POST'])
@jwt_required()
def api_process():
    current_user = get_jwt_identity()
    # Simulate CPU-intensive work
    import time
    time.sleep(2)  # Simulate processing time
    return jsonify({
        "message": "Processing complete", 
        "user": current_user,
        "result": "Sample processed data"
    }), 200

@app.route('/api/filter-image', methods=['POST'])
@jwt_required()
def api_filter_image():
    current_user = get_jwt_identity()
    
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    
    file = request.files['image']
    filter_type = request.form.get('filter', 'BLUR')
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        try:
            img = Image.open(file.stream)
            original_format = img.format if img.format else 'JPEG'
            
            # Apply stronger / more visible filters
            if filter_type == 'BLUR':
                filtered_img = img.filter(ImageFilter.GaussianBlur(radius=5))
            elif filter_type == 'CONTOUR':
                filtered_img = img.filter(ImageFilter.CONTOUR)
            elif filter_type == 'DETAIL':
                filtered_img = img.filter(ImageFilter.DETAIL)
            elif filter_type == 'EDGE_ENHANCE':
                filtered_img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
            elif filter_type == 'EMBOSS':
                filtered_img = img.filter(ImageFilter.EMBOSS)
            elif filter_type == 'SHARPEN':
                filtered_img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=3))
            elif filter_type == 'SMOOTH':
                filtered_img = img.filter(ImageFilter.SMOOTH_MORE)
            elif filter_type == 'EDGES':  # new dramatic effect
                filtered_img = img.filter(ImageFilter.FIND_EDGES)
            else:
                filtered_img = img
            
            # Generate a unique ID
            image_id = str(uuid.uuid4())
            
            # Save to buffer
            img_io = io.BytesIO()
            filtered_img.save(img_io, format=original_format)
            img_io.seek(0)
            
            files[image_id] = {
                'data': img_io.getvalue(),
                'format': original_format.lower(),
                'filter': filter_type
            }
            
            img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
            
            return jsonify({
                "message": "Image processed successfully",
                "user": current_user,
                "filter": filter_type,
                "image_id": image_id,
                "image": f"data:image/{original_format.lower()};base64,{img_base64}"
            }), 200
            
        except Exception as e:
            return jsonify({"error": f"Error processing image: {str(e)}"}), 500

@app.route('/api/download-image/<image_id>', methods=['GET'])
def api_download_image(image_id):
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Missing token"}), 401
    
    try:
        from flask_jwt_extended import decode_token
        decode_token(token)
    except:
        return jsonify({"error": "Invalid token"}), 401
    
    if image_id not in files:
        return jsonify({"error": "Image not found"}), 404
    
    image_data = files[image_id]
    format = image_data['format']
    filter_name = image_data['filter']
    
    img_io = io.BytesIO(image_data['data'])
    img_io.seek(0)
    
    filename = f"filtered_image_{filter_name.lower()}.{format}"
    
    return send_file(
        img_io,
        mimetype=f"image/{format}",
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        
    app.run(debug=True, host='0.0.0.0', port=8080)
