
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
  - Name, UID, Status, Submission Count, Dates, Country, Source View
- **Dynamic filters** in the sidebar:
  - Project name (keyword search, comma-separated)
  - Country
  - Date created (range)
  - Minimum number of submissions

### 📊 Analytics Dashboard
- Visualize project statistics:
  - Number of projects by country
  - Total submissions per project (Top N)
  - Submission trends over time
  - Projects grouped by source view

### 🧾 XML Form Analyzer
- Parse XLSForm/XML definitions of filtered projects
- Extract and list all question names (columns)
- Search columns across all forms
- Compare two forms to identify:
  - Common fields
  - Unique fields
  - Fuzzy matches based on name similarity
- Global fuzzy column name search across all forms

### 📤 Data Export Center
- Export:
  - Displayed or all project metadata (Excel)
  - Selected form definitions (XLS/XML as ZIP)
  - Raw submission data:
    - Per form (CSV/Excel ZIPs)
    - All filtered projects as:
      - ZIP of Excel files
      - Single Excel workbook with one sheet per form

---

## 🛠️ Installation

### Required Packages

Install the required Python packages (ideally in a virtual environment):

```bash
pip install streamlit requests pandas openpyxl altair lxml fuzzywuzzy python-Levenshtein
```

> 💡 `python-Levenshtein` is optional but highly recommended for faster fuzzy matching.

---

## 📂 Project Structure

- `main.py`: Streamlit UI, session state, and layout
- `kobo_api_functions.py`: All Kobo API interactions (project metadata, views, submissions, forms, etc.)

---

## ⚙️ Setup Instructions

1. **Clone the repository** and place `main.py` and `kobo_api_functions.py` in the same directory.
2. **Install dependencies** using the command above.
3. **Run the app**:

```bash
streamlit run main.py
```

---

## 🔑 KoboToolbox API Setup

1. Log into your [KoboToolbox account](https://kf.kobotoolbox.org or https://eu.kobotoolbox.org).
2. Go to **Account Settings > API** tab.
3. Copy your **API token** (keep it private!).
4. Paste your token and server URL in the **Streamlit sidebar**:
   - Example server URLs:
     - `https://kf.kobotoolbox.org`
     - `https://eu.kobotoolbox.org`

---

## 🧭 Usage Guide

### 1. Authentication & Source Selection
- Enter server URL + API token in sidebar
- Choose one data source:
  - **Project Views API**: Select from pre-defined project views
  - **Assets API**: Load all accessible surveys
- Optional: Filter to **only survey-type forms**

### 2. Fetch Project Data
- For **Project Views API**:
  - Click “Fetch Available Project Views”
  - Select views from dropdown
  - Click “Load Assets”
- For **Assets API**:
  - Click “Fetch All Assets (Direct)”

### 3. Project Browser (Tab 1)
- Browse all loaded projects in a table
- Use sidebar filters to narrow the view

### 4. Analytics Dashboard (Tab 2)
- Explore charts based on filtered projects

### 5. XML Form Analyzer (Tab 3)
- Analyze form structures and compare fields
- Search and compare column names across forms

> ⚠️ This tab is a **work in progress** – feedback welcome!

### 6. Data Export Center (Tab 4)
- Export project metadata and raw data
- Choose specific forms or all filtered ones
- Export options:
  - ZIP of form definitions
  - ZIP of raw submissions
  - Excel workbook with one sheet per form

---

## 🧰 Troubleshooting

### 🔧 Common Errors & Fixes

#### ❌ `NameError: name 'requests' is not defined`
- Add `import requests` to the top of `main.py`

#### ❌ Zero submissions / missing data
- Ensure:
  - Your **API token** is correct
  - Your account has **View Submissions** permission
  - The **form is deployed**
- Use tools like Postman to test the API manually:
  ```
  YOUR_SERVER/api/v2/assets/YOUR_UID/data/?format=json
  ```

#### ❌ Cached empty results
- Use **“Clear App Cache”** in the sidebar
- Re-fetch the data

#### ❌ Network timeouts
- Large forms can take time to load
- Fetch timeout is set to **180 seconds**
- Retry if the server is slow or under load

---

## 📎 Notes

- **Flattening JSON**: Deeply nested Kobo data may not flatten cleanly into tables. For complex forms (with repeat groups), Kobo's own XLS export may be more appropriate.
- **Streamlit reruns**: All interactions re-trigger the full app. State is preserved using `st.session_state`.

---

## 📫 Feedback & Contributions

This project is actively maintained. Issues, ideas, and contributions are welcome via [GitHub Issues](https://github.com/your-repo/issues).
