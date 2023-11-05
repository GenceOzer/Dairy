from datetime import datetime
import time

import streamlit as st
import requests

st.set_page_config(page_title="Dairy", page_icon=None, layout="centered", initial_sidebar_state="auto", menu_items=None)


st.markdown(
    f'''
  <style>
  .appview-container .main .block-container{{
          padding-top: 1rem;    }}
  .st-emotion-cache-16txtl3{{
        padding-top: 4rem;    }}
  </style>
    ''',
    unsafe_allow_html=True,
)




st.markdown("""
<style>
div.stButton > button:first-child {
    background-color: #f6eee3;
    width: 100%;
    color: black;
}
</style>""", unsafe_allow_html=True)

st.markdown("""
<style>
.stTextArea textarea {
    background-color: #f6eee3;
    color: black;
    border: 2px solid #000000;
    font-size: 20px;
    font-family: "Times New Roman", Times, serif;
    font-style: italic;
}
</style>""", unsafe_allow_html=True)


def set_date(selected_date):
  st.session_state.selected_date=selected_date

today = datetime.today().date()

# Main page
if "selected_date" not in st.session_state:
  st.session_state.selected_date = today

with st.sidebar:
  st.image("dairy.png", width=200)
  buttons = []
  st.header("Your Latest Entries")
  entries = requests.get("http://localhost:8000/api/entries").json()
  buttons.append((today, st.button("Today")))
  sorted_entries = sorted(entries, reverse=True) 
  for entry in sorted_entries[:7]:
    if today.strftime("%Y-%m-%d") != entry:
      display_date = datetime.strptime(entry, "%Y-%m-%d").strftime("%B %d")
      buttons.append((datetime.strptime(entry, "%Y-%m-%d").date(), st.button(display_date)))
  
  for selected_date, dt_button in buttons:
    if dt_button:
      set_date(selected_date)
      break
  
  st.date_input(
    label="Diary date", 
    key="selected_date",
    value="today"
  )

  perspective_week_button = st.button("Reflect on the week")
  perspective_month_button = st.button("Reflect on the month") 


# Show the selected date
if perspective_week_button:
  resp = requests.get(f"http://localhost:8000/api/today-and-last-x-days?n_days=7").json()
  st.markdown(body=resp)
elif perspective_month_button:
  resp = requests.get(f"http://localhost:8000/api/today-and-last-x-days?n_days=30").json()
  st.markdown(body=resp)
else:
  date_str = st.session_state.selected_date.strftime('%B %d, %Y')
  st.title(f"{date_str}")

  # Find the text to be displayed
  resp = requests.get(f"http://localhost:8000/api/entries/{st.session_state.selected_date}").json()
  input_text = ""
  if "text" in resp:
    input_text = resp.get("text", "")

  if st.session_state.selected_date != today:
    text = st.text_area(label="", value=input_text, height=400, disabled=True)
  else:
    text = st.text_area(label="", value=input_text, placeholder="Write your thoughts here", height=400)

    if st.button("Add to diary"):
      with st.spinner('Adding to your diary'):
        data = {
          "date": time.strftime("%Y-%m-%d"),
          "text": text
        }
        resp = requests.post("http://localhost:8000/api/entries", json=data).json()
        formatted_body = f'<h3>Dairy says...</h3><br><p style="font-family:sans-serif; color:Black; font-size: 18px;">{resp["analysis_text"]}</p>'
        st.markdown(formatted_body, unsafe_allow_html=True)
