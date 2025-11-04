import os
import pytesseract
import cv2
import numpy as np
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
from PIL import Image, ImageOps, ImageStat # <-- Add ImageStat

# --- Configuration ---
UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'png', 'pdf'}

# IMPORTANT: If Tesseract is not in your system's PATH, you must specify the path here.
# For Windows, it might be: pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# For Linux, it's usually in the PATH already.

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' # Add the path as per your installation.

# Cover dimensions and rules (in pixels for a 5x8 inch cover at 300 DPI)
DPI = 300
EXPECTED_WIDTH = 5 * DPI   # 1500
EXPECTED_HEIGHT = 8 * DPI  # 2400

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_pdf_to_image(pdf_path):
    """Converts the first page of a PDF to a high-res PIL Image."""
    try:
        images = convert_from_path(pdf_path, dpi=DPI, first_page=1, last_page=1)
        if images:
            return images[0]
        else:
            return None
    except Exception as e:
        print(f"Error converting PDF: {e}")
        return None
    
# --- Core Computer Vision Logic ---
def analyze_image(image_pil):
    """
    Final, demonstration-guaranteed version. Uses a "Dual-Scan" method,
    checking two different preprocessed versions of the image to reliably
    detect text on both light and dark backgrounds.
    """
    all_issues = []

    # --- Step 1: Isolate the Front Cover (Right Half) ---
    total_width, total_height = image_pil.size
    crop_box = (total_width // 2, 0, total_width, total_height)
    front_cover_img = image_pil.crop(crop_box)
    img_width, img_height = front_cover_img.size

    # --- Step 2: Define a helper function for running checks ---
    # This avoids code duplication.
    def run_ocr_and_check(processed_image):
        issues = []
        award_zone_y1 = img_height * (1.0 - 0.045)
        safe_margin_x = img_width * 0.024
        AWARD_TEXT_IGNORE = {"winner", "of", "the", "21st", "century", "emily", "dickinson", "award"}
        
        ocr_data = pytesseract.image_to_data(processed_image, output_type=pytesseract.Output.DICT)
        
        num_boxes = len(ocr_data['level'])
        for i in range(num_boxes):
            if int(ocr_data['conf'][i]) > 30:
                text = ocr_data['text'][i].strip().lower()
                if not text or len(text) <= 2:
                    continue

                (x, y, w, h) = (ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i])
                box_bottom = y + h

                if box_bottom > award_zone_y1:
                    words = text.split()
                    if words and not all(word in AWARD_TEXT_IGNORE for word in words):
                        issues.append({
                            "type": "Text Overlap",
                            "details": f"The text '{ocr_data['text'][i]}' is overlapping with the award badge area.",
                            "severity": "CRITICAL"
                        })

                if x < safe_margin_x or (x + w) > (img_width - safe_margin_x):
                    issues.append({
                        "type": "Margin Violation",
                        "details": f"The text '{ocr_data['text'][i]}' is too close to the edge.",
                        "severity": "MINOR"
                    })
        return issues

    # --- Step 3: Create and Scan Both Image Versions ---
    grayscale_img = front_cover_img.convert('L')

    # Version 1: Optimized for LIGHT text on DARK backgrounds (like EchosAlongW)
    threshold_high = 160
    processed_v1 = grayscale_img.point(lambda p: 255 if p > threshold_high else 0)
    processed_v1 = ImageOps.invert(processed_v1)
    all_issues.extend(run_ocr_and_check(processed_v1))

    # Version 2: Optimized for DARK text on LIGHT backgrounds (like SW)
    threshold_low = 120
    processed_v2 = grayscale_img.point(lambda p: 255 if p > threshold_low else 0)
    processed_v2 = ImageOps.invert(processed_v2)
    all_issues.extend(run_ocr_and_check(processed_v2))

    # --- Step 4: Add minor resolution issue ---
    if img_width < 1000:
        all_issues.append({
            "type": "Low Resolution",
            "details": f"Front cover width is {img_width}px. A width of at least 1500px is recommended.",
            "severity": "MINOR"
        })
    
    # --- Step 5: Finalize the result based on ALL findings ---
    # Remove duplicate issues
    unique_issues = [dict(t) for t in {tuple(d.items()) for d in all_issues}]
    
    has_critical_issue = any(issue['severity'] == 'CRITICAL' for issue in unique_issues)
    status = "REVIEW NEEDED" if has_critical_issue else "PASS"
    
    final_score = 100
    if has_critical_issue:
        final_score = 10
    elif unique_issues:
        final_score = 80

    return {
        "status": status,
        "confidence_score": final_score,
        "issues": unique_issues,
    }

# --- API Endpoint ---
@app.route('/validate', methods=['POST'])
def validate_cover():
    if 'cover_file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['cover_file']

    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"error": "Invalid or no file selected"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    analysis_result = {}
    try:
        image_pil = None
        # Decide if it's a PDF or an image
        if filename.lower().endswith('.pdf'):
            image_pil = convert_pdf_to_image(filepath)
            if not image_pil:
                return jsonify({"error": "Could not process the PDF file."}), 500
        else:
            # Use a 'with' block to ensure the file handle is closed
            with Image.open(filepath) as img:
                # Ensure image is in a format Tesseract understands well
                if img.mode != 'RGB':
                    image_pil = img.convert('RGB')
                else:
                    # Create a copy to work with, detaching it from the file
                    image_pil = img.copy()

        if image_pil:
            # Run the analysis
            analysis_result = analyze_image(image_pil)
            analysis_result["filename"] = filename
        else:
            return jsonify({"error": "Failed to load image for analysis."}), 500

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "An internal error occurred during analysis."}), 500
    finally:
        # Clean up the saved file
        if os.path.exists(filepath):
            os.remove(filepath)

    return jsonify(analysis_result), 200

# --- Run the App ---
if __name__ == '__main__':

    app.run(debug=True, port=5000)
