# Required packages:
# pip install streamlit requests pandas openpyxl altair lxml fuzzywuzzy # Added fuzzywuzzy
# lxml is often faster for XML, but ElementTree is built-in
# fuzzywuzzy is for string comparison, often needs python-Levenshtein for speed

import streamlit as st
import requests
import pandas as pd
import io
import zipfile
from datetime import datetime
import altair as alt
import re # For regular expressions in keyword search
from fuzzywuzzy import fuzz # Keep this import here for fuzz.ratio

# Import API functions from the new file
import kobo_api_functions as kobo_api

st.set_page_config(layout="wide", page_title="KoboToolbox Project Dashboard")
st.title("KoboToolbox Project Dashboard")

# --- Session State Initialization ---
if "available_project_views" not in st.session_state: # Stores metadata of all project views (for PV API)
    st.session_state.available_project_views = []
if "project_views_fetched" not in st.session_state:
    st.session_state.project_views_fetched = False
if "loaded_assets_from_views" not in st.session_state: # Stores the actual asset data loaded (list of dicts)
    st.session_state.loaded_assets_from_views = []
if "assets_loaded" not in st.session_state: # Flag when assets from views are loaded
    st.session_state.assets_loaded = False
if "filtered_projects_df" not in st.session_state: # The DataFrame currently displayed/filtered
    st.session_state.filtered_projects_df = pd.DataFrame()
if "filters_applied" not in st.session_state:
    st.session_state.filters_applied = False
# New session state variable to hold all loaded assets as a DataFrame for filter options
if "all_loaded_assets_df" not in st.session_state:
    st.session_state.all_loaded_assets_df = pd.DataFrame()

# Session state variables for Form Analyser tab
if "xml_form_details" not in st.session_state: # Stores list of {'form_name': ..., 'uid': ..., 'columns': [...]} from form definitions
    st.session_state.xml_form_details = []
if "all_xml_column_names" not in st.session_state:
    st.session_state.all_xml_column_names = set() # Stores a set of all unique column names found from form definitions
if "xml_forms_processed" not in st.session_state:
    st.session_state.xml_forms_processed = False
if "keyword_match_results" not in st.session_state: # New state for keyword matching results
    st.session_state.keyword_match_results = pd.DataFrame()

# New session state for Form Analyser inputs to prevent reset on type/rerun
if "analyser_keywords_input" not in st.session_state:
    st.session_state.analyser_keywords_input = ""
if "analyser_fuzzy_threshold" not in st.session_state:
    st.session_state.analyser_fuzzy_threshold = 80
if "analyser_fuzzy_method" not in st.session_state:
    st.session_state.analyser_fuzzy_method = "Token Set Ratio (fuzz.token_set_ratio)" # Set initial default


