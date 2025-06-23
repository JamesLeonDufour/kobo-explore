import requests
import pandas as pd
import io
import zipfile
from datetime import datetime
import pycountry
import xml.etree.ElementTree as ET # Kept for potential other uses, but not directly for form content parsing now
import json
from fuzzywuzzy import fuzz
import re
import streamlit as st # Streamlit is needed for caching and progress indicators


def fetch_all_project_views_metadata(token, server_url, progress_bar=None, status_text=None):
    """
    Fetches metadata for all available project views from KoboToolbox.
    Displays progress and handles API errors.
    """
    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/json"
    }
    all_views = []
    page_count = 0
    total_views_count = None # To store the total count from the API response
    
    pb = progress_bar if progress_bar is not None else st.progress(0)
    st_text = status_text if status_text is not None else st.empty()


    next_url = f"{server_url}/api/v2/project-views/?format=json"
    while next_url:
        try:
            res = requests.get(next_url, headers=headers, timeout=10)
            res.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = res.json()

            if total_views_count is None: # Get total count from the first page
                total_views_count = data.get("count", 0)
                if total_views_count == 0:
                    st_text.text("No project views found.")
                    pb.empty()
                    return []

            results = data.get("results", [])
            for pv in results:
                if not isinstance(pv, dict):
                    st.warning(f"Skipping unexpected non-dictionary project view item: {pv}")
                    continue

                all_views.append({
                    "View Name": pv.get("name"),
                    "View UID": pv.get("uid"),
                    "URL": pv.get("url") # Keep URL for reference if needed
                })
            
            current_progress = len(all_views) / total_views_count if total_views_count > 0 else 0
            st_text.text(f"Fetching project views: {len(all_views)} of {total_views_count} ({min(100, int(current_progress * 100))}%)")
            pb.progress(current_progress)

            page_count += 1
            next_url = data.get("next")
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to fetch project views: {e}")
            pb.empty()
            st_text.empty()
            return []
    
    return all_views

def fetch_assets_for_project_views(selected_view_uids, token, server_url, include_surveys=True, progress_bar=None, status_text=None):
    """
    Fetches asset metadata (e.g., forms, surveys) for selected project views.
    Filters by asset_type if specified and derives a 'Status' field.
    Updates provided progress_bar and status_text.
    """
    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/json"
    }
    all_assets_from_views = []
    
    pb = progress_bar if progress_bar is not None else st.progress(0)
    st_text = status_text if status_text is not None else st.empty()

    total_views = len(selected_view_uids)
    
    for i, view_uid in enumerate(selected_view_uids):
        view_page_count = 0
        current_view_assets_fetched = 0
        total_assets_in_current_view = None # To store total assets for this view
        
        next_asset_url = f"{server_url}/api/v2/project-views/{view_uid}/assets/?format=json"
        
        while next_asset_url:
            try:
                res = requests.get(next_asset_url, headers=headers, timeout=30)
                res.raise_for_status()
                data = res.json()

                if total_assets_in_current_view is None:
                    total_assets_in_current_view = data.get("count", 0)

                assets_in_view = data.get("results", [])

                for asset in assets_in_view:
                    if not isinstance(asset, dict):
                        st.warning(f"Skipping unexpected non-dictionary asset in view '{view_uid}': {asset}")
                        continue

                    if include_surveys and asset.get("asset_type") != "survey":
                        continue

                    settings = asset.get("settings", {})
                    country_list = settings.get("country", [])
                    sector_data = settings.get("sector") 

                    country_label = country_list[0].get("label", "") if country_list and isinstance(country_list, list) and len(country_list) > 0 else ""
                    country_code = country_list[0].get("value", "") if country_list and isinstance(country_list, list) and len(country_list) > 0 else ""

                    status_label = "Draft" 
                    if asset.get("deployment_status") == "deployed":
                        status_label = "Deployed"
                    elif asset.get("is_archived"):
                        status_label = "Archived"

                    all_assets_from_views.append({
                        "Name": asset.get("name"),
                        "UID": asset.get("uid"),
                        "Submission Count": asset.get("deployment__submission_count", 0),
                        "Date Created": asset.get("date_created"),
                        "Date Modified": asset.get("date_modified"),
                        "Country Label": country_label,
                        "Country Code": country_code,
                        "Source View UID": view_uid,
                        "Source View Name": next((pv["View Name"] for pv in st.session_state.available_project_views if pv["View UID"] == view_uid), "Unknown"),
                        "Is Deployed": asset.get("is_deployed", False),
                        "Is Archived": asset.get("is_archived", False),
                        "Status": status_label,
                        "Owner Username": asset.get("owner__username"), 
                        "Sector": sector_data # Keep sector as it's part of top-level metadata
                        # Removed "Form Content Raw" from here, will fetch it in fetch_and_parse_form_definitions
                    })
                
                current_view_assets_fetched += len(assets_in_view)
                view_page_count += 1
                next_asset_url = data.get("next")

                current_view_progress = current_view_assets_fetched / total_assets_in_current_view if total_assets_in_current_view > 0 else 0
                st_text.text(f"View {i+1}/{total_views}: Loading assets for '{view_uid}' - {current_view_assets_fetched} of {total_assets_in_current_view} ({min(100, int(current_view_progress * 100))}%)")
                pb.progress(min(1.0, (i + current_view_progress) / total_views))

            except requests.exceptions.RequestException as e:
                st.warning(f"Could not fetch assets for project view '{view_uid}': {e}. Skipping this view.")
                next_asset_url = None
    
    return all_assets_from_views


