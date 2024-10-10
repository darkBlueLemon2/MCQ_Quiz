import streamlit as st
import pandas as pd
import json
import os
from github import Github
from github import Auth
import base64
import time
import threading
import queue

# GitHub setup
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = "darkBlueLemon2/MCQ_Quiz"
BRANCH_NAME = "main"

auth = Auth.Token(GITHUB_TOKEN)
g = Github(auth=auth)
repo = g.get_repo(REPO_NAME)

# Queue for save operations
save_queue = queue.Queue()

# @st.cache_data
def load_questions(file):
    df = pd.read_csv(file)
    questions = df.to_dict('records')
    for q in questions:
        q['options'] = q['options'].split('|')
    return questions

# @st.cache_data
def get_file_content(filename):
    try:
        content = repo.get_contents(f"data/{filename}", ref=BRANCH_NAME)
        return base64.b64decode(content.content).decode('utf-8')
    except:
        return None

def save_file_content(filename, content):
    try:
        file = repo.get_contents(f"data/{filename}", ref=BRANCH_NAME)
        repo.update_file(file.path, f"Update {filename}", content, file.sha, branch=BRANCH_NAME)
    except:
        repo.create_file(f"data/{filename}", f"Create {filename}", content, branch=BRANCH_NAME)

@st.cache_data
def load_progress(filename):
    progress_filename = f"{filename}_progress.json"
    content = get_file_content(progress_filename)
    if content:
        return json.loads(content)
    return {}

def save_progress(progress, filename):
    progress_filename = f"{filename}_progress.json"
    content = json.dumps(progress)
    save_queue.put((progress_filename, content))

def save_worker():
    while True:
        try:
            filename, content = save_queue.get(timeout=1)
            save_file_content(filename, content)
            save_queue.task_done()
        except queue.Empty:
            continue

def start_save_thread():
    save_thread = threading.Thread(target=save_worker, daemon=True)
    save_thread.start()

def periodic_save(progress, filename):
    current_time = time.time()
    if current_time - st.session_state.last_save_time > 0:  # Save every 5 minutes
        save_progress(progress, filename)
        st.session_state.last_save_time = current_time

@st.cache_data
def list_csv_files():
    contents = repo.get_contents("data", ref=BRANCH_NAME)
    return [content.name for content in contents if content.name.endswith('.csv')]

def find_first_unanswered_question(progress, total_questions):
    for i in range(total_questions):
        if str(i) not in progress:
            return i
    return total_questions

def display_quiz(file_path):
    questions = load_questions(file_path)
    filename = os.path.splitext(os.path.basename(file_path))[0]
    
    if 'progress' not in st.session_state:
        st.session_state.progress = load_progress(filename)
    
    if 'current_question' not in st.session_state:
        st.session_state.current_question = find_first_unanswered_question(st.session_state.progress, len(questions))

    if st.session_state.current_question < len(questions):
        question = questions[st.session_state.current_question]
        st.markdown(f"### Question {question['question_number']}")
        st.write(question['question'])

        current_progress = st.session_state.progress.get(str(st.session_state.current_question), {})
        if current_progress:
            selected_option = current_progress['selected']
            selected_index = question['options'].index(selected_option) if selected_option in question['options'] else None
        else:
            selected_index = None

        selected_option = st.radio("Choose an option:", question['options'], key=f"q{st.session_state.current_question}", index=selected_index)

        # col1, col2 = st.columns(2)
        col1, col2, _ = st.columns([1, 1, 1])
        with col1:
            if st.button("Previous", key="previous_button"):
                st.session_state.current_question = max(0, st.session_state.current_question - 1)
                st.rerun()
        with col2:
            if st.button("Next", key="next_button"):
                st.session_state.progress[str(st.session_state.current_question)] = {
                    'selected': selected_option,
                }
                periodic_save(st.session_state.progress, filename)
                st.session_state.current_question += 1
                st.rerun()
    else:
        correct_answers = 0
        total_questions = len(questions)

        for i, (q, result) in enumerate(st.session_state.progress.items()):
            question = questions[int(q)]
            if result['selected'] == question['correct_option']:
                correct_answers += 1

        st.markdown(f"### Your score: {correct_answers}/{total_questions}")

        incorrect_questions = [
            (questions[int(q)], result)
            for q, result in st.session_state.progress.items()
            if result['selected'] != questions[int(q)]['correct_option']
        ]

        if incorrect_questions:
            st.markdown("---")
            st.subheader("Review Incorrect Answers:")
            for question, result in incorrect_questions:
                # st.markdown(f"#### Question {question['question_number']}")
                st.markdown(f"<h4 style='color: #ff4b4b;'>Question {question['question_number']}</h4>", unsafe_allow_html=True)
                st.write(question['question'])
                st.write("Options:")
                for option in question['options']:
                    st.write(f"- {option}")
                st.warning(f"Your answer: {result['selected']}")
                st.success(f"Correct answer: {question['correct_option']}")
                st.markdown("---")

        if st.button("Restart Quiz", key="restart_button"):
            st.session_state.current_question = 0
            st.session_state.progress = {}
            save_progress(st.session_state.progress, filename)
            st.rerun()

def main():
    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = False
    
    # st.set_page_config(page_title="Multiple Choice Quiz App", page_icon=":question:", layout="wide")
    st.set_page_config(page_title="Multiple Choice Quiz App", page_icon=":question:")
    
    if not st.session_state.quiz_started:
        st.title("Multiple Choice Quiz")

    # Start the save thread
    start_save_thread()

    # Initialize last_save_time
    if 'last_save_time' not in st.session_state:
        st.session_state.last_save_time = time.time()

    csv_files = list_csv_files()

    # Display filenames without extensions
    file_options = [os.path.splitext(f)[0] for f in csv_files]

    if not csv_files:
        st.error("No CSV files found in the 'data/' directory of the GitHub repository.")
        return

    if 'selected_file' not in st.session_state:
        st.session_state.selected_file = None

    if not st.session_state.quiz_started:
        # Present file options without extensions
        selected_file_no_ext = st.selectbox("Choose a CSV file", [""] + file_options)
        
        if selected_file_no_ext:
            # Retrieve the full filename (with extension) when selected
            full_filename = f"{selected_file_no_ext}.csv"
            file_path = f"data/{full_filename}"

            if st.button("Start Quiz", key="start_button"):
                st.session_state.selected_file = full_filename
                st.session_state.quiz_started = True
                st.rerun()

    if st.session_state.quiz_started:
        # Show the selected filename as the title of the quiz
        selected_file_no_ext = os.path.splitext(st.session_state.selected_file)[0]
        st.title(f"{selected_file_no_ext} Quiz")

        file_path = f"data/{st.session_state.selected_file}"
        display_quiz(file_path)

if __name__ == "__main__":
    main()