# --- Sidebar: Authentication & Fetch Buttons ---
# Compacted layout for sidebar
with st.sidebar:
    st.header("Authentication")
    server_url_input = st.text_input("KoboToolbox Server URL", "https://eu.kobotoolbox.org", help="e.g., https://kobo.humanitarianresponse.info or https://kf.kobotoolbox.org")
    api_token_input = st.text_input("API Token", type="password", help="Get your token from KoboToolbox Account Settings (API tab)")

    # Use these consistent variables from now on
    server_url = server_url_input
    api_token = api_token_input

    st.checkbox("Include Only Surveys (applied to loaded assets)", value=True, key="include_surveys_only", help="Filters asset types during initial data load.")

    st.header("Data Source Selection")
    data_source_option = st.radio(
        "Choose how to fetch project metadata:",
        ("Project Views API", "Regular Assets API"),
        key="data_source_selector",
        help="Project Views API allows filtering by Kobo project views. Regular Assets API fetches all accessible surveys directly."
    )

    # Container for dynamic status messages and progress bars in sidebar
    sidebar_status_container = st.empty() # This empty container will be filled dynamically
    sidebar_progress_bar = sidebar_status_container.progress(0)
    sidebar_status_text = sidebar_status_container.empty()


    # --- Conditional Fetching Logic based on Data Source Selection ---

    if data_source_option == "Project Views API":
        st.header("Step 1: Fetch Project Views")
        if st.button("Fetch Available Project Views", key="fetch_views_button_pv"):
            if not api_token or not server_url:
                st.error("Please enter both API Token and Server URL.")
                sidebar_progress_bar.empty() # Clear if error
                sidebar_status_text.empty() # Clear if error
            else:
                # Reset primary asset-related session states ONLY
                st.session_state.project_views_fetched = False
                st.session_state.available_project_views = []
                st.session_state.loaded_assets_from_views = [] # Clear previously loaded assets
                st.session_state.assets_loaded = False
                st.session_state.filtered_projects_df = pd.DataFrame()
                st.session_state.filters_applied = False
                st.session_state.all_loaded_assets_df = pd.DataFrame()
                # DO NOT reset form analyser states here (xml_forms_processed, xml_form_details etc.)

                with st.spinner("Fetching available project views..."): 
                    st.session_state.available_project_views = kobo_api.fetch_all_project_views_metadata(api_token, server_url, progress_bar=sidebar_progress_bar, status_text=sidebar_status_text)
                    if st.session_state.available_project_views:
                        st.session_state.project_views_fetched = True
                        sidebar_status_text.success(f"Found {len(st.session_state.available_project_views)} project views.")
                    else:
                        sidebar_status_text.warning("No project views found. Ensure forms are deployed or check your API token/URL.")
                
                sidebar_progress_bar.empty()

        st.header("Step 2: Load Assets from Project Views")
        selected_pv_uids_for_loading = []
        if st.session_state.project_views_fetched and st.session_state.available_project_views:
            pv_options_dict = {
                f"{pv['View Name']} (UID: {pv['View UID']})": pv['View UID']
                for pv in sorted(st.session_state.available_project_views, key=lambda x: x['View Name'])
            }
            selected_pv_full_strings = st.multiselect(
                "Select Project View(s) to Load Assets From:", 
                list(pv_options_dict.keys()), 
                key="selected_pv_for_loading"
            )
            selected_pv_uids_for_loading = [pv_options_dict[s] for s in selected_pv_full_strings]
        else:
            st.info("Fetch project views first using 'Step 1' button.")

        if st.button("Load Assets from Selected Project View(s)", key="load_assets_button_pv"):
            if not selected_pv_uids_for_loading:
                st.warning("Please select at least one Project View to load assets from.")
                sidebar_progress_bar.empty() # Clear if error
                sidebar_status_text.empty() # Clear if error
            elif not api_token or not server_url:
                st.error("Please enter both API Token and Server URL.")
                sidebar_progress_bar.empty() # Clear if error
                sidebar_status_text.empty() # Clear if error
            else:
                # Reset primary asset-related session states ONLY
                st.session_state.loaded_assets_from_views = []
                st.session_state.assets_loaded = False
                st.session_state.filtered_projects_df = pd.DataFrame() # Clear before new load
                st.session_state.filters_applied = False
                st.session_state.all_loaded_assets_df = pd.DataFrame()
                # DO NOT reset form analyser states here (xml_forms_processed, xml_form_details etc.)

                with st.spinner("Loading assets from selected project views..."): 
                    st.session_state.loaded_assets_from_views = kobo_api.fetch_assets_for_project_views(
                        selected_pv_uids_for_loading, 
                        api_token, 
                        server_url,
                        st.session_state.include_surveys_only,
                        progress_bar=sidebar_progress_bar, # Pass progress bar
                        status_text=sidebar_status_text # Pass status text
                    )
                    if st.session_state.loaded_assets_from_views:
                        st.session_state.assets_loaded = True
                        df_temp = pd.DataFrame(st.session_state.loaded_assets_from_views).drop_duplicates(subset=['UID'])
                        df_temp["Date Created"] = pd.to_datetime(df_temp["Date Created"], errors='coerce').dt.tz_localize(None)
                        df_temp["Date Modified"] = pd.to_datetime(df_temp["Date Modified"], errors='coerce').dt.tz_localize(None)
                        
                        st.session_state.all_loaded_assets_df = df_temp.copy() # Populate for filter options
                        st.session_state.filtered_projects_df = df_temp.copy() # Set filtered_projects_df initially to all loaded
                        st.session_state.filters_applied = True # Indicate filters can be applied now
                        sidebar_status_text.success(f"Successfully loaded {len(df_temp)} unique asset(s) from selected project views.")
                    else:
                        sidebar_status_text.error("Failed to load any assets for the selected views. Check your token and selections.")
                
                sidebar_progress_bar.empty()


    elif data_source_option == "Regular Assets API":
        st.header("Step 1: Fetch All Assets Directly")
        st.info("This will fetch all surveys you have access to directly, skipping Project View selection.")
        
        if st.button("Fetch All Assets (Direct)", key="fetch_all_assets_button"):
            if not api_token or not server_url:
                st.error("Please enter both API Token and Server URL.")
                sidebar_progress_bar.empty() # Clear if error
                sidebar_status_text.empty() # Clear if error
            else:
                # Reset primary asset-related session states ONLY
                st.session_state.project_views_fetched = False # Not using project views
                st.session_state.available_project_views = []
                st.session_state.loaded_assets_from_views = [] 
                st.session_state.assets_loaded = False
                st.session_state.filtered_projects_df = pd.DataFrame() # Clear before new load
                st.session_state.filters_applied = False
                st.session_state.all_loaded_assets_df = pd.DataFrame()
                # DO NOT reset form analyser states here (xml_forms_processed, xml_form_details etc.)

                with st.spinner("Fetching all assets directly..."): 
                    fetched_assets = kobo_api.fetch_all_assets_metadata(
                        api_token, 
                        server_url, 
                        st.session_state.include_surveys_only,
                        progress_bar=sidebar_progress_bar, # Pass progress bar
                        status_text=sidebar_status_text # Pass status text
                    )
                    if fetched_assets:
                        st.session_state.loaded_assets_from_views = fetched_assets
                        st.session_state.assets_loaded = True
                        df_temp = pd.DataFrame(st.session_state.loaded_assets_from_views).drop_duplicates(subset=['UID'])
                        df_temp["Date Created"] = pd.to_datetime(df_temp["Date Created"], errors='coerce').dt.tz_localize(None)
                        df_temp["Date Modified"] = pd.to_datetime(df_temp["Date Modified"], errors='coerce').dt.tz_localize(None)
                        
                        st.session_state.all_loaded_assets_df = df_temp.copy()
                        st.session_state.filtered_projects_df = df_temp.copy()
                        st.session_state.filters_applied = True # Indicate filters can be applied now
                        sidebar_status_text.success(f"Successfully loaded {len(df_temp)} unique assets directly from KoboToolbox.")
                    else:
                        sidebar_status_text.error("Failed to load any assets directly. Check your API token/URL or if there are assets available.")
                
                sidebar_progress_bar.empty()

    st.header("Advanced Options")
    if st.button("Clear App Cache"):
        st.cache_data.clear()
        st.cache_resource.clear() # Clear both types if you use resource caching too
        st.rerun()
        st.success("Cache cleared! Please re-fetch data.")


