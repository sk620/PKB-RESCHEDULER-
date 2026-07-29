import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import tempfile
import os
import io
import re
import time
from collections import defaultdict

# --- ১. পেজ সেটিংস ---
st.set_page_config(
    page_title="Paired PDF to Excel Converter",
    page_icon="⚡",
    layout="centered"
)

st.title("⚡ Paired PDF to Excel Auto Converter")
st.write("আপনার ৫০-৬০ জোড়া বা একাধিক পার্টের PDF ফাইল একত্রে আপলোড করুন। অ্যাপটি স্বয়ংক্রিয়ভাবে জোড়া চিনে Excel-এর প্রতি সারিতে নির্ভুল ডাটা বসিয়ে দেবে।")

# --- ২. সাইলেন্ট API Key রিড (Streamlit Secrets) ---
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))

if not API_KEY:
    st.error("⚠️ Server Configuration Error: Gemini API Key পাওয়া যায়নি! Streamlit Secrets-এ API Key সেট করুন।")
    st.stop()

genai.configure(api_key=API_KEY)

# --- ৩. এক্সট্রাকশন কলাম কনফিগারেশন ---
with st.expander("⚙️ এক্সট্র্যাক্ট করার কলামসমূহ (প্রয়োজনে পরিবর্তন করতে পারেন)"):
    fields_input = st.text_input(
        "কলামের নামসমূহ (কমা দিয়ে লিখুন):",
        value="Name, Registration No, Date, Total Amount, Address"
    )

# --- ৪. পিডিএফ ফাইল আপলোড ---
uploaded_files = st.file_uploader(
    "আপনার সকল PDF ফাইল সিলেক্ট বা ড্রপ করুন (যেমন: res1 1, res1 2, res2 1, res2 2...)", 
    type=["pdf"], 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("🚀 প্রসেসিং শুরু করুন", type="primary", use_container_width=True):
        
        # --- ফাইল অটো-গ্রুপিং লজিক ---
        # "res1 1", "res1 2" -> Group: "res1"
        # "res 2 1", "res 2 2" -> Group: "res 2"
        # "res1_part1", "res1_part2" -> Group: "res1"
        grouped_files = defaultdict(list)
        
        for file in uploaded_files:
            filename_without_ext = os.path.splitext(file.name)[0].strip()
            
            # নাম থেকে শেষ অংশটি (পার্ট নম্বর) আলাদা করার Regex
            match = re.match(r'^(.*?)[_\s\-\.]+(?:part|p)?(\d+|[a-zA-Z])$', filename_without_ext, re.IGNORECASE)
            
            if match:
                group_id = match.group(1).strip()  # যেমন: "res1" বা "res 2"
                part_identifier = match.group(2)   # যেমন: "1", "2" বা "a", "b"
            else:
                group_id = filename_without_ext
                part_identifier = "1"
                
            grouped_files[group_id].append((part_identifier, file))

        # গ্রুপের ভেতর ফাইলগুলো ক্রমানুসারে সাজানো
        for g_id in grouped_files:
            grouped_files[g_id].sort(key=lambda x: str(x[0]))

        total_groups = len(grouped_files)
        st.info(f"📁 মোট {total_groups} টি অনন্য রেকর্ড/জোড়া সনাক্ত করা হয়েছে। (মোট ফাইল: {len(uploaded_files)} টি)")

        model = genai.GenerativeModel("gemini-1.5-flash")
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        # --- ব্যাচ প্রসেসিং লুপ ---
        for idx, (group_id, file_list) in enumerate(grouped_files.items()):
            file_names_str = ", ".join([f[1].name for f in file_list])
            status_text.info(f"⏳ প্রসেস হচ্ছে [{idx+1}/{total_groups}]: আইডি '{group_id}' ({len(file_list)} টি ফাইল)")

            remote_files = []
            tmp_paths = []

            try:
                # গ্রুপের সকল পিডিএফ টেম্পোরারি সেভ ও Gemini-তে আপলোড
                for _, file_obj in file_list:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(file_obj.read())
                        tmp_paths.append(tmp.name)
                    
                    remote_file = genai.upload_file(tmp.name)
                    remote_files.append(remote_file)

                prompt = f"""
                You are an expert document OCR and data extraction system.
                You are provided with {len(file_list)} PDF file(s) belonging to a single record/person (ID: {group_id}).
                Combine information from ALL attached pages/files to extract a SINGLE consolidated record.

                REQUIRED FIELDS TO EXTRACT: {fields_input}

                RULES & INSTRUCTIONS:
                1. The documents contain Bengali, English, or mixed text. Perform 100% accurate OCR transcription.
                2. Preserve Bengali spellings and accurate numeric characters exactly as written.
                3. Merge relevant information across all provided file parts into one single JSON object.
                4. Return ONLY a valid, pure JSON object without markdown formatting or introductory text.
                5. Keys of JSON MUST match exact field names: {fields_input}. If a field is missing, set its value to null.
                """

                # জেমিনাই-তে সব ফাইল একত্রে পাঠানো
                response = model.generate_content(remote_files + [prompt])

                # JSON ক্লিন-আপ
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()

                extracted_data = json.loads(raw_text)
                extracted_data["Record ID"] = group_id
                extracted_data["Processed Files"] = file_names_str
                results.append(extracted_data)

            except Exception as e:
                st.error(f"❌ আইডি [{group_id}] প্রসেসিং ত্রুটি: {str(e)}")
                results.append({
                    "Record ID": group_id,
                    "Processed Files": file_names_str,
                    "Error": str(e)
                })
            finally:
                # লোকাল টেম্পোরারি ফাইল রিমুভ
                for p in tmp_paths:
                    if os.path.exists(p):
                        os.remove(p)
                # Gemini সার্ভার থেকে রিমোট ফাইল ক্লিনআপ
                for rf in remote_files:
                    try:
                        genai.delete_file(rf.name)
                    except Exception:
                        pass

            # প্রোগ্রেস বার আপডেট
            progress_bar.progress((idx + 1) / total_groups)

            # API Rate Limit (Error 429) এড়াতে ৪ সেকেন্ডের বিরতি (৫০-৬০ জোড়ার বড় ব্যাচের জন্য)
            if idx < total_groups - 1:
                time.sleep(4)

        status_text.success(f"🎉 অভিনন্দন! সকল {total_groups} টি রেকর্ডের তথ্য সফলভাবে এক্সট্র্যাক্ট করা হয়েছে!")

        # --- রেজাল্ট প্রদর্শন ও এক্সেল ডাউনলোড ---
        if results:
            df = pd.DataFrame(results)
            
            # 'Record ID' ও 'Processed Files' কলাম দুটি সবার সামনে আনা
            cols = ["Record ID", "Processed Files"] + [c for c in df.columns if c not in ["Record ID", "Processed Files"]]
            df = df[cols]

            st.subheader("📊 ফলাফল প্রিভিউ")
            st.dataframe(df, use_container_width=True)

            # ইন-মেমোরি এক্সেল স্ট্রিম
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Extracted_Data')
            excel_data = buffer.getvalue()

            st.download_button(
                label="📥 চূড়ান্ত Excel ফাইল ডাউনলোড করুন (.xlsx)",
                data=excel_data,
                file_name="paired_pdf_extracted_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
