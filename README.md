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
        - **Simple Ratio (`fuzz.ratio`)**: General similarity; order and exactness matter more.
        - **Partial Ratio (`fuzz.partial_ratio`)**: Finds the best matching substring; good for phrases contained within longer strings.
        - **Token Sort Ratio (`fuzz.token_sort_ratio`)**: Sorts words alphabetically before comparing; ignores word order.
        - **Token Set Ratio (`fuzz.token_set_ratio`)**: Compares unique word sets; robust to extra words and reordering. Often the best general choice for messy data.
        - **Weighted Ratio (`fuzz.WRatio`)**: A sophisticated general-purpose ratio that attempts to provide the "best" score across various comparison types.
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