# --- Main Content Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["Project Browser", "Analytics Dashboard", "Form Analyser", "Data Export"]) 

with tab1:
    if not st.session_state.assets_loaded:
        st.info("Please use the sidebar to select a data source and fetch project metadata.")
    else: 
        # --- Sidebar: Apply Filters Section (Now Interactive) ---
        st.sidebar.header("Step 3: Apply Filters (Interactive)")
        
        # Filter: Keyword search for Project Name (only text input now)
        project_name_keywords_input = st.sidebar.text_input(
            "Search Project Name (comma-separated keywords):",
            value=st.session_state.get('project_name_keywords_input_val', ''), # Keep value on rerun
            help="Enter one or more keywords to search in project names. Separate with commas. Projects matching ANY keyword will be shown.",
            key="project_name_keywords_input_widget" # Changed key to avoid conflict with initial assignment
        )
        # Update session state for persistence across reruns caused by other widgets
        st.session_state.project_name_keywords_input_val = project_name_keywords_input
        project_name_keywords = [kw.strip() for kw in project_name_keywords_input.split(',') if kw.strip()]

        # Filter: Country Label
        loaded_countries_options = sorted(st.session_state.all_loaded_assets_df["Country Label"].dropna().unique()) if not st.session_state.all_loaded_assets_df.empty else []
        selected_countries = st.sidebar.multiselect("Country:", loaded_countries_options, key="country_label_select")
        
        # Filter: Project Status (Dynamically populated options)
        # Check if "Status" column exists and is not empty before getting unique values
        status_options_for_selection = []
        if "Status" in st.session_state.all_loaded_assets_df.columns and not st.session_state.all_loaded_assets_df.empty:
            status_options_for_selection = sorted(st.session_state.all_loaded_assets_df["Status"].dropna().unique().tolist())
        
        selected_statuses = st.sidebar.multiselect(
            "Project Status(es)", 
            options=status_options_for_selection, 
            default=status_options_for_selection, # Default to all loaded statuses selected
            help="Filter projects by their deployment status.",
            key="status_select"
        )

        # Filter: Sector (NEW)
        # This function converts raw sector data (dict or str) into a consistent string for filtering and display
        def get_sector_display_name(sector_item):
            if isinstance(sector_item, dict) and sector_item: # Check if it's a non-empty dictionary
                return sector_item.get('name') or sector_item.get('label') or str(sector_item)
            elif isinstance(sector_item, str) and sector_item.strip(): # If it's a non-empty string
                return sector_item
            return None # Handle None, empty strings, or other unexpected types

        # Extract unique sector options using the helper function
        loaded_sectors_options = []
        if "Sector" in st.session_state.all_loaded_assets_df.columns:
            # Apply the helper function to each item in the 'Sector' column
            # Then drop None values and get unique, then sort
            processed_sectors = st.session_state.all_loaded_assets_df["Sector"].apply(get_sector_display_name)
            loaded_sectors_options = sorted(processed_sectors.dropna().unique().tolist())

        selected_sectors = st.sidebar.multiselect("Sector:", loaded_sectors_options, key="sector_select")


        # New layout for Date Range and Minimum Submissions
        # Place date inputs side by side
        col_date_start, col_date_end = st.sidebar.columns(2)
        with col_date_start:
            # Filter: Date Range - From
            valid_dates = st.session_state.all_loaded_assets_df["Date Created"].dropna()
            min_date_val = valid_dates.min().date() if not valid_dates.empty else datetime.now().date()
            # Ensure the date_input retains its value across reruns
            date_start = st.date_input("Created From:", min_date_val, key="date_start_select")
        with col_date_end:
            # Filter: Date Range - To
            max_date_val = valid_dates.max().date() if not valid_dates.empty else datetime.now().date()
            # Ensure the date_input retains its value across reruns
            date_end = st.date_input("Created To:", max_date_val, key="date_end_select")
        
        # Place minimum submissions below dates
        min_submission_count = st.sidebar.number_input(
            "Minimum Submissions:",
            min_value=0,
            max_value=int(st.session_state.all_loaded_assets_df["Submission Count"].max() if "Submission Count" in st.session_state.all_loaded_assets_df.columns and not st.session_state.all_loaded_assets_df.empty else 0),
            value=st.session_state.get('min_submission_count_filter_val', 0), # Keep value on rerun
            step=10,
            help="Only show projects with at least this many submissions.",
            key="min_submission_count_filter_widget" # Changed key
        )
        st.session_state.min_submission_count_filter_val = min_submission_count # Update session state for persistence

        # --- Interactive Filtering Logic ---
        # This block now runs automatically whenever any filter widget changes
        filtered_df = st.session_state.all_loaded_assets_df.copy()
        
        if not filtered_df.empty: 
            # Filter 1: Date Range
            if "Date Created" in filtered_df.columns and not filtered_df["Date Created"].empty:
                filtered_df = filtered_df[
                    (filtered_df["Date Created"].dt.date >= date_start) &
                    (filtered_df["Date Created"].dt.date <= date_end)
                ]

            # Filter 2: Project Name Keyword Search (using single text input)
            if project_name_keywords:
                if "Name" in filtered_df.columns:
                    pattern = "|".join(re.escape(word) for word in project_name_keywords if word)
                    if pattern:
                        filtered_df = filtered_df[filtered_df["Name"].str.contains(pattern, case=False, na=False, regex=True)]
                else:
                    st.warning("Project Name column not found for keyword search.")
                    
            # Filter 3: Country Label
            if selected_countries: # Only filter if selections are made
                if "Country Label" in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df["Country Label"].isin(selected_countries)]
                else:
                    st.warning("Country Label column not found for country filter.")

            # Filter 4: Project Status (Re-added logic, using selected_statuses)
            if selected_statuses:
                if "Status" in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df["Status"].isin(selected_statuses)]
                else:
                    st.warning("Status column not found for project status filter.")
            else: # If user explicitly selects no statuses, filter out everything based on status
                if "Status" in filtered_df.columns:
                    filtered_df = pd.DataFrame() # An empty DataFrame if no status is selected

            
        # Filter: Operational Purpose
        if "Operational Purpose" in st.session_state.all_loaded_assets_df.columns:
            operational_purposes = sorted(st.session_state.all_loaded_assets_df["Operational Purpose"].dropna().unique().tolist())
            selected_operational_purposes = st.sidebar.multiselect("Operational Purpose:", operational_purposes, key="operational_purpose_select")
        else:
            selected_operational_purposes = []

        # Filter: Collects PII
        if "Collects PII" in st.session_state.all_loaded_assets_df.columns:
            collects_pii_options = st.session_state.all_loaded_assets_df["Collects PII"].dropna().unique().tolist()
            selected_collects_pii = st.sidebar.multiselect("Collects PII:", collects_pii_options, key="collects_pii_select")
        else:
            selected_collects_pii = []

        # Filter: Description (keyword match)
        description_keywords_input = st.sidebar.text_input(
            "Search Description (keywords):",
            value=st.session_state.get('description_keywords_input_val', ''),
            help="Enter keywords to search in the description.",
            key="description_keywords_input_widget"
        )
        st.session_state.description_keywords_input_val = description_keywords_input
        description_keywords = [kw.strip() for kw in description_keywords_input.split(',') if kw.strip()]


        
        # Filter: Operational Purpose
        if "Operational Purpose" in filtered_df.columns and selected_operational_purposes:
            filtered_df = filtered_df[filtered_df["Operational Purpose"].isin(selected_operational_purposes)]

        # Filter: Collects PII
        if "Collects PII" in filtered_df.columns and selected_collects_pii:
            filtered_df = filtered_df[filtered_df["Collects PII"].isin(selected_collects_pii)]

        # Filter: Description
        if "Description" in filtered_df.columns and description_keywords:
            pattern = "|".join(re.escape(word) for word in description_keywords if word)
            if pattern:
                filtered_df = filtered_df[filtered_df["Description"].str.contains(pattern, case=False, na=False, regex=True)]

        # Filter 5: Sector (NEW Logic)
        if selected_sectors:
            if "Sector" in filtered_df.columns:
                # Apply the same helper function to the DataFrame column for filtering
                filtered_df = filtered_df[
                    filtered_df["Sector"].apply(lambda x: get_sector_display_name(x) in selected_sectors)
                ]
            else:
                st.warning("Sector column not found for sector filter.")
        
        # Filter 6: Minimum Submission Count
        if "Submission Count" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Submission Count"] >= min_submission_count]
        else:
            st.warning("Submission Count column not found for minimum submissions filter.")

        st.session_state.filtered_projects_df = filtered_df
        st.session_state.filters_applied = True # Keep this flag if it's used elsewhere for display logic

        current_display_df = st.session_state.filtered_projects_df.copy() # Refresh the displayed df

        # --- Display Section of tab1 ---
        st.subheader("Current Project Statistics")
        col_stats1, col_stats2 = st.columns(2)
        with col_stats1:
            st.metric(label="Total Projects Displayed", value=len(current_display_df))
        with col_stats2:
            total_submissions = current_display_df["Submission Count"].sum()
            st.metric(label="Total Submissions", value=f"{total_submissions:,}") 
        st.markdown("---") # Separator

        st.write(f"### Current Projects Displayed ({len(current_display_df)})")
        
        # Define columns to display and their order for the main table
        display_cols_order = [
            "Name", "UID", "Status", "Submission Count", 
            "Date Created", "Date Modified", "Country Label", "Sector", 
            "Source View Name", "Owner Username"
        ]
        
        # Prepare 'Sector' column for display, converting dicts to strings
        display_df_for_table = current_display_df.copy()
        if "Sector" in display_df_for_table.columns:
            display_df_for_table["Sector"] = display_df_for_table["Sector"].apply(get_sector_display_name)


        # Ensure all display columns exist, if not, fill with None or skip
        actual_display_cols = [col for col in display_cols_order if col in display_df_for_table.columns] 
        
        if not display_df_for_table.empty and actual_display_cols:
            st.dataframe(display_df_for_table[actual_display_cols], use_container_width=True)
        elif not display_df_for_table.empty:
            st.info("No displayable columns found in the loaded data.")
        else:
            st.info("No projects loaded or matching current filters.")


