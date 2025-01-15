# README: Setup for Active Window Tracking and OCR with Tesseract

## 1. **Install Python Environment**

1. Install Python 3.x from the [official Python website](https://www.python.org/downloads/).
2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```
   - Windows:
     ```bash
     venv\Scripts\activate
     ```

## 2. **Install Required Python Libraries**

Run the following command to install the required packages:

```bash
pip install pillow pytesseract pygetwindow pywin32
```

## 3. **Install Tesseract OCR**

1. Download Tesseract from the [official Tesseract GitHub page](https://github.com/UB-Mannheim/tesseract/wiki).
2. Install Tesseract using the downloaded installer.
3. Add the Tesseract installation path to the system's PATH environment variable:
   - Default path: `C:\Program Files\Tesseract-OCR\tesseract.exe`

## 4. **Verify Tesseract Installation**

1. Open a terminal or command prompt.
2. Run:
   ```bash
   tesseract --version
   ```
3. Ensure it displays the Tesseract version.

## 5. **Set Up and Run the Code**

1. Place the Python script provided in the repository in your working directory.
2. Open the script and verify the following:
   - Update `pytesseract.pytesseract.tesseract_cmd` with the Tesseract executable path if needed.
   - Replace placeholders for email and password in the code.
3. Run the script:
   ```bash
   python script_name.py
   ```

## 6. **Optional Customizations**

- **Email and Password**:
  Update the variables in the script to match your credentials.
- **Screenshot Interval**:
  Modify the interval in the `monitor_active_window()` function.
- **Languages for OCR**:
  Install additional language packs for Tesseract if needed and update the `lang` parameter in `pytesseract.image_to_string`.

## 7. **Troubleshooting**

- Ensure Tesseract is correctly added to the PATH.
- Verify that Python dependencies are installed in the correct virtual environment.
- For Windows-specific issues, ensure `pywin32` is installed and functional.
