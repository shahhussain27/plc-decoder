import streamlit as st
import pandas as pd
import json
import tempfile
import os
from pathlib import Path

# Import our backend modules
from parser.hex_parser import HexParser
from configs.config_loader import load_template
from exporters.excel_exporter import ExcelExporter
from utils.file_reader import FileReader

st.set_page_config(page_title="PLC Decoder Web", page_icon="⚙️", layout="wide")

st.title("⚙️ PLC Decoder Web App")
st.markdown("Decode LiraNET / Mitsubishi FX5U PLC hex data into clean Excel reports directly in your browser.")

# 1. Configuration (cached so we don't load it every time)
@st.cache_data
def get_config():
    return load_template("liranet_fx5u")

config = get_config()

# 2. File Upload Area
st.subheader("1. Upload Data")
uploaded_file = st.file_uploader(
    "Select PLC Data File (TXT, CSV, BIN)", 
    type=["txt", "csv", "bin", "hex", "log", "dat"]
)

if uploaded_file is not None:
    # Save the uploaded file to a temporary file for our FileReader
    suffix = f".{uploaded_file.name.split('.')[-1]}" if "." in uploaded_file.name else ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
        
    try:
        reader = FileReader(tmp_path)
        hex_data = reader.hex_data
        
        st.success(f"✅ File loaded! Hex bytes: {len(hex_data)//2:,}")
        
        # 3. Parse Button
        st.subheader("2. Parse and Preview")
        if st.button("▶️ Parse Data", type="primary"):
            with st.spinner("Parsing packet data..."):
                parser = HexParser(config)
                records = parser.parse_hex_stream(hex_data)
                stats = parser.get_stats()
                errors = parser.get_errors()
                
                # Show metric cards
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Packets", stats.total_packets)
                col2.metric("Valid Packets", stats.valid_packets)
                col3.metric("Invalid Packets", stats.invalid_packets)
                col4.metric("Success Rate", f"{stats.success_rate:.1f}%")
                
                # Show preview table
                if records:
                    st.markdown("### 📋 Decoded Records Preview")
                    df = pd.DataFrame([r.to_flat_dict() for r in records])
                    st.dataframe(df, use_container_width=True)
                    
                    # 4. Download Export
                    st.subheader("3. Export Report")
                    
                    # Save the Excel to a temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_xl:
                        xl_path = tmp_xl.name
                    
                    exporter = ExcelExporter(xl_path, config)
                    exporter.export(records, stats, errors, uploaded_file.name)
                    
                    # Provide the file download
                    with open(xl_path, "rb") as f:
                        btn = st.download_button(
                            label="💾 Download Excel Report",
                            data=f,
                            file_name=f"{uploaded_file.name.split('.')[0]}_decoded.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary"
                        )
                    os.unlink(xl_path)  # cleanup excel temp file
                else:
                    st.warning("No records could be parsed. Please check the file contents.")
    finally:
        os.unlink(tmp_path)  # cleanup uploaded temp file
else:
    st.info("Please upload a file to begin.")