# --- Analytics Dashboard Tab ---
with tab2:
    st.header("Analytics Dashboard")
    if not st.session_state.assets_loaded:
        st.info("Please **load assets** in the 'Project Browser' tab to see analytics.")
    elif st.session_state.filtered_projects_df.empty:
        st.info("No data available for analytics. **Apply filters** in the 'Project Browser' tab or load more assets.")
    else:
        analytics_df = st.session_state.filtered_projects_df.copy()

        analytics_df["Date Created"] = pd.to_datetime(analytics_df["Date Created"], errors='coerce')
        analytics_df.dropna(subset=["Date Created"], inplace=True) 

        # --- Key Stats for Analytics Dashboard (Duplicated from Project Browser) ---
        st.subheader("Current Project Statistics (Based on Applied Filters)")
        col_stats1, col_stats2 = st.columns(2)
        with col_stats1:
            st.metric(label="Total Projects Displayed", value=len(analytics_df))
        with col_stats2:
            total_submissions = analytics_df["Submission Count"].sum()
            st.metric(label="Total Submissions", value=f"{total_submissions:,}") 
        st.markdown("---") # Separator


        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("1. Number of Projects by Country")
            if not analytics_df.empty:
                assets_by_country = analytics_df["Country Label"].value_counts().reset_index()
                assets_by_country.columns = ["Country", "Project Count"] 
                
                chart_assets_by_country = alt.Chart(assets_by_country).mark_bar().encode(
                    y=alt.Y("Country:N", sort="-x", title="Country"),
                    x=alt.X("Project Count:Q", title="Number of Projects"),
                    tooltip=["Country", "Project Count"]
                ).properties(
                    title="Projects by Country"
                ).interactive()
                st.altair_chart(chart_assets_by_country, use_container_width=True)
            else:
                st.info("No project data to show analytics by country.")

            st.markdown("---")

            st.subheader("3. Submissions Trend for Top Projects")
            if not analytics_df.empty:
                max_slider_val = len(analytics_df)
                if max_slider_val == 0:
                    st.info("Not enough projects to configure top projects display.")
                elif max_slider_val == 1: # Handle single project case
                    st.info("Only one project available; displaying its submission trend.")
                    top_projects_for_chart = analytics_df.copy() # The single project
                    top_n_for_trend = 1 # For display text, not used by slider
                else: # max_slider_val >= 2, so slider is safe
                    top_n_for_trend = st.slider("Select number of top projects to display (for trend):", 1, min(10, max_slider_val), min(5, max_slider_val), key="top_projects_slider_tab2")
                    top_projects_for_chart = analytics_df.nlargest(top_n_for_trend, "Submission Count").copy()
                    
                if not analytics_df.empty: # Check analytics_df after handling max_slider_val == 1
                    if "top_projects_for_chart" in locals() and not top_projects_for_chart.empty:
                        chart_top_submissions = alt.Chart(top_projects_for_chart).mark_circle(size=100).encode(
                            x=alt.X("Date Created:T", title="Project Creation Date"),
                            y=alt.Y("Submission Count:Q", title="Submission Count"),
                            color=alt.Color("Name:N", title="Project Name"),
                            tooltip=["Name", alt.Tooltip("Date Created", format="%Y-%m-%d"), "Submission Count"]
                        ).properties(
                            title=f"Submission Count for Top {top_n_for_trend} Projects (at Creation Date)"
                        ).interactive()
                        st.altair_chart(chart_top_submissions, use_container_width=True)
                    else:
                        st.info(f"Not enough data to display top projects chart.") # Fallback if for some reason top_projects_for_chart is empty
                else:
                    st.info("No project data to show submission trends for top projects.")
            
            st.markdown("---")
            st.subheader("5. Projects by Source View")
            if "Source View Name" in analytics_df.columns and not analytics_df.empty:
                projects_by_source_view = analytics_df["Source View Name"].value_counts().reset_index()
                projects_by_source_view.columns = ["Source View", "Project Count"]
                
                chart_projects_by_source = alt.Chart(projects_by_source_view).mark_bar().encode(
                    y=alt.Y("Source View:N", sort="-x", title="Source View"),
                    x=alt.X("Project Count:Q", title="Number of Projects"),
                    tooltip=["Source View", "Project Count"]
                ).properties(
                    title="Projects by Source View"
                ).interactive()
                st.altair_chart(chart_projects_by_source, use_container_width=True)
            else:
                st.info("Source View data not available or no projects to display.")


        with chart_col2:
            st.subheader("2. Total Submissions per Individual Project")
            if not analytics_df.empty:
                max_slider_val_sub = len(analytics_df) # Use a distinct variable
                if max_slider_val_sub == 0:
                    st.info("Not enough projects to configure total submissions display.")
                elif max_slider_val_sub == 1: # Handle single project case
                    st.info("Only one project available; displaying its total submissions.")
                    projects_by_submissions = analytics_df.copy()
                    top_n_submissions_projects = 1 # For display text, not used by slider
                else: # max_slider_val_sub >= 2
                    top_n_submissions_projects = st.slider("Show Top N Projects by Submissions:", 1, min(20, max_slider_val_sub), min(10, max_slider_val_sub), key="top_sub_projects_slider")
                    projects_by_submissions = analytics_df.nlargest(top_n_submissions_projects, "Submission Count").copy()
                
                if not analytics_df.empty: # Check analytics_df after handling max_slider_val_sub == 1
                    if "projects_by_submissions" in locals() and not projects_by_submissions.empty:
                        projects_by_submissions.sort_values(by="Submission Count", ascending=False, inplace=True) 

                        chart_total_submissions_per_project = alt.Chart(projects_by_submissions).mark_bar().encode(
                            y=alt.Y("Name:N", sort="-x", title="Project Name"),
                            x=alt.X("Submission Count:Q", title="Total Submissions"),
                            tooltip=["Name", "Submission Count"]
                        ).properties(
                            title=f"Top {top_n_submissions_projects} Projects by Total Submissions"
                        ).interactive()
                        st.altair_chart(chart_total_submissions_per_project, use_container_width=True)
                    else:
                        st.info("No project data to show total submissions per project chart.") # Fallback
                else:
                    st.info("No project data to show total submissions per project.")

            st.markdown("---")

            st.subheader("4. Projects Created Over Time (Monthly)")
            if not analytics_df.empty:
                projects_created_monthly = analytics_df.groupby(pd.Grouper(key="Date Created", freq="M")).size().reset_index(name="Project Count")
                projects_created_monthly.columns = ["Month", "Project Count"]
                projects_created_monthly["Month"] = projects_created_monthly["Month"].dt.strftime("%Y-%m")

                if not projects_created_monthly.empty:
                    chart_projects_over_time = alt.Chart(projects_created_monthly).mark_bar().encode(
                        x=alt.X("Month:O", title="Month Created", sort=None), 
                        y=alt.Y("Project Count:Q", title="Number of Projects"),
                        tooltip=["Month", "Project Count"]
                    ).properties(
                        title="Number of Projects Created Per Month"
                    ).interactive()
                    st.altair_chart(chart_projects_over_time, use_container_width=True)
                else:
                    st.info("Not enough data to show projects created over time.")
            else:
                st.info("No project data to show creation trends.")

