import streamlit as st
import pdfplumber
import pandas as pd
import io

st.set_page_config(page_title="PDF to Excel Converter", page_icon="📊")

st.title("📄 PDF to Excel Converter (No API Required)")
st.write("যেযেকোনো সিলেক্টেবল PDF আপলোড করুন, সরাসরি Excel ফাইল ডাউনলোড করুন।")

uploaded_files = st.file_uploader("আপনার PDF ফাইলগুলো সিলেক্ট করুন", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    all_rows = []
    
    with st.spinner("PDF থেকে ডাটা এক্সট্র্যাক্ট করা হচ্ছে..."):
        for pdf_file in uploaded_files:
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    # ১. প্রথমে টেবিল এক্সট্র্যাক্ট করার চেষ্টা করবে
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            # খালি সারি বাদ দেওয়া
                            if any(row):
                                all_rows.append(row)
                    
                    # ২. যদি নির্দিষ্ট কোনো টেবিল স্ট্রাকচার না থাকে, তবে সাধারণ টেক্সট লাইন বাই লাইন পড়বে
                    if not tables:
                        text = page.extract_text()
                        if text:
                            lines = text.split("\n")
                            for line in lines:
                                # স্পেস দিয়ে কলাম ভাগ করা
                                parts = line.split()
                                if parts:
                                    all_rows.append(parts)

    if all_rows:
        # ডাটাফ্রেমে রূপান্তর
        df = pd.DataFrame(all_rows)
        
        st.success("✅ ডাটা সফলতা সাথে এক্সট্র্যাক্ট করা হয়েছে!")
        st.write("### Extracted Data Preview", df.head(10))
        
        # Excel ফাইলে সেভ করার বাফার
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, header=False, sheet_name='PDF_Data')
        
        excel_data = output.getvalue()
        
        # ডাউনলোড বাটন
        st.download_button(
            label="📥 Download Excel File",
            data=excel_data,
            file_name="extracted_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("PDF থেকে কোনো ডাটা পড়া সম্ভব হয়নি।")