def fetch_all_assets_metadata(token, server_url, include_surveys=True, progress_bar=None, status_text=None):
    """
    Fetches metadata for all assets directly from the /api/v2/assets/ endpoint.
    Processes data similarly to maintain consistency with dashboard structure.
    Updates provided progress_bar and status_text.
    """
    headers = {"Authorization": f"Token {token}", "Accept": "application/json"}
    all_assets = []
    page_count = 0
    total_assets_count = None # To store the total count from the API response
    
    pb = progress_bar if progress_bar is not None else st.progress(0)
    st_text = status_text if status_text is not None else st.empty()

    next_url = f"{server_url}/api/v2/assets/?format=json"
    while next_url:
        try:
            res = requests.get(next_url, headers=headers, timeout=15)
            res.raise_for_status()
            data = res.json()

            if total_assets_count is None: # Get total count from the first page
                total_assets_count = data.get("count", 0)
                if total_assets_count == 0:
                    st_text.text("No assets found.")
                    pb.empty()
                    return []

            results = data.get("results", [])
            
            for asset in results:
                if not isinstance(asset, dict):
                    st.warning(f"Skipping unexpected non-dictionary asset: {asset}")
                    continue

                if include_surveys and asset.get("asset_type") != "survey":
                    continue

                settings = asset.get("settings", {})
                country_list = settings.get("country", [])
                sector_data = settings.get("sector") 
                
                country_label = country_list[0].get("label", "") if country_list and isinstance(country_list, list) and len(country_list) > 0 else ""
                country_code = country_list[0].get("value", "") if country_list and isinstance(country_list, list) and len(country_list) > 0 else ""

                status_label = "Draft" 
                if asset.get("deployment_status") == "deployed":
                    status_label = "Deployed"
                elif asset.get("is_archived", False):
                    status_label = "Archived"

                all_assets.append({
                    "Name": asset.get("name"),
                    "UID": asset.get("uid"),
                    "Submission Count": asset.get("deployment__submission_count", 0),
                    "Date Created": asset.get("date_created"),
                    "Date Modified": asset.get("date_modified"),
                    "Country Label": country_label,
                    "Country Code": country_code,
                    "Source View UID": "N/A",
                    "Source View Name": "Direct Assets API",
                    "Is Deployed": asset.get("is_deployed", False),
                    "Is Archived": asset.get("is_archived", False),
                    "Status": status_label,
                    "Owner Username": asset.get("owner__username"), 
                    "Sector": sector_data # Keep sector as it's part of top-level metadata
                    # Removed "Form Content Raw" from here, will fetch it in fetch_and_parse_form_definitions
                })
            
            current_progress = len(all_assets) / total_assets_count if total_assets_count > 0 else 0
            st_text.text(f"Fetching assets: {len(all_assets)} of {total_assets_count} ({min(100, int(current_progress * 100))}%)")
            pb.progress(current_progress)

            page_count += 1
            next_url = data.get("next")
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to fetch assets from /api/v2/assets/: {e}")
            pb.empty()
            st_text.empty()
            return []
    
    return all_assets


