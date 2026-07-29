import streamlit as st
import pandas as pd
from pypdf import PdfReader
from openai import OpenAI
import json
import io

st.set_page_config(page_title="PDF to Excel Converter", page_icon="📊", layout="wide")

st.title("📊 AI PDF to Excel Converter")
st.write("আপনার PDF ফাইলটি আপলোড করুন, AI সম্পূর্ণ ডাটা এক্সট্র্যাক্ট করে Excel ফাইলেই রূপান্তর করে দেবে।")

# Sidebar settings
with st.sidebar:
    st.header("⚙️ Settings")
    token_from_secrets = st.secrets.get("GITHUB_TOKEN", "")
    github_token = token_from_secrets if token_from_secrets else st.text_input("GitHub Token:", type="password")
    
    selected_model = st.selectbox(
        "Model Choice:",
        ["gpt-4o", "gpt-4o-mini", "meta-llama-3.3-70b-instruct"]
    )

# File Uploader
uploaded_file = st.file_uploader("PDF ফাইল আপলোড করুন (Max 200KB Text Recommended)", type=["pdf"])

if uploaded_file and st.button("🚀 Convert to Excel"):
    if not github_token:
        st.error("দয়া করে সাইডবারে আপনার GitHub Token দিন।")
        st.stop()
        
    with st.spinner("PDF থেকে লেখা পড়া হচ্ছে..."):
        # 1. Read PDF Text
        pdf_reader = PdfReader(uploaded_file)
        extracted_text = ""
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"

    if not extracted_text.strip():
        st.error("PDF টি থেকে কোনো টেক্সট পাওয়া যায়নি। (এটি হয়তো কোনো স্ক্যান করা ইমেজ PDF)।")
        st.stop()

    with st.spinner("AI ডাটা প্রসেস করে টেবিল তৈরি করছে..."):
        try:
            client = OpenAI(
                base_url="https://models.inference.ai.azure.com",
                api_key=github_token
            )

            prompt = f"""
            Extract all tabular data or structured data from the following text and return it as a JSON array of objects.
            Each object represents a row where keys are column names.
            Do NOT include markdown wrapping like ```json. Just raw JSON string.

            Text:
            {extracted_text[:4000]}  # Limiting length for safety
            """

            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": "You are a data extraction assistant that outputs strictly raw JSON arrays."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            result_text = response.choices[0].message.content.strip()
            
            # Clean response if markdown blocks exist
            if result_text.startswith("```"):
                result_text = result_text.replace("```json", "").replace("```", "").strip()

            # 2. Convert JSON to Pandas DataFrame
            data_json = json.loads(result_text)
            df = pd.DataFrame(data_json)

            st.success("✅ ডাটা এক্সট্র্যাকশন সফল হয়েছে!")
            st.subheader("📋 Preview Data")
            st.dataframe(df, use_container_width=True)

            # 3. Create Downloadable Excel File in memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
            excel_data = output.getvalue()

            st.download_button(
                label="📥 Download Excel File (.xlsx)",
                data=excel_data,
                file_name="converted_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Error occurred: {str(e)}")
