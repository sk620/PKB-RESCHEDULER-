import streamlit as st
from openai import OpenAI
import pdfplumber
import pandas as pd
import json
import io

st.set_page_config(page_title="AI PDF to Excel (OpenAI)", page_icon="🤖", layout="wide")

st.title("🤖 PDF to Excel Converter (OpenAI Powered)")
st.write("PDF ফাইল আপলোড করুন এবং OpenAI AI-এর সাহায্যে ইচ্ছামতো কাস্টমাইজ করে Excel ফাইল ডাউনলোড করুন।")

# --- ১. OpenAI API Key কনফিগারেশন ---
api_key = st.secrets.get("OPENAI_API_KEY", "")

if not api_key:
    api_key = st.text_input("OpenAI API Key দিন (sk-...):", type="password")

# --- ২. ইউজার ইন্টারফেস ---
col1, col2 = st.columns([1, 1])

with col1:
    uploaded_files = st.file_uploader("PDF ফাইল সিলেক্ট করুন", type=["pdf"], accept_multiple_files=True)

with col2:
    custom_prompt = st.text_area(
        "কাস্টমাইজেশন নির্দেশাবলী (Custom Instructions):",
        value="PDF থেকে সমস্ত তথ্য সুন্দরভাবে কলাম আকারে বের করো।",
        height=150
    )

process_btn = st.button("🚀 Process & Generate Excel", type="primary")

# --- ৩. প্রসেসিং লজিক ---
if process_btn:
    if not api_key:
        st.error("⚠️ অনুগ্রহ করে OpenAI API Key প্রদান করুন!")
    elif not uploaded_files:
        st.warning("⚠️ অন্তত একটি PDF ফাইল আপলোড করুন!")
    else:
        all_extracted_data = []
        client = OpenAI(api_key=api_key.strip())
        
        with st.spinner("OpenAI ডাটা প্রসেস করছে..."):
            try:
                for pdf_file in uploaded_files:
                    raw_text = ""
                    with pdfplumber.open(pdf_file) as pdf:
                        for page in pdf.pages:
                            raw_text += (page.extract_text() or "") + "\n"

                    if not raw_text.strip():
                        st.warning(f"'{pdf_file.name}' ফাইলটিতে কোনো লেখা পাওয়া যায়নি।")
                        continue

                    # OpenAI API Call (JSON Mode অন করা)
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        response_format={"type": "json_object"},
                        messages=[
                            {
                                "role": "system", 
                                "content": "You extract structured data from text into a JSON object. You MUST return a JSON object with a single key 'data' containing an array of objects/records."
                            },
                            {
                                "role": "user", 
                                "content": f"Instructions: {custom_prompt}\n\nPDF Content:\n{raw_text}"
                            }
                        ]
                    )

                    result_text = response.choices[0].message.content
                    parsed_json = json.loads(result_text)
                    
                    # 'data' কি থেকে লিস্ট বের করা
                    records = parsed_json.get("data", parsed_json)
                    
                    if isinstance(records, list):
                        all_extracted_data.extend(records)
                    elif isinstance(records, dict):
                        all_extracted_data.append(records)

                if all_extracted_data:
                    df = pd.DataFrame(all_extracted_data)
                    st.success("✅ সফলভাবে প্রসেস করা হয়েছে!")
                    st.write("### 📊 Extracted Data Preview", df)

                    # Excel তৈরি
                    excel_output = io.BytesIO()
                    with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Data')

                    st.download_button(
                        label="📥 Download Excel File",
                        data=excel_output.getvalue(),
                        file_name="extracted_data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.error("কোনো ডাটা প্রসেস করা সম্ভব হয়নি।")

            except Exception as e:
                st.error(f"❌ এরর ঘটেছে: {str(e)}")
