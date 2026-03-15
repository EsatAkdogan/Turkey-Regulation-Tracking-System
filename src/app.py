import streamlit as st
from scraper import RegulationScraper
from storage import RegulationStorage
from llm import LLMSummarizer
import datetime

st.set_page_config(page_title="Turkey Regulation Tracker", layout="wide", page_icon="⚖️")

st.title("Turkey Regulation Tracking System")
st.markdown("""
**Monitor and track Turkish legal developments** across multiple official sources including the Official Gazette, KVKK, MEB, GİB, BDDK, SPK, EPDK, BTK, and more.
""")

st.sidebar.header("Control Panel")

@st.cache_resource
def get_modules():
    scraper = RegulationScraper()
    storage = RegulationStorage()
    llm = LLMSummarizer()
    return scraper, storage, llm

scraper, storage, llm = get_modules()

if st.sidebar.button("Run Daily Scan"):
    with st.spinner("Scanning Turkish official sources..."):
        new_regs = scraper.fetch_regulations()
        count = 0
        for reg in new_regs:
            if storage.add_regulation(reg):
                count += 1
        
        if count > 0:
            st.sidebar.success(f"{count} new records added to local database.")
        else:
            st.sidebar.info("No new updates found for today.")

st.sidebar.markdown("---")
st.sidebar.info("""
**Monitored Turkish Sources:**
- Official Gazette (Resmi Gazete)
- Personal Data Protection (KVKK)
- Ministry of Education (MEB)
- Revenue Administration (GİB)
- Banking Regulation (BDDK)
- Capital Markets Board (SPK)
- Energy Market Board (EPDK)
- Competition Authority (Rekabet)
- Information Tech Board (BTK)
""")

# Search section
st.markdown("Search Regulations")

col1, col2 = st.columns([3, 1])
with col1:
    search_query = st.text_input("Search query", placeholder="Search for regulations...")
with col2:
    time_range = st.selectbox("Search range", ["Last 7 Days", "Last 30 Days", "Last 1 Year", "Last 10 Years"], index=1)

if st.button("Search All Sources", type="primary", use_container_width=True):
    if not search_query:
        st.warning("Please enter a search term.")
    else:
        st.session_state['search_results'] = []
        st.session_state['last_query'] = search_query
        
        with st.spinner(f"Searching for '{search_query}'..."):
            try:
                days_to_scrape = 3650
                if time_range == "Last 7 Days":
                    days_to_scrape = 7
                elif time_range == "Last 30 Days":
                    days_to_scrape = 30
                elif time_range == "Last 1 Year":
                    days_to_scrape = 365
                
                st.info(f"Scanning sources over the last {days_to_scrape} days...")
                
                # Check local 
                local_results = storage.search_regulations(search_query)
                if local_results:
                    st.session_state['search_results'].extend(local_results)
                    st.toast(f"Retrieved {len(local_results)} local matches.")
                
                seen_links = {r.get('link') or r.get('url') for r in local_results}
                
                #Show online results
                for online_batch in scraper.search_online(search_query, days=days_to_scrape):
                    new_results = []
                    for res in online_batch:
                        link = res.get('link') or res.get('url')
                        if link not in seen_links:
                            new_results.append(res)
                            seen_links.add(link)
                    
                    if new_results:
                        st.session_state['search_results'].extend(new_results)
                        st.session_state['search_results'].sort(key=lambda x: x.get('date', ''), reverse=True)
                        st.rerun() 
                
                st.success(f"Search completed. Found {len(st.session_state['search_results'])} total matches.")
            except Exception as e:
                st.error(f"An error occurred during search: {str(e)}")

#Results display
if 'search_results' in st.session_state and st.session_state['search_results']:
    results = st.session_state['search_results']
    st.markdown(f"**Matches Found ({len(results)}):**")
    for i, result in enumerate(results):
        link = result.get('link', result.get('url', '#'))
        source = result.get('source', 'Official Source')
        date = result.get('date', 'Unknown Date')
        
        with st.expander(f"{date} | {result.get('title', 'Untitled')} | {source}"):
            st.markdown(f"**Source:** [{source}]({link})")
            st.markdown(f"**Date:** {date}")
            
            
            content_preview = result.get('content', '')[:500] + "..." if result.get('content') else "No content available."
            st.markdown("**Content Preview:**")
            st.write(content_preview)
            
            
            summary_key = f"summary_{i}"
            if st.button("Summarize with AI", key=f"btn_{i}"):
                with st.spinner("Generating AI summary..."):
                    if result.get('content'):
                        summary = llm.summarize(result['content'])
                        st.session_state[summary_key] = summary
                    else:
                        st.warning("No content available to summarize.")
            
            if summary_key in st.session_state:
                st.info(f"**AI Summary:**\n\n{st.session_state[summary_key]}")
            
            st.markdown("---")
            st.markdown(f"[View Original Source]({link})")

st.markdown("---")
st.caption("Turkey Regulation Tracking System - Production Ready")
