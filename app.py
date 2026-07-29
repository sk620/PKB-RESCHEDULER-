import streamlit as st
import google.generativeai as genai
import pdfplumber
import pandas as pd
import json
import io

st.set_page_config(page_title="AI Powered PDF to Excel", page_icon="🤖", layout="wide")

st.title("🤖 AI-Powered PDF to Excel Converter")
st.write("PDF ফাইল আপলোড করুন এবং আপনার ইচ্ছেমতো প্রম্পট দিয়ে ডাটা কাস্টমাইজ করে Excel ফাইল ডাউনলোড করুন।")

# --- ১. API Key কনফিগারেশন ---
# Secrets থেকে API Key নেওয়ার চেষ্টা করবে, না পেলে ইনপুট বক্স দেখাবে
api_key = st.secrets.get("GEMINI_API_KEY", "")

if not api_key:
    api_key = st.text_input("Gemini API Key দিন:", type="password")

if api_key:
    # Key-এর চারপাশের কোনো স্পেস বা কোটেশন মুছে ফেলা
    clean_api_key = str(api_key).strip().strip('"').strip("'")
    genai.configure(api_key=clean_api_key)

# --- ২. ইউজার ইন্টারফেস ---
col1, col2 = st.columns([1, 1])

with col1:
    uploaded_files = st.file_uploader("PDF ফাইল সিলেক্ট করুন", type=["pdf"], accept_multiple_files=True)

with col2:
    custom_prompt = st.text_area(
        "কাস্টমাইজেশন নির্দেশাবলী (Custom Instructions):",
        value="PDF থেকে সমস্ত গুরুত্বপূর্ণ ডাটা টেবিল আকারে বের করো। প্রতিটি রেকর্ড যেন একটি JSON Object হয় এবং কলামের নামগুলো বাংলায় বা ইংরেজিতে অর্থপূর্ণ হয়।",
        height=150,
        help="এখানে আপনি AI-কে নির্দিষ্ট নির্দেশনা দিতে পারেন (যেমন: 'শুধুমাত্র তারিখ ও টাকার পরিমাণ বের করো', 'অপ্রয়োজনীয় রো বাদ দাও' ইত্যাদি)।"
    )

process_btn = st.button("🚀 Process & Generate Excel", type="primary")

# --- ৩. ডাটা প্রসেসিং লজিক ---
if process_btn:
    if not api_key:
        st.error("⚠️ অনুগ্রহ করে API Key প্রদান করুন!")
    elif not uploaded_files:
        st.warning("⚠️ অন্তত একটি PDF ফাইল আপলোড করুন!")
    else:
        all_extracted_data = []
        
        with st.spinner("AI ডাটা প্রসেস ও কাস্টমাইজ করছে... অনুগ্রহ করে অপেক্ষা করুন..."):
            try:
                # Gemini Model প্রস্তুত করা (JSON Mode অন করা হয়েছে)
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    generation_config={"response_mime_type": "application/json"}
                )

                for pdf_file in uploaded_files:
                    # PDF থেকে টেক্সট বের করা
                    raw_text = ""
                    with pdfplumber.open(pdf_file) as pdf:
                        for page in pdf.pages:
                            raw_text += (page.extract_text() or "") + "\n"

                    if not raw_text.strip():
                        st.warning(f"'{pdf_file.name}' ফাইলটিতে কোনো সিলেক্টেবল টেক্সট পাওয়া যায়নি।")
                        continue

                    # AI-এর জন্য প্রম্পট সাজানো
                    full_prompt = f"""
                    You are a data extraction expert. Extract information from the provided PDF text according to these instructions:
                    
                    USER INSTRUCTIONS:
                    {custom_prompt}

                    CRITICAL REQUIREMENT:
                    Return ONLY a JSON Array of objects (list of dictionaries). Do NOT wrap it in markdown code blocks like ```json.
                    Example format:
                    [
                        {{"Column1": "Value1", "Column2": "Value2"}},
                        {{"Column1": "Value3", "Column2": "Value4"}}
                    ]

                    PDF TEXT CONTENT:
                    {raw_text}
                    """

                    # Gemini API কল করা
                    response = model.generate_content(full_prompt)
                    
                    # JSON পার্স করা
                    data = json.loads(response.text)
                    
                    if isinstance(data, list):
                        all_extracted_data.extend(data)
                    elif isinstance(data, dict):
                        all_extracted_data.append(data)

                if all_extracted_data:
                    # Pandas DataFrame তৈরি
                    df = pd.DataFrame(all_extracted_data)
                    
                    st.success("✅ প্রসেসিং সফল হয়েছে!")
                    st.write("### 📊 Extracted Data Preview", df)

                    # Excel ফাইলে রূপান্তর
                    excel_output = io.BytesIO()
                    with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Custom_Data')
                    
                    # Download Button
                    st.download_button(
                        label="📥 Download Excel File",
                        data=excel_output.getvalue(),
                        file_name="custom_extracted_data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.error("AI কোনো ডাটা প্রসেস করতে পারেনি। প্রম্পটটি কিছুটা পরিবর্তন করে চেষ্টা করুন।")

            except json.JSONDecodeError:
                st.error("❌ AI সঠিক JSON ফরম্যাটে ডাটা ফেরত পাঠাতে পারেনি। অনুগ্রহ করে প্রম্পটটি আরেকটু স্পষ্ট করে লিখুন।")
            except Exception as e:
                st.error(f"❌ এরর ঘটেছে: {str(e)}")