# --- Form Analyser Tab (Updated) ---
with tab3:
    st.header("KoboToolbox Form Analyser") 
    st.write("Analyze the data column names (question names) from the form definitions of your **currently filtered projects** and search for keywords.")

    # Button to trigger form content fetching and parsing
    if st.button("Analyze Forms from Filtered Projects", key="analyze_forms_button"): 
        if st.session_state.filtered_projects_df.empty:
            st.warning("Please load and filter projects in the 'Project Browser' tab first to enable form analysis.")
        elif not api_token or not server_url:
            st.error("Please enter both API Token and Server URL in the sidebar.")
        else:
            # ONLY reset form analysis states when this button is explicitly clicked
            st.session_state.xml_forms_processed = False 
            st.session_state.xml_form_details = []
            st.session_state.all_xml_column_names = set()
            st.session_state.keyword_match_results = pd.DataFrame() 

            with st.spinner("Fetching and analyzing form definitions... This may take a moment for many projects."): 
                form_data, unique_terms = kobo_api.fetch_and_parse_form_definitions( 
                    st.session_state.filtered_projects_df, 
                    api_token, 
                    server_url
                )
                st.session_state.xml_form_details = form_data 
                st.session_state.all_xml_column_names = sorted(list(unique_terms)) 
                st.session_state.xml_forms_processed = True
                
                if form_data: 
                    st.success(f"Successfully analyzed {len(form_data)} form definitions and found {len(unique_terms)} unique terms (including names and labels).") 
                else:
                    st.warning("No form definitions were processed from the filtered projects. This might be because no assets match your filters, or there was an issue fetching/parsing the definitions for the available assets. Check the 'Project Browser' tab for loaded assets and ensure your API token/server URL are correct.") 
    
    # Keyword search functionality
    if st.session_state.xml_forms_processed and st.session_state.xml_form_details:
        st.markdown("---")
        st.subheader("Search Data Column Names with Keywords")

        # Use on_change to update session state only when user explicitly changes value
        search_keywords_input = st.text_input(
            "Enter keywords (comma-separated):", 
            value=st.session_state.analyser_keywords_input,
            key="form_analyser_keywords_widget", # Unique key for the widget
            on_change=lambda: st.session_state.__setitem__('analyser_keywords_input', st.session_state.form_analyser_keywords_widget) # Update session state on change
        )
        # Use the session state variable for actual processing
        search_keywords = [kw.strip().lower() for kw in st.session_state.analyser_keywords_input.split(',') if kw.strip()]
        
        # Use session state for the slider as well
        fuzzy_threshold = st.slider(
            "Fuzzy Matching Threshold (%)", 
            0, 100, 
            value=st.session_state.analyser_fuzzy_threshold, 
            key="form_analyser_fuzzy_threshold_widget",
            on_change=lambda: st.session_state.__setitem__('analyser_fuzzy_threshold', st.session_state.form_analyser_fuzzy_threshold_widget)
        )
        
        st.markdown("##### Select Fuzzy Matching Method:")
        fuzzy_method_options = {
            "Simple Ratio (fuzz.ratio)": "Calculates general similarity; order and exactness matter more.",
            "Partial Ratio (fuzz.partial_ratio)": "Finds the best matching substring; good for phrases contained within longer strings.",
            "Token Sort Ratio (fuzz.token_sort_ratio)": "Sorts words alphabetically before comparing; ignores word order.",
            "Token Set Ratio (fuzz.token_set_ratio)": "**Recommended for most cases.** Compares unique word sets; robust to extra words, reordering, and varying lengths.", 
            "Weighted Ratio (fuzz.WRatio)": "A sophisticated general-purpose ratio that attempts to provide the 'best' score across various comparison types, handling case and punctuation well."
        }
        
        selected_fuzzy_method_name = st.radio(
            "Choose a method:",
            list(fuzzy_method_options.keys()),
            index=list(fuzzy_method_options.keys()).index(st.session_state.analyser_fuzzy_method), # Set default from session state
            help="Select the fuzzy matching algorithm based on your needs for string similarity.",
            key="fuzzy_method_selector_widget", # Unique key for widget
            on_change=lambda: st.session_state.__setitem__('analyser_fuzzy_method', st.session_state.fuzzy_method_selector_widget) # Update session state on change
        )
        st.info(f"**Method Description**: {fuzzy_method_options[selected_fuzzy_method_name]}")


        if st.button("Search Forms for Keywords", key="search_form_keywords_button"):
            if not search_keywords:
                st.warning("Please enter at least one keyword to search.")
            else:
                # Map selected method name to the actual fuzzywuzzy function
                fuzzy_function_map = {
                    "Simple Ratio (fuzz.ratio)": fuzz.ratio,
                    "Partial Ratio (fuzz.partial_ratio)": fuzz.partial_ratio,
                    "Token Sort Ratio (fuzz.token_sort_ratio)": fuzz.token_sort_ratio,
                    "Token Set Ratio (fuzz.token_set_ratio)": fuzz.token_set_ratio,
                    "Weighted Ratio (fuzz.WRatio)": fuzz.WRatio,
                }
                current_fuzzy_function = fuzzy_function_map[st.session_state.analyser_fuzzy_method] # Use session state for method


                results = []
                if st.session_state.all_loaded_assets_df.empty:
                    st.error("Project metadata not fully loaded. Please fetch assets in 'Project Browser' tab first.")
                else:
                    with st.spinner(f"Searching for keywords in {len(st.session_state.xml_form_details)} forms using {st.session_state.analyser_fuzzy_method}..."): # Use session state for method
                        for form_detail in st.session_state.xml_form_details:
                            form_name = form_detail["Form Name"]
                            form_uid = form_detail["UID"]
                            columns = form_detail["Columns"] 
                            
                            owner_username = "N/A"
                            matching_asset = st.session_state.all_loaded_assets_df[
                                st.session_state.all_loaded_assets_df['UID'] == form_uid
                            ]
                            if not matching_asset.empty:
                                owner_username = matching_asset['Owner Username'].iloc[0] 
                            
                            match_count = 0
                            matched_terms_for_display = [] 

                            for term in columns: 
                                for keyword in search_keywords: # Use search_keywords derived from analyser_keywords_input
                                    if current_fuzzy_function(str(term).lower(), keyword) >= st.session_state.analyser_fuzzy_threshold: # Use session state for threshold
                                        match_count += 1
                                        matched_terms_for_display.append(term) 
                                        break 

                            if match_count > 0:
                                results.append({
                                    "Form Name": form_name,
                                    "UID": form_uid,
                                    "Owner Username": owner_username,
                                    "Number of Keyword Matches": match_count,
                                    "Matched Terms": ", ".join(sorted(list(set(matched_terms_for_display)))) 
                                })
                    
                    st.session_state.keyword_match_results = pd.DataFrame(results)

                if not st.session_state.keyword_match_results.empty:
                    st.write(f"#### Forms with Keyword Matches (Threshold: {st.session_state.analyser_fuzzy_threshold}%, Method: {st.session_state.analyser_fuzzy_method})") # Use session state for display
                    st.dataframe(st.session_state.keyword_match_results, use_container_width=True)
                else:
                    st.info(f"No forms found with columns/labels matching your keywords above the set threshold using {st.session_state.analyser_fuzzy_method}.") # Use session state for display

    elif st.session_state.xml_forms_processed and not st.session_state.xml_form_details:
        st.warning("No form definitions were processed from the filtered projects. This might be because no assets match your filters, or there was an issue fetching/parsing the definitions for the available assets. Check the 'Project Browser' tab for loaded assets and ensure your API token/server URL are correct.") 
    else:
        st.info("Click 'Analyze Forms from Filtered Projects' above to start analyzing the form structures of your filtered KoboToolbox forms, then use the keyword search.") 