def fetch_and_parse_form_definitions(projects_df, token, server_url):
    """
    Fetches and parses form definitions (names, labels, types) for a given DataFrame of projects (assets).
    Always makes a dedicated API call to the asset's full JSON detail endpoint for accuracy.
    """
    headers = {"Authorization": f"Token {token}", "Accept": "application/json"} # Ensure Accept JSON
    form_details = [] 
    all_unique_columns = set()

    if projects_df.empty:
        st.info("No projects in the filtered list to analyze for form definitions.")
        return [], set()

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, (_, row) in enumerate(projects_df.iterrows()):
        uid = row["UID"]
        form_name = row["Name"]
        
        column_terms = set() 
        
        # --- NEW PRIMARY LOGIC: Always fetch the full JSON asset detail ---
        full_asset_json_url = f"{server_url}/api/v2/assets/{uid}/?format=json"
        
        status_text.text(f"Fetching and parsing form content for: {form_name} ({i+1}/{len(projects_df)})...")
        try:
            res = requests.get(full_asset_json_url, headers=headers, timeout=20) # Increased timeout for full content
            res.raise_for_status()
            full_asset_data = res.json()

            form_content = full_asset_data.get("content")
            if isinstance(form_content, dict) and "survey" in form_content:
                survey_elements = form_content.get("survey", [])
                if isinstance(survey_elements, list):
                    for element in survey_elements:
                        if isinstance(element, dict):
                            # Add 'name'
                            if "name" in element and element["name"] is not None:
                                column_terms.add(str(element["name"]))
                            
                            # Add all items from 'label' list
                            labels = element.get("label")
                            if isinstance(labels, list):
                                for label_text in labels:
                                    if label_text is not None:
                                        column_terms.add(str(label_text))
                            elif isinstance(labels, str) and labels is not None: # Handle single string label
                                column_terms.add(str(labels))
                            
                            # Add 'type'
                            if "type" in element and element["type"] is not None:
                                column_terms.add(str(element["type"]))
                else:
                    st.warning(f"Form '{form_name}' (UID: {uid}) has 'content' but its 'survey' field is not a list. Could not parse form definition from JSON.")
            else:
                st.warning(f"Form '{form_name}' (UID: {uid}) does not have valid 'content' data. Could not parse form definition from JSON.")

        except requests.exceptions.RequestException as e:
            st.error(f"Failed to fetch full JSON form definition for {form_name} (UID: {uid}): {e}. No form definition terms extracted.") 
        except json.JSONDecodeError as e:
            st.error(f"Failed to decode JSON for {form_name} (UID: {uid}): {e}. The response may not be valid JSON. No form definition terms extracted.")
        except Exception as e:
            st.error(f"An unexpected error occurred during form definition fetch for {form_name} (UID: {uid}): {e}. No form definition terms extracted.")
            
        unique_form_columns = sorted(list(filter(None, column_terms)))
        all_unique_columns.update(unique_form_columns)

        form_details.append({ 
            "Form Name": form_name,
            "UID": uid,
            "Columns": unique_form_columns
        })
        progress_bar.progress((i + 1) / len(projects_df)) 
            
    progress_bar.empty()
    status_text.empty()
    return form_details, all_unique_columns 


@st.cache_data(show_spinner="Fetching and processing submission data...")
def fetch_submissions_data_from_v2_json(uid, token, server_url):
    """
    Fetches raw submission data in JSON format from /api/v2/assets/{asset_uid}/data/
    and converts it to a pandas DataFrame.
    Handles pagination.
    """
    headers = {"Authorization": f"Token {token}", "Accept": "application/json"}
    all_submissions = []
    next_url = f"{server_url}/api/v2/assets/{uid}/data/?format=json"
    
    try:
        total_submissions_count = None

        while next_url: # Loop to handle pagination
            res = requests.get(next_url, headers=headers, timeout=180) # Increased timeout significantly for data
            res.raise_for_status()

            data = res.json()
            submissions_page = data.get("results", [])
            
            if total_submissions_count is None: # Get total count from the first page
                total_submissions_count = data.get("count", 0)
                if total_submissions_count == 0:
                    st.warning(f"No submissions found for UID {uid}.")
                    return pd.DataFrame()

            all_submissions.extend(submissions_page) # Accumulate submissions
            
            next_url = data.get("next") # Get the URL for the next page
            
        if not all_submissions:
            st.warning(f"No submissions found for UID {uid} after pagination.")
            return pd.DataFrame() # Return empty DataFrame

        # If data is present, convert to DataFrame
        df = pd.json_normalize(all_submissions)
        return df

    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch JSON submissions for UID {uid} from '{server_url}/api/v2/assets/{uid}/data/': {e}")
        st.info("💡 **Tip:** Check if the form is deployed, has submissions, or if your API token is correct for this project/server.")
        st.warning("⚠️ **Important Note:** The `/api/v2/assets/{asset_uid}/data/` endpoint provides raw JSON. For large, complex, or deeply nested forms (especially those with repeat groups), its flattened output might differ significantly from Kobo's native Excel exports. Consider using Kobo's asynchronous `/exports` API for a true UI-like Excel export if this is a limitation.")
        return None
    except json.JSONDecodeError as e:
        st.error(f"Failed to decode JSON from submissions for UID {uid}: {e}. The response may not be valid JSON.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during JSON submission fetch for UID {uid}: {e}")
        return None