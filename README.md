
# KoboToolbox Project Dashboard

A powerful Streamlit application for KoboToolbox users to **browse, filter, analyze, and export** project metadata and submission data using the KoboToolbox API.

Supports both the **Project Views API** (for curated lists of projects) and the **Assets API** (for direct access to all surveys).

---

## 🚀 Features

### 🔐 Authentication
- Secure login via KoboToolbox **API Token**.

### 🔄 Flexible Data Source
- **Project Views API**: Filter by pre-defined project views (if configured in your Kobo account).
- **Assets API**: Fetch all accessible surveys directly.

### 📁 Project Browser
- View a table of loaded projects with metadata:
  - Name, UID, Status, Submission Count, Dates, Country, **Sector**, Source View, Owner Username
- **Dynamic filters** in the sidebar:
  - Project name (keyword search, comma-separated)
  - Country
  - Project Status (dynamically populated from your data)
  - Sector (dynamically populated from your data)
  - Date created (range)
  - Minimum number of submissions

### 📊 Analytics Dashboard
- Visualize project statistics based on your filtered data:
  - Number of projects by country
  - Total submissions per project (Top N)
  - Submission trends over time
  - Projects grouped by source view

### 📝 Form Analyser
- Analyze form definitions of currently filtered projects by parsing their JSON content (or falling back to XLSForm XML).
- Extracts all question names (`name`) and their associated labels (from all languages if available), and question types.
- **Keyword Search**:
    - Enter keywords (comma-separated) to search within all extracted question names, labels, and types.
    - Select a **Fuzzy Matching Method** to control similarity:
        - **Simple Ratio (`fuzz.ratio`)**: Calculates general similarity; order and exactness matter more.
        - **Partial Ratio (`fuzz.partial_ratio`)**: Finds the best matching substring; good for phrases contained within longer strings.
        - **Token Sort Ratio (`fuzz.token_sort_ratio`)**: Sorts words alphabetically before comparing; ignores word order.
        - **Token Set Ratio (`fuzz.token_set_ratio`)**: Compares unique word sets; robust to extra words, reordering, and varying lengths. **This is often the best general choice for matching natural language questions/labels.**
        - **Weighted Ratio (`fuzz.WRatio`)**: A sophisticated general-purpose ratio that attempts to provide the "best" score across various comparison types, handling case and punctuation well.
    - Output: A table showing each form's Name, UID, Owner Username, the number of keyword matches found, and the specific terms that matched.

### 📤 Data Export Center
- Export data for **all currently displayed/filtered projects**:
  - **1. Project Metadata Export (Excel)**: Downloads all available metadata columns for the displayed projects.
  - **2. XLSForm Downloads (ZIP)**: Downloads the raw XLSForm `.xls` definition file for each displayed project, zipped.
  - **3. Raw Submission Data (JSON ZIP)**: Downloads the raw JSON submission data for each displayed project, zipped. Data is flattened as returned by Kobo's API.

---

## 🛠️ Installation

### Required Packages

Install the required Python packages (ideally in a virtual environment):

```bash
pip install streamlit requests pandas openpyxl altair lxml fuzzywuzzy python-Levenshtein
```

💡 `python-Levenshtein` is optional but highly recommended for faster fuzzy matching.

💡 If `fuzzywuzzy` causes issues, try:
```bash
pip install thefuzz
```
Then change:
```python
from fuzzywuzzy import fuzz
```
to:
```python
from thefuzz import fuzz
```

---

## 📂 Project Structure

- `main.py`: Streamlit UI, session state, and layout.
- `kobo_api_functions.py`: All Kobo API interactions, including fetching project metadata, project views, submissions, and parsing form definitions.

---

## ⚙️ Setup Instructions

### Save the Files:
Save `main.py` and `kobo_api_functions.py` in the same directory on your local machine.

### Install Dependencies:
Open your terminal or command prompt, navigate to the directory where you saved the files, and run:

```bash
pip install streamlit requests pandas openpyxl altair lxml fuzzywuzzy python-Levenshtein
```

### Run the Streamlit App:
From the same directory in your terminal:

```bash
streamlit run main.py
```

This will open the application in your default web browser.

---

## 🔑 KoboToolbox API Setup

1. Log into your [KoboToolbox account](https://kf.kobotoolbox.org or https://eu.kobotoolbox.org).
2. Go to **Account Settings > API** tab.
3. Copy your **API token** (keep it private!).
4. Paste your token and server URL in the Streamlit sidebar:
   - Example server URLs:
     - `https://kf.kobotoolbox.org`
     - `https://eu.kobotoolbox.org`

---

## 🧭 Usage Guide

### 1. Authentication & Source Selection (Sidebar)
- Enter your KoboToolbox Server URL and API Token in the sidebar.
- Choose your data source: "Project Views API" or "Regular Assets API".
- Optionally, check **"Include Only Surveys"** to filter assets during initial load.

### 2. Fetch Project Data
- Click the appropriate button in the sidebar based on your chosen data source:
  - **"Fetch Available Project Views"** (if using Project Views API, then select views and **"Load Assets from Selected Project View(s)"**).
  - **"Fetch All Assets (Direct)"** (if using Regular Assets API).
- The **"Project Browser"** tab will populate with your loaded project metadata.

### 3. Project Browser (Tab 1)
- Browse your loaded projects in a comprehensive table.
- Use the various filters in the sidebar (Project Name keywords, Country, Project Status, Sector, Date range, Minimum Submissions) to dynamically narrow down the displayed projects.

### 4. Analytics Dashboard (Tab 2)
- Explore visual analytics and charts based on your currently filtered projects from the "Project Browser" tab.

### 5. Form Analyser (Tab 3)
- Click **"Analyze Forms from Filtered Projects"** to retrieve and process the definitions of your currently displayed projects.
- Use the **"Search Data Column Names with Keywords"** section to:
  - Enter keywords
  - Adjust the Fuzzy Matching Threshold
  - Select a Fuzzy Matching Method
  - Click **"Search Forms for Keywords"** to see matching results in a table.

### 6. Data Export Center (Tab 4)
This tab allows you to download data for all projects currently displayed/filtered in the "Project Browser" tab.

1. **Project Metadata Export**: Download an Excel file containing all available metadata columns of the displayed projects.
2. **XLSForm Downloads**: Download a ZIP archive containing the raw XLSForm `.xls` definition file for each displayed project.
3. **Raw Submission Data**: Download a ZIP archive containing the raw JSON submission data for each displayed project. Each project's submissions will be a separate `.json` file within the ZIP, with data flattened as returned by Kobo's API response.