# --- New Data Export Tab ---
with tab4:
    st.header("Data Export Center")
    st.write("Download various types of data from your KoboToolbox projects.")

    if not st.session_state.assets_loaded:
        st.info("Please load project metadata in the 'Project Browser' tab first to enable export options.")
    elif st.session_state.filtered_projects_df.empty: 
        st.info("No projects are currently displayed/filtered. Please load assets and apply filters in the 'Project Browser' tab to enable export options.")
    else: # Only proceed with download buttons if there are projects to download
        
        # --- 1. Project Metadata Export ---
        st.subheader("1. Project Metadata Export (for All Displayed Projects)")
        excel_buffer_filtered = io.BytesIO()
        filtered_for_download = st.session_state.filtered_projects_df.copy()
        
        # Prepare 'Sector' column for display, converting dicts to strings for export
        if "Sector" in filtered_for_download.columns:
            filtered_for_download["Sector"] = filtered_for_download["Sector"].apply(lambda x: 
                (x.get('name') or x.get('label') or str(x)) if isinstance(x, dict) and x else (str(x) if x is not None else None)
            )
        
        # Convert datetime columns to timezone-naive for Excel compatibility
        for col in ["Date Created", "Date Modified"]:
            if pd.api.types.is_datetime64_any_dtype(filtered_for_download[col]) and filtered_for_download[col].dt.tz is not None:
                filtered_for_download[col] = filtered_for_download[col].dt.tz_localize(None)
        
        # Export ALL available columns in the filtered_projects_df
        filtered_for_download.to_excel(excel_buffer_filtered, index=False, columns=filtered_for_download.columns.tolist())
        excel_buffer_filtered.seek(0)
        st.download_button(
            "Download Displayed Project Metadata (Excel)", 
            data=excel_buffer_filtered, 
            file_name="displayed_projects_metadata.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Downloads all available metadata columns of projects currently displayed in the 'Project Browser' table."
        )

        st.markdown("---")

        # --- 2. XLSForm Downloads ---
        st.subheader("2. XLSForm Downloads (for All Displayed Projects)")
        st.info("This will download the raw XLSForm definition file for each project currently displayed/filtered.")
        
        uids_for_download = st.session_state.filtered_projects_df['UID'].tolist()
        names_for_download = st.session_state.filtered_projects_df['Name'].tolist() 

        if st.button("Download All Displayed XLS Forms (ZIP)", key="dl_all_xls_forms_displayed"):
            headers = {"Authorization": f"Token {api_token}"}
            zip_buffer_xls = io.BytesIO()
            progress_text_xls_dl_all = st.empty()
            progress_bar_xls_dl_all = st.progress(0)
            
            with zipfile.ZipFile(zip_buffer_xls, 'w') as zipf_xls:
                for i, uid in enumerate(uids_for_download):
                    form_name_info = names_for_download[i] 
                    clean_form_name = form_name_info.replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace('"', "_").replace("<", "_").replace(">", "_").replace("|", "_")
                    
                    xls_url = f"{server_url}/api/v2/assets/{uid}.xls" 
                    
                    progress_text_xls_dl_all.text(f"Downloading XLS for '{clean_form_name}' ({i+1}/{len(uids_for_download)})...")
                    progress_bar_xls_dl_all.progress((i + 1) / len(uids_for_download))
                    
                    try:
                        xls_res = requests.get(xls_url, headers=headers, timeout=10)
                        xls_res.raise_for_status()
                        if xls_res.status_code == 200:
                            zipf_xls.writestr(f"{clean_form_name}_{uid}.xls", xls_res.content)
                        else:
                            st.warning(f"XLS download failed for {uid} ({clean_form_name}): Status code {xls_res.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.warning(f"Error downloading XLS for {uid} ({clean_form_name}): {e}")
                        
            zip_buffer_xls.seek(0)
            progress_text_xls_dl_all.text("✅ All displayed XLS forms downloaded.")
            progress_bar_xls_dl_all.empty()
            st.download_button(
                "Click to Download All Displayed XLS Forms ZIP", 
                data=zip_buffer_xls.getvalue(), 
                file_name="kobotoolbox_all_displayed_xls_forms.zip", 
                mime="application/zip",
                key="dl_all_xls_final_displayed"
            )
            st.success("All Displayed XLS Forms ZIP is ready for download!")

        st.markdown("---")

        # --- 3. Raw Submission Data ---
        st.subheader("3. Raw Submission Data (for All Displayed Projects)")
        st.info("This will download the raw JSON submission data (flattened) for each project currently displayed/filtered. Each form's data will be a separate JSON file in a ZIP archive.")

        if st.button("Download All Displayed JSON Submissions (ZIP)", key="dl_all_json_submissions_displayed"):
            headers = {"Authorization": f"Token {api_token}"}
            zip_buffer_json_submissions = io.BytesIO()
            progress_text_json_dl_all = st.empty()
            progress_bar_json_dl_all = st.progress(0)
            
            st.warning("Downloading raw JSON submission data can be slow for large datasets. Data will be flattened from Kobo's API response.")
            with zipfile.ZipFile(zip_buffer_json_submissions, 'w') as zipf_json_sub:
                for i, uid in enumerate(uids_for_download):
                    form_name_info = names_for_download[i]
                    clean_form_name = form_name_info.replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace('"', "_").replace("<", "_").replace(">", "_").replace("|", "_")
                    
                    progress_text_json_dl_all.text(f"Downloading JSON submissions for '{clean_form_name}' ({i+1}/{len(uids_for_download)})...")
                    progress_bar_json_dl_all.progress((i + 1) / len(uids_for_download))
                    
                    submissions_df = kobo_api.fetch_submissions_data_from_v2_json(uid, api_token, server_url)
                    
                    if submissions_df is not None and not submissions_df.empty:
                        json_output_str = submissions_df.to_json(orient="records", indent=4)
                        zipf_json_sub.writestr(f"{clean_form_name}_{uid}_submissions.json", json_output_str)
                    else:
                        st.info(f"No submissions or failed to fetch for '{clean_form_name}' (UID: {uid}). Skipping JSON export for this form.")
                        
            zip_buffer_json_submissions.seek(0)
            progress_text_json_dl_all.text("✅ All displayed JSON submissions downloaded.")
            progress_bar_json_dl_all.empty()
            st.download_button(
                "Click to Download All Displayed JSON Submissions ZIP", 
                data=zip_buffer_json_submissions.getvalue(), 
                file_name="kobotoolbox_all_displayed_submissions_json.zip", 
                mime="application/zip",
                key="dl_all_json_final_displayed"
            )
            st.success("All Displayed JSON Submissions ZIP is ready for download!")
