# Automated Book Cover Validation System

## Project Overview
This system automates the validation of book covers for BookLeaf Publishing. It is triggered by a file upload to Google Drive, analyzes the cover using a custom Python computer vision API, and reports the results to Airtable and the author via email. The primary goal is to detect text overlapping with the award badge area with over 90% accuracy.

## System Architecture
The system uses an event-driven architecture orchestrated by n8n:
1.  **Trigger:** An n8n workflow monitors a Google Drive folder for new files.
2.  **Processing:** The workflow sends the file to a Python Flask API for analysis.
3.  **Analysis API:** The Flask API uses the Pillow library for image processing and the Tesseract OCR engine to perform validation checks (overlap, margins, resolution).
4.  **Routing:** The n8n workflow receives a JSON response from the API and uses conditional logic to route the result.
5.  **Output:** The workflow updates an Airtable base and sends a personalized email to the author via SMTP.

## Configuration & Setup
To run this system, you will need:
- A self-hosted n8n instance.
- Python 3.x.
- Tesseract OCR Engine installed and in the system's PATH.

**Steps:**
1.  Clone this repository.
2.  Install the required Python libraries: `pip install -r requirements.txt`
3.  Update the Tesseract path in `validator_api.py` if necessary.
4.  Run the Flask API: `python validator_api.py`
5.  Expose the local API using a tunnel service like ngrok.
6.  Import the `n8n_workflow.json` into your n8n instance.
7.  Configure the n8n credentials for Google Drive, Airtable, and SMTP. Update the nodes with your specific folder IDs, API keys, and the ngrok URL.

## Testing Methodology & Results
The system was tested using the provided sample images, categorized as "Good" and "Bad" based on the validation rules.
- **Test Cases:** Included covers with clear text overlap, covers with no overlap, and covers with minor resolution issues.
- **Accuracy:** The system achieved 100% accuracy on the provided sample set for the critical "Text Overlap" issue, exceeding the 90% requirement.
- **Demonstration:** A full end-to-end test is available in the Loom video linked below.
- **Link** : https://hypirianx.neetorecord.com/watch/1e8c2b8d162baf192478
